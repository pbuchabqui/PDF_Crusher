const uploadArea = document.getElementById('uploadArea');
const pdfInput = document.getElementById('pdfInput');
const uploadForm = document.getElementById('uploadForm');
const submitBtn = document.getElementById('submitBtn');
const useGroqCheckbox = document.getElementById('useGroq');
const groqPanel = document.getElementById('groqPanel');
const groqKey = document.getElementById('groqKey');
const status = document.getElementById('status');
const results = document.getElementById('results');
const fileList = document.getElementById('fileList');
const downloadZipBtn = document.getElementById('downloadZipBtn');

let currentJobId = null;

// Toggle Groq panel
useGroqCheckbox.addEventListener('change', () => {
    groqPanel.classList.toggle('show', useGroqCheckbox.checked);
});

// Upload area interactions
uploadArea.addEventListener('click', () => pdfInput.click());
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});
uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});
uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        pdfInput.files = files;
        updateFileName();
    }
});

pdfInput.addEventListener('change', updateFileName);

function updateFileName() {
    if (pdfInput.files.length > 0) {
        const fileName = pdfInput.files[0].name;
        const uploadText = uploadArea.querySelector('.upload-text');
        uploadText.textContent = `✓ ${fileName} selecionado`;
    }
}

// Form submission
uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!pdfInput.files.length) {
        showStatus('Selecione um PDF', 'error');
        return;
    }

    submitBtn.disabled = true;
    showStatus('⏳ Processando PDF...', 'loading');
    results.classList.remove('show');

    const formData = new FormData();
    formData.append('pdf', pdfInput.files[0]);
    formData.append('use_groq', useGroqCheckbox.checked);
    if (useGroqCheckbox.checked && groqKey.value) {
        formData.append('groq_api_key', groqKey.value);
    }

    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
            showStatus(`Erro: ${data.error || data.detail || 'Erro desconhecido'}`, 'error');
            submitBtn.disabled = false;
            return;
        }

        currentJobId = data.job_id;
        showStatus('✓ PDF processado com sucesso!', 'success');
        displayResults(data);

    } catch (error) {
        showStatus(`Erro na requisição: ${error.message}`, 'error');
    } finally {
        submitBtn.disabled = false;
    }
});

function showStatus(message, type) {
    status.textContent = message;
    status.className = `status show ${type}`;
    if (type === 'loading') {
        status.innerHTML = `<span class="spinner"></span>${message}`;
    }
}

function displayResults(data) {
    fileList.innerHTML = '';

    const allFiles = [
        ...data.claude_files.map(f => ({ path: f, type: 'claude' })),
        ...data.audit_files.map(f => ({ path: f, type: 'audit' })),
    ];

    allFiles.forEach(file => {
        const item = document.createElement('div');
        item.className = 'file-item';
        const filename = file.path.split('/').pop();
        item.innerHTML = `
            <span class="file-name">${file.path}</span>
            <button type="button" class="btn-download" onclick="downloadFile('${file.path}')">
                ⬇️ Baixar
            </button>
        `;
        fileList.appendChild(item);
    });

    downloadZipBtn.onclick = downloadZip;
    results.classList.add('show');
}

function downloadFile(filepath) {
    if (!currentJobId) return;
    const url = `/api/files/${currentJobId}/${filepath}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = filepath.split('/').pop();
    a.click();
}

function downloadZip() {
    if (!currentJobId) return;
    const url = `/api/jobs/${currentJobId}/zip`;
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentJobId}.zip`;
    a.click();
}
