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

    def is_binary_content(self, content: bytes) -> bool:
        """Check if content appears to be binary."""
        textchars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
        return bool(content.translate(None, textchars))

    def is_valid_text_file(self, file_path: str, content: bytes) -> bool:
        """Check if a file is a valid text file based on extension and content."""
        # Skip certain directories
        if any(part.startswith('.') for part in Path(file_path).parts):
            return False

        # Skip common binary file extensions
        binary_extensions = {
            '.pyc', '.pyo', '.so', '.dll', '.dylib', '.jar', '.war', '.ear',
            '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar', '.pdf', '.doc',
            '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png',
            '.gif', '.bmp', '.ico', '.tiff', '.class', '.exe', '.bin', '.dat',
            '.db', '.sqlite', '.o', '.obj', '.lib', '.a', '.mo', '.ttf', '.woff',
            '.woff2', '.eot'
        }

        if Path(file_path).suffix.lower() in binary_extensions:
            return False

        # Check if content is binary
        try:
            return not self.is_binary_content(content)
        except:
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

            # Insert or update repository record
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

            # Clear existing files for this repository
            cursor.execute("DELETE f FROM files f WHERE f.repo_id = %s", (repo_id,))
            conn.commit()

            # Process all files in the repository
            for root, _, files in os.walk(base_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, base_path)

                    try:
                        with open(file_path, 'rb') as f:
                            content_bytes = f.read()

                        # Skip if not a valid text file
                        if not self.is_valid_text_file(relative_path, content_bytes):
                            print(f"Skipping binary or invalid file: {relative_path}")
                            continue

                        try:
                            content = content_bytes.decode('utf-8')
                        except UnicodeDecodeError:
                            print(f"Skipping file due to encoding issues: {relative_path}")
                            continue

                        # Skip empty files or files that are too large
                        if not content.strip() or len(content) > 1_000_000:  # Skip files larger than 1MB
                            print(f"Skipping empty or large file: {relative_path}")
                            continue

                        # Insert file content
                        cursor.execute(
                            "INSERT INTO files (repo_id, file_path, content) VALUES (%s, %s, %s)",
                            (repo_id, relative_path, content)
                        )
                        file_id = cursor.lastrowid

                        try:
                            # Generate and store embedding
                            embedding = self.generate_embedding(content)
                            embedding_json = json.dumps(embedding)

                            cursor.execute(
                                "INSERT INTO embeddings (file_id, embedding) VALUES (%s, %s)",
                                (file_id, embedding_json)
                            )
                            conn.commit()
                            print(f"Successfully processed: {relative_path}")
                        except Exception as e:
                            print(f"Error generating embedding for {relative_path}: {str(e)}")
                            # Delete the file entry if we couldn't generate an embedding
                            cursor.execute("DELETE FROM files WHERE id = %s", (file_id,))
                            conn.commit()

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

    def parse_github_url(self, repo_url: str) -> tuple:
        """Extract owner and repo name from GitHub URL."""
        path = urlparse(repo_url).path.strip('/')
        owner, repo = path.split('/')
        # Remove .git if present
        repo = repo.replace('.git', '')
        return owner, repo

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
                FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
                INDEX idx_repo_path (repo_id, file_path(750))
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')

        # Create embeddings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS embeddings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                file_id INT,
                embedding LONGTEXT,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
                INDEX idx_file_id (file_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')

        conn.commit()
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

    def search_files(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar content using vector similarity."""
        query_embedding = self.generate_embedding(query)
        query_embedding_array = np.array(query_embedding)

        conn = mysql.connector.connect(**self.mysql_config)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT f.id, f.content, f.file_path, r.repo_name, e.embedding
            FROM embeddings e
            JOIN files f ON e.file_id = f.id
            JOIN repositories r ON f.repo_id = r.id
        ''')

        results = []
        for file_id, content, file_path, repo_name, embedding_str in cursor:
            embedding = np.array(json.loads(embedding_str))
            similarity = np.dot(query_embedding_array, embedding) / (
                    np.linalg.norm(query_embedding_array) * np.linalg.norm(embedding)
            )
            results.append({
                'id': file_id,
                'content': content,
                'file_path': file_path,
                'repo_name': repo_name,
                'similarity': similarity
            })

        conn.close()
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:top_k]

    def get_file_contents(self, file_ids: List[int]) -> List[Dict[str, str]]:
        """Retrieve file contents for selected files."""
        conn = mysql.connector.connect(**self.mysql_config)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT f.content, f.file_path, r.repo_name
            FROM files f
            JOIN repositories r ON f.repo_id = r.id
            WHERE f.id IN (%s)
        ''' % ','.join(['%s'] * len(file_ids)), file_ids)

        results = []
        for content, file_path, repo_name in cursor:
            results.append({
                'content': content,
                'file_path': file_path,
                'repo_name': repo_name
            })

        conn.close()
        return results

    def stream_prompt_response(self, selected_files: List[Dict[str, str]], prompt: str) -> Generator[str, None, None]:
        """Stream response for the prompt with selected file contents."""
        context = "\n\n".join([
            f"From {file['repo_name']}/{file['file_path']}:\n{file['content']}"
            for file in selected_files
        ])

        stream = self.client.messages.stream(
            model="claude-3-sonnet-20240229",
            system="You are a helpful assistant. Respond in short and clear sentences.",
            messages=[
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nPrompt: {prompt}"
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
