// Initialize state
const selectedFiles = new Set();

// Utility functions
function showLoading(id) {
  document.getElementById(id).style.display = 'flex';
}

function hideLoading(id) {
  document.getElementById(id).style.display = 'none';
}

function showError(id, message, isSuccess = false) {
  const error = document.getElementById(id);
  error.textContent = message;
  error.style.display = 'block';
  error.className = `message ${isSuccess ? 'success' : 'error'}`;
}

function hideError(id) {
  document.getElementById(id).style.display = 'none';
}

function tryParseJSON(jsonString, defaultValue) {
  try {
    return jsonString ? JSON.parse(jsonString) : defaultValue;
  } catch (e) {
    console.warn('Failed to parse JSON:', e);
    return defaultValue;
  }
}

function getLanguageColor(language) {
  const colors = {
    javascript: '#f1e05a',
    python: '#3572A5',
    java: '#b07219',
    typescript: '#2b7489',
    html: '#e34c26',
    css: '#563d7c',
    ruby: '#701516',
    go: '#00ADD8',
    rust: '#dea584',
    cpp: '#f34b7d',
    c: '#555555',
    csharp: '#178600',
    php: '#4F5D95',
    default: '#cccccc'
  };
  return colors[language?.toLowerCase()] || colors.default;
}

function getLanguageFromPath(path) {
  if (!path) return 'plaintext';
  const parts = path.split('.');
  if (parts.length <= 1) return 'plaintext';

  const ext = parts.pop().toLowerCase();
  const languageMap = {
    js: 'javascript',
    jsx: 'javascript',
    ts: 'typescript',
    tsx: 'typescript',
    py: 'python',
    java: 'java',
    html: 'html',
    css: 'css',
    json: 'json',
    md: 'markdown',
    php: 'php',
    rb: 'ruby',
    rs: 'rust',
    go: 'go',
    sql: 'sql',
    xml: 'xml',
    yaml: 'yaml',
    yml: 'yaml',
    sh: 'bash',
    bash: 'bash',
    cpp: 'cpp',
    c: 'c',
    h: 'c',
    hpp: 'cpp',
    cs: 'csharp'
  };
  return languageMap[ext] || 'plaintext';
}

function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function tryParseJSON(jsonString, defaultValue) {
  if (!jsonString) return defaultValue;

  try {
    // Handle string that might be already an array
    if (Array.isArray(jsonString)) return jsonString;

    // Try parsing the JSON string
    return JSON.parse(jsonString);
  } catch (e) {
    console.warn('Failed to parse JSON:', e);
    return defaultValue;
  }
}

function displaySearchResults(results) {
  const resultsContainer = document.getElementById('searchResults');
  resultsContainer.innerHTML = '';

  if (!results || results.length === 0) {
    resultsContainer.innerHTML = '<div class="no-results">No results found</div>';
    return;
  }

  results.forEach(repo => {
    const repoElement = document.createElement('div');
    repoElement.className = 'repository-item';

    // Ensure arrays are properly handled
    const technologies = Array.isArray(repo.main_technologies) ? repo.main_technologies : [];
    const features = Array.isArray(repo.key_features) ? repo.key_features : [];
    const dependencies = Array.isArray(repo.dependencies) ? repo.dependencies : [];

    repoElement.innerHTML = `
      <div class="repository-header">
        <h3>
          <svg class="repo-icon" viewBox="0 0 16 16" width="16" height="16">
            <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"></path>
          </svg>
          ${escapeHtml(repo.name)}
        </h3>
        <span class="similarity-score">
          ${(repo.similarity * 100).toFixed(2)}% match
        </span>
      </div>

      <div class="repository-content">
        <div class="repository-info">
          <p class="description">${escapeHtml(repo.description || 'No description available')}</p>
          
          <div class="metadata">
            ${technologies.length > 0 ? `
              <div class="technologies">
                ${technologies.map(tech => 
                  `<span class="tag technology">${escapeHtml(tech)}</span>`
                ).join('')}
              </div>
            ` : ''}
            
            ${repo.last_updated ? `
              <div class="last-updated">
                Last updated: ${new Date(repo.last_updated).toLocaleDateString()}
              </div>
            ` : ''}
          </div>

          <details class="repository-details">
            <summary>More Details</summary>
            <div class="details-content">
              ${repo.overview ? `
                <section>
                  <h4>Overview</h4>
                  <p>${escapeHtml(repo.overview)}</p>
                </section>
              ` : ''}

              ${features.length > 0 ? `
                <section>
                  <h4>Key Features</h4>
                  <ul>
                    ${features.map(feature => 
                      `<li>${escapeHtml(feature)}</li>`
                    ).join('')}
                  </ul>
                </section>
              ` : ''}

              ${repo.architecture ? `
                <section>
                  <h4>Architecture</h4>
                  <p>${escapeHtml(repo.architecture)}</p>
                </section>
              ` : ''}

              ${dependencies.length > 0 ? `
                <section>
                  <h4>Dependencies</h4>
                  <div class="tags">
                    ${dependencies.map(dep => 
                      `<span class="tag dependency">${escapeHtml(dep)}</span>`
                    ).join('')}
                  </div>
                </section>
              ` : ''}
            </div>
          </details>
        </div>

        <div class="file-tree">
          <h4>Repository Files</h4>
          <div class="tree-actions">
            <button onclick="expandAllNodes(this)">Expand All</button>
            <button onclick="collapseAllNodes(this)">Collapse All</button>
          </div>
          ${buildFileTree(repo.file_tree, repo.id)}
        </div>
      </div>
    `;

    resultsContainer.appendChild(repoElement);
  });
}

function buildFileTree(nodes, repoId, path = '') {
  if (!nodes || nodes.length === 0) return '';

  return `
    <ul class="tree-list">
      ${nodes.map(node => {
        const nodePath = path ? `${path}/${node.name}` : node.name;
        
        if (node.type === 'directory') {
          return `
            <li class="tree-item directory">
              <div class="directory-header">
                <span class="toggle-icon">▶</span>
                <span class="directory-name">${escapeHtml(node.name)}</span>
                <button class="select-all" onclick="selectAllFiles(this, ${repoId}, '${nodePath}')">
                  Select All
                </button>
              </div>
              ${buildFileTree(node.children, repoId, nodePath)}
            </li>
          `;
        } else {
          return `
            <li class="tree-item file">
              <div class="file-header ${selectedFiles.has(node.id.toString()) ? 'selected' : ''}"
                   onclick="toggleFileSelection('${node.id}', '${nodePath}')">
                <span class="file-icon">📄</span>
                <span class="file-name">${escapeHtml(node.name)}</span>
                <span class="file-language">${escapeHtml(node.language || '')}</span>
              </div>
            </li>
          `;
        }
      }).join('')}
    </ul>
  `;
}

function expandAllNodes(button) {
  const fileTree = button.closest('.file-tree');
  fileTree.querySelectorAll('.directory').forEach(dir => {
    dir.classList.add('expanded');
    dir.querySelector('.toggle-icon').textContent = '▼';
  });
}

function collapseAllNodes(button) {
  const fileTree = button.closest('.file-tree');
  fileTree.querySelectorAll('.directory').forEach(dir => {
    dir.classList.remove('expanded');
    dir.querySelector('.toggle-icon').textContent = '▶';
  });
}

function selectAllFiles(button, repoId, dirPath) {
  const directory = button.closest('.directory');
  const files = directory.querySelectorAll('.file');
  const isSelecting = button.textContent === 'Select All';

  files.forEach(file => {
    const fileHeader = file.querySelector('.file-header');
    const fileId = fileHeader.getAttribute('onclick').match(/'([^']+)'/)[1];

    if (isSelecting) {
      selectedFiles.add(fileId);
      fileHeader.classList.add('selected');
    } else {
      selectedFiles.delete(fileId);
      fileHeader.classList.remove('selected');
    }
  });

  button.textContent = isSelecting ? 'Deselect All' : 'Select All';
  updateSelectedFiles();
}

// Event delegation for directory toggling
document.addEventListener('click', function(e) {
  if (e.target.classList.contains('toggle-icon')) {
    const directory = e.target.closest('.directory');
    directory.classList.toggle('expanded');
    e.target.textContent = directory.classList.contains('expanded') ? '▼' : '▶';
  }
});

// Main functions
async function addRepository() {
  const repoUrl = document.getElementById('repoUrl').value.trim();
  if (!repoUrl) return;

  hideError('repoError');
  showLoading('repoLoading');

  try {
    const response = await fetch('/add_repository', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url: repoUrl })
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.message || 'Failed to add repository');

    document.getElementById('repoUrl').value = '';
    showError('repoError', 'Repository added successfully!', true);
  } catch (error) {
    showError('repoError', error.message);
  } finally {
    hideLoading('repoLoading');
  }
}

async function searchFiles() {
  const query = document.getElementById('searchQuery').value.trim();
  if (!query) return;

  hideError('searchError');
  showLoading('searchLoading');

  try {
    const response = await fetch('/search_files', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });

    if (!response.ok) {
      throw new Error('Failed to search files');
    }

    const results = await response.json();
    console.log('Search results:', results);
    displaySearchResults(results);
  } catch (error) {
    showError('searchError', error.message);
  } finally {
    hideLoading('searchLoading');
  }
}

function toggleFileSelection(fileId, filePath) {
  if (!fileId) return;
  const id = fileId.toString();

  if (selectedFiles.has(id)) {
    selectedFiles.delete(id);
  } else {
    selectedFiles.add(id);
  }
  updateSelectedFiles();
  updateSearchResults();
}

function updateSelectedFiles() {
  const container = document.getElementById('selectedFiles');
  if (selectedFiles.size === 0) {
    container.innerHTML = '<div class="no-files-selected">No files selected</div>';
    return;
  }

  container.innerHTML = Array.from(selectedFiles).map(fileId => `
    <div class="selected-file">
      <span>${escapeHtml(fileId)}</span>
      <button class="remove-file" onclick="toggleFileSelection('${fileId}')">
        <svg class="remove-icon" viewBox="0 0 16 16" width="16" height="16">
          <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"></path>
        </svg>
      </button>
    </div>
  `).join('');
}

function updateSearchResults() {
  const buttons = document.querySelectorAll('.result-item button');
  buttons.forEach(button => {
    const onclick = button.getAttribute('onclick');
    if (onclick) {
      const match = onclick.match(/'([^']+)'/);
      if (match) {
        const fileId = match[1];
        button.textContent = selectedFiles.has(fileId) ? 'Remove from Selection' : 'Add to Selection';
      }
    }
  });
}

async function submitPrompt() {
  const prompt = document.getElementById('promptInput').value.trim();
  if (!prompt || selectedFiles.size === 0) {
    showError('promptError', 'Please enter a prompt and select at least one file.');
    return;
  }

  hideError('promptError');
  showLoading('promptLoading');
  document.getElementById('promptResponse').textContent = '';

  try {
    const response = await fetch('/stream_prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_ids: Array.from(selectedFiles),
        prompt: prompt
      })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value);
      const lines = text.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.text) {
              document.getElementById('promptResponse').textContent += data.text;
            }
            if (data.error) {
              showError('promptError', data.error);
            }
          } catch (e) {
            console.error('Error parsing SSE data:', e);
          }
        }
      }
    }
  } catch (error) {
    showError('promptError', error.message);
  } finally {
    hideLoading('promptLoading');
  }
}

// Initialize event listeners when DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
  // Add Repository
  const addRepoButton = document.getElementById('addRepo');
  const repoUrlInput = document.getElementById('repoUrl');

  if (addRepoButton) {
    addRepoButton.addEventListener('click', addRepository);
  }

  if (repoUrlInput) {
    repoUrlInput.addEventListener('keypress', e => {
      if (e.key === 'Enter') addRepository();
    });
  }

  // Search Files
  const searchFilesButton = document.getElementById('searchFiles');
  const searchQueryInput = document.getElementById('searchQuery');

  if (searchFilesButton) {
    searchFilesButton.addEventListener('click', searchFiles);
  }

  if (searchQueryInput) {
    searchQueryInput.addEventListener('keypress', e => {
      if (e.key === 'Enter') searchFiles();
    });
  }

  // Submit Prompt
  const submitPromptButton = document.getElementById('submitPrompt');
  if (submitPromptButton) {
    submitPromptButton.addEventListener('click', submitPrompt);
  }

  // Initialize empty states
  updateSelectedFiles();
});
