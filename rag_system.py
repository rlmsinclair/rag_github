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
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGSystem:
    def __init__(self, mysql_config: Dict[str, str], anthropic_api_key: str,
                 github_token: str = None, github_username: str = None):
        self.mysql_config = mysql_config
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        self.github_token = github_token
        self.github_username = github_username
        self.setup_database()
        self.github_headers = {'Authorization': f'token {self.github_token}'} if self.github_token else {}

    def get_file_description(self, file_path: str, content: str) -> Dict[str, str]:
        """Get file description from Claude."""
        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0,
                system="You are a helpful assistant that describes code files in natural language. "
                       "Respond ONLY with a JSON object containing these fields:\n"
                       "- file_name: the name of the file\n"
                       "- primary_language: the main programming language used\n"
                       "- description: a clear, detailed description of what the file does\n"
                       "- key_components: main functions, classes, or features\n"
                       "- dependencies: any external libraries or imports used\n"
                       "Keep descriptions concise but informative.",
                messages=[
                    {
                        "role": "user",
                        "content": f"Describe this file ({file_path}):\n\n{content}"
                    }
                ]
            )

            try:
                # Extract JSON from the response
                description = message.content[0].text
                formatted_description = json.loads(self.extract_json(description))

                # Ensure all required fields are present
                required_fields = ['file_name', 'primary_language', 'description', 'key_components', 'dependencies']
                for field in required_fields:
                    if field not in formatted_description:
                        formatted_description[field] = ''

                return formatted_description

            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse Claude response for {file_path}: {e}")
                # Return a default structure if parsing fails
                return {
                    'file_name': os.path.basename(file_path),
                    'primary_language': '',
                    'description': 'Description unavailable',
                    'key_components': [],
                    'dependencies': []
                }

        except Exception as e:
            logger.error(f"Error getting description for {file_path}: {str(e)}")
            raise

    def setup_database(self) -> None:
        """Create necessary database tables if they don't exist."""
        conn = mysql.connector.connect(**self.mysql_config)
        cursor = conn.cursor()

        # Set up proper character encoding
        cursor.execute("SET NAMES utf8mb4")
        cursor.execute("SET CHARACTER SET utf8mb4")
        cursor.execute("SET character_set_connection=utf8mb4")

        # Create repositories table with description
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repositories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                repo_url VARCHAR(255) UNIQUE,
                repo_name VARCHAR(255),
                description TEXT,
                overview TEXT,
                main_technologies TEXT,
                key_features TEXT,
                architecture TEXT,
                dependencies TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_repo_url (repo_url)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')

        # Create files table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INT AUTO_INCREMENT PRIMARY KEY,
                repo_id INT,
                file_path VARCHAR(1000),
                content LONGTEXT,
                description TEXT,
                primary_language VARCHAR(50),
                key_components TEXT,
                dependencies TEXT,
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

        # Add description column if it doesn't exist (for existing installations)
        try:
            cursor.execute('''
                ALTER TABLE repositories 
                ADD COLUMN IF NOT EXISTS description TEXT 
                AFTER repo_name
            ''')
        except:
            # MySQL version might not support IF NOT EXISTS for ALTER TABLE
            try:
                cursor.execute('''
                    ALTER TABLE repositories 
                    ADD COLUMN description TEXT 
                    AFTER repo_name
                ''')
            except:
                # Column might already exist
                pass

        conn.commit()
        conn.close()

    def generate_repository_description(self, repo_id: int) -> Dict[str, Any]:
        """Generate a complete repository description using file descriptions."""
        conn = mysql.connector.connect(**self.mysql_config)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT file_path, description, key_components, dependencies 
            FROM files 
            WHERE repo_id = %s
        """, (repo_id,))

        files = cursor.fetchall()

        # Combine all file descriptions
        file_descriptions = [
            f"File: {file[0]}\nDescription: {file[1]}\nKey Components: {file[2]}\nDependencies: {file[3]}"
            for file in files
        ]

        combined_description = "\n\n".join(file_descriptions)

        try:
            message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                temperature=0,
                system="You are a helpful assistant that provides repository summaries. "
                       "Your response must be a valid JSON object. "
                       "Include these exact fields in your JSON response:\n"
                       "{\n"
                       '  "overview": "brief overview of the repository",\n'
                       '  "description": "comprehensive description of the repository",\n'
                       '  "main_technologies": ["list", "of", "technologies"],\n'
                       '  "key_features": ["list", "of", "features"],\n'
                       '  "architecture": "brief architecture description",\n'
                       '  "dependencies": ["list", "of", "dependencies"]\n'
                       "}\n"
                       "Ensure your response contains only the JSON object with no additional text.",
                messages=[
                    {
                        "role": "user",
                        "content": f"Based on these file descriptions, generate a repository summary as a JSON object:\n\n{combined_description}"
                    }
                ]
            )

            # Get the response text and try to parse it as JSON
            response_text = message.content[0].text.strip()
            logger.info(f"Claude response: {response_text}")  # Log the response for debugging

            try:
                # Extract JSON from response
                json_str = self.extract_json(response_text)
                logger.info(f"Extracted JSON: {json_str}")

                # Parse the extracted JSON
                repo_info = json.loads(json_str)

                # Validate required fields
                required_fields = ['overview', 'description', 'main_technologies',
                                   'key_features', 'architecture', 'dependencies']
                missing_fields = [field for field in required_fields if field not in repo_info]

                if missing_fields:
                    raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

                # Store repository description
                cursor.execute("""
                    UPDATE repositories 
                    SET 
                        description = %s,
                        overview = %s,
                        main_technologies = %s,
                        key_features = %s,
                        architecture = %s,
                        dependencies = %s
                    WHERE id = %s
                """, (
                    repo_info['description'],
                    repo_info['overview'],
                    json.dumps(repo_info['main_technologies']),
                    json.dumps(repo_info['key_features']),
                    repo_info['architecture'],
                    json.dumps(repo_info['dependencies']),
                    repo_id
                ))

                conn.commit()
                return repo_info

            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse Claude response: {e}")
                logger.error(f"Response text: {response_text}")

                # Fallback: Create a basic structure
                fallback_info = {
                    'overview': 'Repository overview not available',
                    'description': 'Repository description not available',
                    'main_technologies': [],
                    'key_features': [],
                    'architecture': 'Architecture information not available',
                    'dependencies': []
                }

                # Store fallback information
                cursor.execute("""
                    UPDATE repositories 
                    SET 
                        description = %s,
                        overview = %s,
                        main_technologies = %s,
                        key_features = %s,
                        architecture = %s,
                        dependencies = %s
                    WHERE id = %s
                """, (
                    fallback_info['description'],
                    fallback_info['overview'],
                    json.dumps(fallback_info['main_technologies']),
                    json.dumps(fallback_info['key_features']),
                    fallback_info['architecture'],
                    json.dumps(fallback_info['dependencies']),
                    repo_id
                ))

                conn.commit()
                return fallback_info
        except Exception as e:
            logger.error(f"Error generating repository description: {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()

    def extract_json(self, text: str) -> str:
        """Extract JSON object from text by finding the outermost braces."""
        try:
            start = text.index('{')
            end = text.rindex('}') + 1
            return text[start:end]
        except ValueError as e:
            logger.error(f"Failed to find JSON brackets in text: {e}")
            raise

    def search_files(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar content using vector similarity."""
        logger.info(f"Starting search with query: {query}")

        try:
            logger.info("Generating query embedding")
            query_embedding = self.generate_embedding(query)
            query_embedding_array = np.array(query_embedding)
            logger.info("Query embedding generated successfully")

            conn = mysql.connector.connect(**self.mysql_config)
            cursor = conn.cursor(dictionary=True)
            logger.info("Database connection established")

            try:
                # Repository matches
                logger.info("Fetching repositories")
                cursor.execute('''
                    SELECT 
                        id, repo_name, description, overview, main_technologies, 
                        key_features, architecture, dependencies
                    FROM repositories
                ''')

                repo_rows = cursor.fetchall()
                logger.info(f"Found {len(repo_rows)} repositories")
                repositories = []

                for repo in repo_rows:
                    try:
                        logger.debug(f"Processing repository: {repo.get('repo_name', 'unknown')}")
                        logger.debug(f"Repository data: {json.dumps(repo, default=str)}")

                        # Build repository description for embedding
                        repo_desc = f"{repo['description'] or ''} {repo['overview'] or ''}"
                        if repo['main_technologies']:
                            try:
                                tech_list = json.loads(repo['main_technologies'])
                                repo_desc += f" {' '.join(tech_list)}"
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse main_technologies for repo {repo['repo_name']}: {e}")

                        logger.debug(f"Generating embedding for repo: {repo['repo_name']}")
                        repo_embedding = self.generate_embedding(repo_desc)

                        # Calculate similarity
                        similarity = np.dot(query_embedding_array, np.array(repo_embedding)) / (
                                np.linalg.norm(query_embedding_array) * np.linalg.norm(repo_embedding)
                        )

                        # Prepare repository data
                        repo_data = {
                            'id': repo['id'],
                            'repo_name': repo['repo_name'],
                            'description': repo['description'],
                            'type': 'repository',
                            'similarity': float(similarity),  # Convert numpy float to Python float
                            'overview': repo['overview'],
                            'main_technologies': json.loads(repo['main_technologies']) if repo[
                                'main_technologies'] else [],
                            'key_features': json.loads(repo['key_features']) if repo['key_features'] else [],
                            'architecture': repo['architecture'],
                            'dependencies': json.loads(repo['dependencies']) if repo['dependencies'] else []
                        }

                        logger.debug(f"Repository data prepared: {json.dumps(repo_data, default=str)}")
                        repositories.append(repo_data)

                    except Exception as e:
                        logger.error(f"Error processing repository {repo.get('repo_name', 'unknown')}: {str(e)}")
                        logger.exception("Full traceback:")
                        continue

                # File matches
                logger.info("Fetching files")
                cursor.execute('''
                    SELECT 
                        f.id, f.content, f.file_path, r.repo_name, r.id as repo_id,
                        e.embedding, f.description, f.key_components, f.dependencies,
                        f.primary_language
                    FROM embeddings e
                    JOIN files f ON e.file_id = f.id
                    JOIN repositories r ON f.repo_id = r.id
                ''')

                file_rows = cursor.fetchall()
                logger.info(f"Found {len(file_rows)} files")
                files = []

                for file in file_rows:
                    try:
                        logger.debug(f"Processing file: {file.get('file_path', 'unknown')}")
                        logger.debug(
                            f"File data: {json.dumps({k: v for k, v in file.items() if k != 'content'}, default=str)}")

                        if not file['file_path']:
                            logger.warning(f"Skipping file with ID {file['id']} - no file_path")
                            continue

                        # Parse embedding and calculate similarity
                        embedding = np.array(json.loads(file['embedding']))
                        similarity = np.dot(query_embedding_array, embedding) / (
                                np.linalg.norm(query_embedding_array) * np.linalg.norm(embedding)
                        )

                        # Create folder structure
                        path_parts = file['file_path'].split('/')
                        folders = []
                        current_path = ""
                        for part in path_parts[:-1]:
                            current_path = f"{current_path}/{part}" if current_path else part
                            folders.append({
                                'path': current_path,
                                'name': part,
                                'type': 'folder'
                            })

                        # Prepare file data
                        file_data = {
                            'id': file['id'],
                            'repo_id': file['repo_id'],
                            'content': file['content'],
                            'file_path': file['file_path'],
                            'repo_name': file['repo_name'],
                            'type': 'file',
                            'similarity': float(similarity),  # Convert numpy float to Python float
                            'description': file['description'] or '',
                            'key_components': json.loads(file['key_components']) if file['key_components'] else [],
                            'dependencies': json.loads(file['dependencies']) if file['dependencies'] else [],
                            'primary_language': file['primary_language'] or 'unknown',
                            'folders': folders
                        }

                        logger.debug(
                            f"File data prepared: {json.dumps({k: v for k, v in file_data.items() if k != 'content'}, default=str)}")
                        files.append(file_data)

                    except Exception as e:
                        logger.error(f"Error processing file {file.get('file_path', 'unknown')}: {str(e)}")
                        logger.exception("Full traceback:")
                        continue

                # Sort and combine results
                logger.info(f"Sorting results - Repositories: {len(repositories)}, Files: {len(files)}")
                repositories.sort(key=lambda x: x['similarity'], reverse=True)
                files.sort(key=lambda x: x['similarity'], reverse=True)

                final_results = repositories[:top_k] + files[:top_k]
                logger.info(f"Returning {len(final_results)} total results")

                # Log the structure of the first result for debugging
                if final_results:
                    logger.debug(
                        f"Sample result structure: {json.dumps({k: v for k, v in final_results[0].items() if k != 'content'}, default=str)}")

                return final_results

            except Exception as e:
                logger.error(f"Database error in search_files: {str(e)}")
                logger.exception("Full traceback:")
                raise
            finally:
                cursor.close()
                conn.close()
                logger.info("Database connection closed")

        except Exception as e:
            logger.error(f"Top-level error in search_files: {str(e)}")
            logger.exception("Full traceback:")
            raise

        except Exception as e:
            logger.error(f"Error in search_files: {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()

    def clone_repository(self, repo_url: str) -> None:
        """Download repository content using GitHub API and store in database."""
        owner, repo_name = self.parse_github_url(repo_url)
        temp_dir = f"temp_{repo_name}"
        processed_files = 0
        skipped_files = 0
        error_files = 0

        try:
            logger.info(f"Starting clone of repository: {repo_url}")

            # Download and extract repository
            download_url = f'https://api.github.com/repos/{owner}/{repo_name}/zipball'
            response = requests.get(download_url, headers=self.github_headers, stream=True)
            response.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                zip_ref.extractall(temp_dir)
                total_files = len(zip_ref.filelist)
                logger.info(f"Total files in zip: {total_files}")

            extracted_dir = next(os.walk(temp_dir))[1][0]
            base_path = os.path.join(temp_dir, extracted_dir)

            conn = mysql.connector.connect(**self.mysql_config, autocommit=False)
            cursor = conn.cursor()

            try:
                # Repository setup
                cursor.execute(
                    "INSERT INTO repositories (repo_url, repo_name) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE last_updated=CURRENT_TIMESTAMP",
                    (repo_url, repo_name)
                )
                conn.commit()

                cursor.execute("SELECT id FROM repositories WHERE repo_url = %s", (repo_url,))
                repo_id = cursor.fetchone()[0]

                cursor.execute("DELETE f FROM files f WHERE f.repo_id = %s", (repo_id,))
                conn.commit()

                # Process files
                for root, _, files in os.walk(base_path):
                    for file in files:
                        try:
                            file_path = os.path.join(root, file)
                            relative_path = os.path.relpath(file_path, base_path)

                            logger.info(f"Processing file: {relative_path}")

                            # Read and validate file
                            try:
                                with open(file_path, 'rb') as f:
                                    content_bytes = f.read()
                            except Exception as e:
                                logger.error(f"Error reading file {relative_path}: {str(e)}")
                                error_files += 1
                                continue

                            if not self.is_valid_text_file(relative_path, content_bytes):
                                skipped_files += 1
                                continue

                            try:
                                content = content_bytes.decode('utf-8')
                            except UnicodeDecodeError:
                                logger.info(f"Skipping non-UTF8 file: {relative_path}")
                                skipped_files += 1
                                continue

                            if not content.strip() or len(content) > 1_000_000:
                                logger.info(f"Skipping empty or large file: {relative_path}")
                                skipped_files += 1
                                continue

                            # Get file description from Claude
                            try:
                                file_info = self.get_file_description(relative_path, content)

                                # Insert file with description
                                cursor.execute("""
                                    INSERT INTO files 
                                    (repo_id, file_path, content, primary_language, description, key_components, dependencies) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    repo_id,
                                    relative_path,
                                    content,
                                    file_info.get('primary_language'),
                                    file_info.get('description'),
                                    json.dumps(file_info.get('key_components')),
                                    json.dumps(file_info.get('dependencies'))
                                ))
                                file_id = cursor.lastrowid

                                # Generate embedding from description
                                description_text = f"{file_info.get('description')} {file_info.get('key_components')} {file_info.get('dependencies')}"
                                embedding = self.generate_embedding(description_text)

                                cursor.execute(
                                    "INSERT INTO embeddings (file_id, embedding) VALUES (%s, %s)",
                                    (file_id, json.dumps(embedding))
                                )
                                conn.commit()
                                processed_files += 1
                                logger.info(f"Successfully processed: {relative_path}")

                            except Exception as e:
                                logger.error(f"Error processing file {relative_path}: {str(e)}")
                                if 'file_id' in locals():
                                    cursor.execute("DELETE FROM files WHERE id = %s", (file_id,))
                                    conn.commit()
                                error_files += 1

                        except Exception as e:
                            logger.error(f"Error processing file: {str(e)}")
                            error_files += 1
                            conn.rollback()
                            continue

                logger.info(f"Repository processing completed:")
                logger.info(f"- Processed files: {processed_files}")
                logger.info(f"- Skipped files: {skipped_files}")
                logger.info(f"- Error files: {error_files}")

                try:
                    # After processing all files, generate repository description
                    repo_info = self.generate_repository_description(repo_id)
                    logger.info(f"Generated repository description: {repo_info}")

                except Exception as e:
                    logger.error(f"Error in repository description: {str(e)}")


            except Exception as e:
                logger.error(f"Database error: {str(e)}")
                conn.rollback()
                raise
            finally:
                cursor.close()
                conn.close()

        except Exception as e:
            logger.error(f"Failed to process repository: {str(e)}")
            raise
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def is_valid_text_file(self, file_path: str, content: bytes) -> bool:
        """Check if a file is a valid text file based on extension and content."""
        # Skip hidden files and directories
        if any(part.startswith('.') for part in Path(file_path).parts):
            logger.info(f"Skipping hidden file: {file_path}")
            return False

        # Skip common binary file extensions
        binary_extensions = {
            '.pyc', '.pyo', '.so', '.dll', '.dylib', '.jar', '.war', '.ear',
            '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar', '.pdf', '.doc',
            '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png',
            '.gif', '.bmp', '.ico', '.tiff', '.class', '.exe', '.bin', '.dat',
            '.db', '.sqlite', '.o', '.obj', '.lib', '.a', '.mo', '.ttf', '.woff',
            '.woff2', '.eot', '.svg', '.otf', '.mp3', '.mp4', '.avi', '.mov',
            '.wav', '.flac', '.ogg', '.webm', '.webp', '.psd', '.ai', '.eps'
        }

        if Path(file_path).suffix.lower() in binary_extensions:
            logger.info(f"Skipping binary extension: {file_path}")
            return False

        # Check if content appears to be binary
        textchars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
        is_binary = bool(content.translate(None, textchars))
        if is_binary:
            logger.info(f"Skipping binary content: {file_path}")
            return False

        return True

    def is_binary_content(self, content: bytes) -> bool:
        """Check if content appears to be binary."""
        textchars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
        return bool(content.translate(None, textchars))

    def parse_github_url(self, repo_url: str) -> tuple:
        """Extract owner and repo name from GitHub URL."""
        path = urlparse(repo_url).path.strip('/')
        owner, repo = path.split('/')
        # Remove .git if present
        repo = repo.replace('.git', '')
        return owner, repo

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

        message = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            temperature=0,
            system="You are a helpful assistant.",
            messages=[
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nPrompt: {prompt}"
                }
            ],
            stream=True
        )

        try:
            for chunk in message:
                if chunk.type == "content_block_delta" and chunk.delta.text:
                    yield chunk.delta.text
        except Exception as e:
            yield f"Error: {str(e)}"
