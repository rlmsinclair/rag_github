import json

import numpy as np
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from config import Config
from rag_system import RAGSystem
import logging
import mysql.connector

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)
rag = RAGSystem(
    mysql_config=Config.MYSQL_CONFIG,
    anthropic_api_key=Config.ANTHROPIC_API_KEY,
    github_token=Config.GITHUB_TOKEN,
    github_username=Config.GITHUB_USERNAME
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_repository', methods=['POST'])
def add_repository():
    repo_url = request.json.get('repo_url')
    try:
        rag.clone_repository(repo_url)
        return jsonify({'status': 'success', 'message': f'Repository {repo_url} added successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/search_files', methods=['POST'])
def search_files():
    query = request.json.get('query')
    if not query:
        return jsonify({'error': 'Search query is required'}), 400

    try:
        logger.info(f"Starting search request with query: {query}")

        # Connect to database
        conn = mysql.connector.connect(**Config.MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Get all repositories with their details
        cursor.execute("""
            SELECT 
                id, repo_url, repo_name, description, overview,
                main_technologies, key_features, architecture,
                dependencies, last_updated
            FROM repositories
        """)
        repositories = cursor.fetchall()

        # Get all files
        cursor.execute("""
            SELECT 
                f.id, f.repo_id, f.file_path, f.content,
                f.description, f.primary_language,
                f.key_components, f.dependencies,
                r.repo_name
            FROM files f
            JOIN repositories r ON f.repo_id = r.id
        """)
        files = cursor.fetchall()

        # Process repositories
        processed_repos = []
        for repo in repositories:
            # Parse JSON strings
            repo['main_technologies'] = json.loads(repo['main_technologies'] or '[]')
            repo['key_features'] = json.loads(repo['key_features'] or '[]')
            repo['dependencies'] = json.loads(repo['dependencies'] or '[]')

            # Create file tree structure
            repo_files = [f for f in files if f['repo_id'] == repo['id']]
            file_tree = build_file_tree(repo_files)

            repo_data = {
                'id': repo['id'],
                'type': 'repository',
                'repo_url': repo['repo_url'],
                'name': repo['repo_name'],
                'description': repo['description'],
                'overview': repo['overview'],
                'main_technologies': repo['main_technologies'],
                'key_features': repo['key_features'],
                'architecture': repo['architecture'],
                'dependencies': repo['dependencies'],
                'last_updated': repo['last_updated'].isoformat() if repo['last_updated'] else None,
                'file_tree': file_tree,
                'similarity': calculate_similarity(query, f"{repo['description']} {repo['overview']}")
            }
            processed_repos.append(repo_data)

        # Sort repositories by similarity
        processed_repos.sort(key=lambda x: x['similarity'], reverse=True)

        logger.info(f"Search completed successfully, found {len(processed_repos)} repositories")
        return jsonify(processed_repos)

    except Exception as e:
        logger.error(f"Error in search_files endpoint: {str(e)}")
        logger.exception("Full traceback:")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


def build_file_tree(files):
    """Build a hierarchical file tree structure."""
    root = {'name': '/', 'type': 'directory', 'children': {}}

    for file in files:
        path_parts = file['file_path'].split('/')
        current = root

        # Build directory structure
        for i, part in enumerate(path_parts[:-1]):
            if part not in current['children']:
                current['children'][part] = {
                    'name': part,
                    'type': 'directory',
                    'path': '/'.join(path_parts[:i + 1]),
                    'children': {}
                }
            current = current['children'][part]

        # Add file
        filename = path_parts[-1]
        current['children'][filename] = {
            'name': filename,
            'type': 'file',
            'id': file['id'],
            'path': file['file_path'],
            'description': file['description'],
            'language': file['primary_language'],
            'key_components': json.loads(file['key_components'] or '[]'),
            'dependencies': json.loads(file['dependencies'] or '[]')
        }

    # Convert children dictionaries to sorted lists
    def dict_to_list(node):
        if 'children' in node:
            children = node['children']
            node['children'] = sorted(
                [dict_to_list(child) for child in children.values()],
                key=lambda x: (x['type'] != 'directory', x['name'].lower())
            )
        return node

    return dict_to_list(root)['children']


def calculate_similarity(query, text):
    """Calculate similarity between query and text using embeddings."""
    try:
        query_embedding = rag.generate_embedding(query)
        text_embedding = rag.generate_embedding(text)

        # Calculate cosine similarity
        similarity = np.dot(query_embedding, text_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(text_embedding)
        )
        return float(similarity)
    except Exception as e:
        logger.error(f"Error calculating similarity: {str(e)}")
        return 0.0

@app.route('/stream_prompt', methods=['POST'])
def stream_prompt():
    data = request.get_json()
    if not data or 'file_ids' not in data or 'prompt' not in data:
        return jsonify({'error': 'Both file IDs and prompt are required'}), 400

    file_ids = data['file_ids']
    prompt = data['prompt']

    def generate():
        try:
            selected_files = rag.get_file_contents(file_ids)
            for text in rag.stream_prompt_response(selected_files, prompt):
                yield f"data: {json.dumps({'text': text})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )

if __name__ == '__main__':
    app.run(debug=True)
