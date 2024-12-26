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

function displaySearchResults(results) {
  const resultsContainer = document.getElementById('searchResults');
  resultsContainer.innerHTML = '';

  if (!results || results.length === 0) {
    resultsContainer.innerHTML = '<div class="no-results">No results found</div>';
    return;
  }

  results.forEach(result => {
    const resultItem = document.createElement('div');
    resultItem.className = 'result-item';

    if (result.type === 'repository') {
      const mainTechnologies = tryParseJSON(result.main_technologies, []);
      const keyFeatures = tryParseJSON(result.key_features, []);
      const dependencies = tryParseJSON(result.dependencies, []);

      resultItem.innerHTML = `
        <div class="repo-result">
          <div class="repo-header">
            <h3>
              <svg class="repo-icon" viewBox="0 0 16 16" width="16" height="16">
                <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"></path>
              </svg>
              ${escapeHtml(result.name)}
            </h3>
            <span class="similarity-score">
              <svg class="similarity-icon" viewBox="0 0 16 16" width="16" height="16">
                <path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path>
                <path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z"></path>
              </svg>
              ${(result.similarity * 100).toFixed(2)}% match
            </span>
          </div>

          <div class="repo-details">
            <div class="repo-description">
              ${escapeHtml(result.description || 'No description available')}
            </div>

            <details class="repo-additional-info">
              <summary>More Information</summary>
              <div class="info-grid">
                ${result.overview ? `
                  <div class="info-section">
                    <h4>Overview</h4>
                    <p>${escapeHtml(result.overview)}</p>
                  </div>
                ` : ''}

                ${mainTechnologies.length > 0 ? `
                  <div class="info-section">
                    <h4>Technologies</h4>
                    <div class="tags">
                      ${mainTechnologies.map(tech => `
                        <span class="tag">${escapeHtml(tech)}</span>
                      `).join('')}
                    </div>
                  </div>
                ` : ''}

                ${keyFeatures.length > 0 ? `
                  <div class="info-section">
                    <h4>Key Features</h4>
                    <ul class="feature-list">
                      ${keyFeatures.map(feature => `
                        <li>${escapeHtml(feature)}</li>
                      `).join('')}
                    </ul>
                  </div>
                ` : ''}

                ${result.architecture ? `
                  <div class="info-section">
                    <h4>Architecture</h4>
                    <p>${escapeHtml(result.architecture)}</p>
                  </div>
                ` : ''}

                ${dependencies.length > 0 ? `
                  <div class="info-section">
                    <h4>Dependencies</h4>
                    <div class="tags">
                      ${dependencies.map(dep => `
                        <span class="tag dependency">${escapeHtml(dep)}</span>
                      `).join('')}
                    </div>
                  </div>
                ` : ''}

                <div class="info-section">
                  <h4>Last Updated</h4>
                  <p>${new Date(result.last_updated).toLocaleString()}</p>
                </div>
              </div>
            </details>
          </div>
        </div>
      `;
    } else if (result.type === 'file') {
      const language = result.name ? getLanguageFromPath(result.name) : 'plaintext';
      const keyComponents = tryParseJSON(result.key_components, []);
      const dependencies = tryParseJSON(result.dependencies, []);

      resultItem.innerHTML = `
        <div class="file-result">
          <div class="file-header">
            <h3>
              <svg class="file-icon" viewBox="0 0 16 16" width="16" height="16">
                <path d="M2 1.75C2 .784 2.784 0 3.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0 1 13.25 16h-9.5A1.75 1.75 0 0 1 2 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 0 0 .25-.25V6h-2.75A1.75 1.75 0 0 1 9 4.25V1.5Zm6.75.062V4.25c0 .138.112.25.25.25h2.688l-.011-.013-2.914-2.914-.013-.011Z"></path>
              </svg>
              ${escapeHtml(result.name || 'Unnamed File')}
            </h3>
            <span class="similarity-score">
              <svg class="similarity-icon" viewBox="0 0 16 16" width="16" height="16">
                <path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path>
                <path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z"></path>
              </svg>
              ${(result.similarity * 100).toFixed(2)}% match
            </span>
          </div>

          <div class="file-metadata">
            <span class="language">
              <span class="language-dot" style="background-color: ${getLanguageColor(result.primary_language)}"></span>
              ${escapeHtml(result.primary_language || 'Unknown')}
            </span>
            <span class="repo-reference">Repository ID: ${result.repo_id}</span>
          </div>

          ${result.description ? `
            <div class="file-description">
              ${escapeHtml(result.description)}
            </div>
          ` : ''}

          <div class="file-details">
            ${keyComponents.length > 0 ? `
              <div class="components-section">
                <h4>Key Components</h4>
                <ul class="component-list">
                  ${keyComponents.map(component => `
                    <li>${escapeHtml(component)}</li>
                  `).join('')}
                </ul>
              </div>
            ` : ''}

            ${dependencies.length > 0 ? `
              <div class="dependencies-section">
                <h4>Dependencies</h4>
                <div class="tags">
                  ${dependencies.map(dep => `
                    <span class="tag dependency">${escapeHtml(dep)}</span>
                  `).join('')}
                </div>
              </div>
            ` : ''}
          </div>

          <div class="file-actions">
            <button onclick="toggleFileSelection('${result.id}', '${escapeHtml(result.name || '')}')">
              ${selectedFiles.has(result.id.toString()) ? 'Remove from Selection' : 'Add to Selection'}
            </button>
          </div>

          <details class="code-section">
            <summary>View Code</summary>
            <pre class="line-numbers"><code class="language-${language}">${escapeHtml(result.content || '')}</code></pre>
          </details>
        </div>
      `;
    }

    resultsContainer.appendChild(resultItem);
  });

  // Manually trigger Prism highlighting
  if (typeof Prism !== 'undefined') {
    Prism.highlightAll();
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
