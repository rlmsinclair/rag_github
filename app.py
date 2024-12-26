import json
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from config import Config
from rag_system import RAGSystem

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
        results = rag.search_files(query)
        return jsonify([{
            'id': r['id'],
            'file_path': r['file_path'],
            'repo_name': r['repo_name'],
            'content': r['content'],  # Send full content for preview
            'preview': r['content'][:200] + '...' if len(r['content']) > 200 else r['content']
        } for r in results])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
