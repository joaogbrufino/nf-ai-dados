// JavaScript Simples - Apenas JSON
document.addEventListener('DOMContentLoaded', function() {
    // Elementos DOM
    const uploadArea = document.getElementById('uploadArea');
    const uploadBtn = document.getElementById('uploadBtn');
    const fileInput = document.getElementById('fileInput');
    const fileInfo = document.getElementById('fileInfo');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const uploadSection = document.getElementById('uploadSection');
    const loadingSection = document.getElementById('loadingSection');
    const resultsSection = document.getElementById('resultsSection');
    const errorSection = document.getElementById('errorSection');
    const jsonFrame = document.getElementById('jsonFrame');
    const errorMessage = document.getElementById('errorMessage');

    let selectedFile = null;

    // Event Listeners
    // Upload button click
    if (uploadBtn) {
        uploadBtn.addEventListener('click', () => fileInput.click());
    }
    
    // File input change
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }
    
    // Analyze button click
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', analyzeFile);
    }
    
    // Drag and drop
    if (uploadArea) {
        uploadArea.addEventListener('dragover', handleDragOver);
        uploadArea.addEventListener('drop', handleDrop);
    }

    function handleFileSelect(event) {
        const file = event.target.files[0];
        if (file && file.type === 'application/pdf') {
            selectedFile = file;
            showFileInfo(file);
            analyzeBtn.disabled = false;
        } else {
            showError('Por favor, selecione um arquivo PDF válido.');
        }
    }

    function handleDragOver(event) {
        event.preventDefault();
    }

    function handleDrop(event) {
        event.preventDefault();
        const files = event.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            if (file.type === 'application/pdf') {
                selectedFile = file;
                fileInput.files = files;
                showFileInfo(file);
                analyzeBtn.disabled = false;
            } else {
                showError('Por favor, selecione um arquivo PDF válido.');
            }
        }
    }

    function showFileInfo(file) {
        fileInfo.innerHTML = `<p>Arquivo selecionado: ${file.name}</p>`;
        fileInfo.style.display = 'block';
    }

    function analyzeFile() {
        if (!selectedFile) return;
        
        showSection('loading');
        
        const formData = new FormData();
        formData.append('pdf', selectedFile);
        
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError(data.error);
            } else {
                showResults(data);
            }
        })
        .catch(error => {
            showError('Erro ao processar arquivo: ' + error.message);
        });
    }

    function showResults(data) {
        jsonFrame.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
        showSection('results');
    }

    function showError(message) {
        errorMessage.textContent = message;
        showSection('error');
    }

    function showSection(section) {
        // Hide all sections
        uploadSection.style.display = 'none';
        loadingSection.style.display = 'none';
        resultsSection.style.display = 'none';
        errorSection.style.display = 'none';
        
        // Show selected section
        switch(section) {
            case 'upload':
                uploadSection.style.display = 'block';
                break;
            case 'loading':
                loadingSection.style.display = 'block';
                break;
            case 'results':
                resultsSection.style.display = 'block';
                break;
            case 'error':
                errorSection.style.display = 'block';
                break;
        }
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
});