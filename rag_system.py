import os
import json
import anthropic
import mysql.connector
import requests
import numpy as np
from pathlib import Path
import base64
import shutil
from typing import List, Dict, Any, Generator
from urllib.parse import urlparse
import zipfile
import io



class RAGSystem:
    def __init__(self, mysql_config: Dict[str, str], anthropic_api_key: str,
                 github_token: str = None, github_username: str = None):
        self.mysql_config = mysql_config
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        self.github_token = github_token
        self.github_username = github_username
        self.setup_database()
        self.github_headers = {'Authorization': f'token {self.github_token}'} if self.github_token else {}

    # Update the stream_query_with_context method in rag_system.py
    # Update the stream_query_with_context method in rag_system.py
    def stream_query_with_context(self, search_query: str, prompt: str) -> Generator[str, None, None]:
        """Stream query response from Claude with relevant context."""
        similar_contents = self.search_similar_content(search_query)
        context = "\n\n".join([
            f"From {result['repo_name']}/{result['file_path']}:\n{result['content'][:1000]}"
            for result in similar_contents
        ])

        stream = self.client.messages.stream(
            model="claude-3-5-sonnet-20241022",
            system="Respond in short and clear sentences.",
            max_tokens=1000,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"You are a helpful assistant. Use the following code context to answer questions.\n\nContext from repository search for '{search_query}':\n\n{context}\n\nPrompt: {prompt}"
                        }
                    ]
                }
            ]
        )

        for chunk in stream:
            if chunk.type == "content_block_delta":
                yield chunk.text
            elif chunk.type == "message_delta":
                continue
            elif chunk.type == "error":
                yield f"Error: {chunk.error}"

    def parse_github_url(self, repo_url: str) -> tuple:
        """Extract owner and repo name from GitHub URL."""
        path = urlparse(repo_url).path.strip('/')
        owner, repo = path.split('/')
        # Remove .git if present
        repo = repo.replace('.git', '')
        return owner, repo

    def is_text_file(self, file_path: str) -> bool:
        """Check if a file is a text file by file extension and content."""
        # Common text file extensions
        text_extensions = {
            '.txt', '.md', '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css',
            '.scss', '.json', '.yaml', '.yml', '.xml', '.csv', '.ini', '.conf',
            '.sh', '.bash', '.zsh', '.sql', '.php', '.rb', '.java', '.c', '.cpp',
            '.h', '.hpp', '.cs', '.go', '.rs', '.swift', '.kt', '.kts', '.r',
            '.dart', '.lua', '.pl', '.pm', '.t', '.vim', '.gradle', '.env',
            '.gitignore', '.dockerignore', '.editorconfig', 'Dockerfile',
            'Makefile', '.vue', '.svelte', '.astro', '.rs', '.toml'
        }

        # Check extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext in text_extensions:
            return True

        # For files without extension, try reading as text
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read(1024)  # Try reading first 1KB
            return True
        except UnicodeDecodeError:
            return False

    def clone_repository(self, repo_url: str) -> None:
        """Download repository content using GitHub API and store in database."""
        owner, repo_name = self.parse_github_url(repo_url)
        temp_dir = f"temp_{repo_name}"

        try:
            # Download repository as zip using GitHub API
            download_url = f'https://api.github.com/repos/{owner}/{repo_name}/zipball'
            response = requests.get(
                download_url,
                headers=self.github_headers,
                stream=True
            )
            response.raise_for_status()

            # Extract zip content
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                zip_ref.extractall(temp_dir)

            # Get the extracted folder name (GitHub adds a prefix)
            extracted_dir = next(os.walk(temp_dir))[1][0]
            base_path = os.path.join(temp_dir, extracted_dir)

            conn = mysql.connector.connect(**self.mysql_config)
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO repositories (repo_url, repo_name) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE last_updated=CURRENT_TIMESTAMP",
                (repo_url, repo_name)
            )
            conn.commit()
            repo_id = cursor.lastrowid

            if not repo_id:
                cursor.execute("SELECT id FROM repositories WHERE repo_url = %s", (repo_url,))
                repo_id = cursor.fetchone()[0]

            # Process all files in the repository
            for root, _, files in os.walk(base_path):
                if '.git' in root:
                    continue

                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, base_path)

                    # Skip if not a text file
                    if not self.is_text_file(file_path):
                        print(f"Skipping non-text file: {relative_path}")
                        continue

                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # Skip empty files or files that are too large
                        if not content.strip() or len(content) > 1_000_000:  # Skip files larger than 1MB
                            print(f"Skipping empty or large file: {relative_path}")
                            continue

                        cursor.execute(
                            "INSERT INTO files (repo_id, file_path, content) VALUES (%s, %s, %s) "
                            "ON DUPLICATE KEY UPDATE content=VALUES(content)",
                            (repo_id, relative_path, content)
                        )
                        file_id = cursor.lastrowid

                        try:
                            embedding = self.generate_embedding(content)
                            embedding_json = json.dumps(embedding)

                            cursor.execute(
                                "INSERT INTO embeddings (file_id, embedding) VALUES (%s, %s) "
                                "ON DUPLICATE KEY UPDATE embedding=VALUES(embedding)",
                                (file_id, embedding_json)
                            )
                            conn.commit()
                        except Exception as e:
                            print(f"Error generating embedding for {relative_path}: {str(e)}")
                            # Delete the file entry if we couldn't generate an embedding
                            cursor.execute("DELETE FROM files WHERE id = %s", (file_id,))
                            conn.commit()

                    except UnicodeDecodeError:
                        print(f"Skipping file due to encoding issues: {relative_path}")
                    except Exception as e:
                        print(f"Error processing file {relative_path}: {str(e)}")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to download repository: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to process repository: {str(e)}")
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            if 'conn' in locals():
                conn.close()

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using BGE-large model via Ollama API."""
        response = requests.post(
            f"{os.getenv('OLLAMA_API_URL')}/api/embeddings",
            json={
                "model": "bge-large",
                "prompt": text
            }
        )
        return response.json()['embedding']

    def search_similar_content(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar content using vector similarity."""
        query_embedding = self.generate_embedding(query)
        query_embedding_array = np.array(query_embedding)

        conn = mysql.connector.connect(**self.mysql_config)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT f.content, f.file_path, r.repo_name, e.embedding
            FROM embeddings e
            JOIN files f ON e.file_id = f.id
            JOIN repositories r ON f.repo_id = r.id
        ''')

        results = []
        for content, file_path, repo_name, embedding_str in cursor:
            embedding = np.array(json.loads(embedding_str))
            similarity = np.dot(query_embedding_array, embedding) / (
                    np.linalg.norm(query_embedding_array) * np.linalg.norm(embedding)
            )
            results.append({
                'content': content,
                'file_path': file_path,
                'repo_name': repo_name,
                'similarity': similarity
            })

        conn.close()
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:top_k]

    def stream_query_with_context(self, query: str, system_prompt: str = "You are a helpful assistant.") -> Generator[
        str, None, None]:
        """Stream query response from Claude with relevant context."""
        similar_contents = self.search_similar_content(query)
        context = "\n\n".join([
            f"From {result['repo_name']}/{result['file_path']}:\n{result['content'][:1000]}"
            for result in similar_contents
        ])

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuery: {query}"
            }
        ]

        with self.client.messages.stream(
                model="claude-3-sonnet-20240229",
                messages=messages,
                max_tokens=1024
        ) as stream:
            for text in stream.text_stream:
                yield text

    def setup_database(self) -> None:
        """Create necessary database tables if they don't exist."""
        conn = mysql.connector.connect(**self.mysql_config)
        cursor = conn.cursor()

        # First, ensure we're using the right character set and collation
        cursor.execute("SET NAMES utf8mb4")
        cursor.execute("SET CHARACTER SET utf8mb4")
        cursor.execute("SET character_set_connection=utf8mb4")

        # Create repositories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repositories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                repo_url VARCHAR(255) UNIQUE,
                repo_name VARCHAR(255),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')

        # Create files table with adjusted index length
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INT AUTO_INCREMENT PRIMARY KEY,
                repo_id INT,
                file_path VARCHAR(1000),
                content LONGTEXT,
                FOREIGN KEY (repo_id) REFERENCES repositories(id),
                INDEX idx_repo_path (repo_id, file_path(750))
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')

        # Create embeddings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS embeddings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                file_id INT,
                embedding LONGTEXT,
                FOREIGN KEY (file_id) REFERENCES files(id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')

        conn.commit()
        conn.close()
