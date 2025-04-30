# GitHub RAG System

A rather clever little system for retrieving and analyzing code repositories with AI assistance, if I do say so myself.

## What's All This Then?

This project implements a Retrieval-Augmented Generation (RAG) system specifically designed for code repositories. It's like having a personal assistant who's read all your code but doesn't judge you for those questionable variable names from 2 AM coding sessions.

The system allows you to:

- Add GitHub repositories to the system (yes, even that one you're slightly embarrassed about)
- Search through repositories and files with semantic understanding (far more sophisticated than Ctrl+F, I assure you)
- Select files and generate AI responses based on their contents (like pair programming, but your partner is infinitely patient)

## Technical Bits and Bobs

### Backend

- **Flask**: Serving the application with the quiet dignity of a British butler
- **MySQL**: Storing data with more reliability than British weather forecasts
- **Anthropic Claude API**: Providing AI responses that are almost as insightful as a proper cup of tea
- **Ollama**: Generating embeddings with the efficiency of a London tube during non-peak hours
- **GitHub API**: Accessing repositories with less drama than a Shakespeare play

### Frontend

- **HTML/CSS/JavaScript**: A simple yet effective trio, much like tea, biscuits, and a good book
- **Responsive Design**: Adapts to different screen sizes with the flexibility of British queuing etiquette
- **Dark Mode Support**: For those who code at night, like vampires or project managers with impossible deadlines

## How It Works

1. **Repository Ingestion**: 
   - Clones repositories from GitHub
   - Analyzes files to extract descriptions, key components, and dependencies
   - Generates embeddings for semantic search
   - Creates a comprehensive repository overview

2. **Search Functionality**:
   - Performs semantic search across repositories and files
   - Ranks results by relevance
   - Displays detailed information about repositories and files

3. **AI Interaction**:
   - Select files of interest
   - Provide a prompt related to the selected files
   - Receive AI-generated responses based on the file contents

## Setup

1. Clone this repository (a bit meta, isn't it?)
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   ```
   MYSQL_HOST=your_mysql_host
   MYSQL_USER=your_mysql_user
   MYSQL_PASSWORD=your_mysql_password
   MYSQL_DATABASE=your_mysql_database
   ANTHROPIC_API_KEY=your_anthropic_api_key
   OLLAMA_API_URL=your_ollama_api_url
   GITHUB_TOKEN=your_github_token
   GITHUB_USERNAME=your_github_username
   ```
4. Initialize the database:
   ```bash
   python -c "from rag_system import RAGSystem; RAGSystem(mysql_config={'host': 'your_host', 'user': 'your_user', 'password': 'your_password', 'database': 'your_database'}, anthropic_api_key='your_key').setup_database()"
   ```
5. Run the application:
   ```bash
   python app.py
   ```
6. Visit `http://localhost:5000` in your browser, preferably with a cup of tea in hand

## Usage

### Adding a Repository

1. Enter a GitHub repository URL in the "Add Repository" section
2. Click "Add Repository"
3. Wait patiently (a quintessentially British trait) while the system processes the repository

### Searching Files

1. Enter a search query in the "Search Files" section
2. Click "Search"
3. Browse through the results with the quiet satisfaction of finding exactly what you were looking for

### Generating AI Responses

1. Select files of interest from the search results
2. Enter a prompt in the "AI Prompt" section
3. Click "Generate Response"
4. Marvel at the response with the reserved appreciation of someone who just witnessed a perfect parallel park

## Limitations

- The system may occasionally struggle with very large repositories, much like a Londoner trying to find affordable housing
- AI responses, while impressive, are not infallible - rather like our beloved British rail system
- The embedding model has its quirks, not unlike British slang to non-natives

## Future Improvements

- Support for private repositories (for those code secrets best kept between you and your compiler)
- Additional language models for more diverse AI responses
- Improved file filtering options, for when you absolutely must ignore those test files
- Real-time collaboration features, for those rare moments when you actually want to code with others

## Contributing

Pull requests are welcome, though they will be reviewed with the thorough scrutiny of a British customs officer.

## License

This project is licensed under the MIT License - see the LICENSE file for details, if you're the sort who actually reads those things.

---

*Built with more care than a properly brewed cup of Earl Grey.*
