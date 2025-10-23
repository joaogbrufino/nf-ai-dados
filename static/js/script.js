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
    const saveToDatabaseBtn = document.getElementById('saveToDatabaseBtn');
    const saveSection = document.getElementById('saveSection');
    const saveStatus = document.getElementById('saveStatus');

    let selectedFile = null;
    let currentData = null; // Armazenar dados atuais para salvamento

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
    
    // Save to database button click
    if (saveToDatabaseBtn) {
        saveToDatabaseBtn.addEventListener('click', saveToDatabase);
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
        // Armazenar dados para possível salvamento
        currentData = data;
        
        // Separar dados de validação dos dados principais
        const validacoes = data.validacoes;
        const dadosParaExibir = {...data};
        delete dadosParaExibir.validacoes; // Remove validações do JSON principal
        delete dadosParaExibir.dados_originais; // Remove dados originais do JSON exibido
        
        // Exibir JSON filtrado
        jsonFrame.innerHTML = `<pre>${JSON.stringify(dadosParaExibir, null, 2)}</pre>`;
        
        // Exibir mensagens de validação se existirem dados duplicados
        if (validacoes) {
            showValidationMessages(validacoes);
        }
        
        // Mostrar botão de salvamento se não for nota fiscal duplicada
        if (validacoes && !validacoes.nota_fiscal_existe) {
            saveSection.style.display = 'block';
            saveToDatabaseBtn.disabled = false;
            saveStatus.innerHTML = '';
            saveStatus.className = 'save-status';
            
            // Debug: verificar dados_novos
            console.log('Dados novos recebidos:', validacoes.dados_novos);
            
            // Exibir dados novos que serão inseridos no banco
            showNewDataPreview(validacoes.dados_novos);
        } else {
            saveSection.style.display = 'none';
            // Ocultar frame de dados novos se não há salvamento
            document.getElementById('newDataPreview').style.display = 'none';
        }
        
        showSection('results');
    }

    function showValidationMessages(validacoes) {
        const validationMessages = document.getElementById('validationMessages');
        const validationContent = document.getElementById('validationContent');
        
        if (!validacoes || (!validacoes.emitente_existe && !validacoes.remetente_existe && !validacoes.nota_fiscal_existe)) {
            validationMessages.style.display = 'none';
            return;
        }
        
        let mensagens = [];
        
        if (validacoes.emitente_existe && validacoes.detalhes.emitente) {
            const emitente = validacoes.detalhes.emitente;
            mensagens.push(`<div class="validation-item">
                <strong>Emitente:</strong> ${emitente.razao_social} (${emitente.documento}) já existe no banco de dados (ID: ${emitente.id})
            </div>`);
        }
        
        if (validacoes.remetente_existe && validacoes.detalhes.remetente) {
            const remetente = validacoes.detalhes.remetente;
            mensagens.push(`<div class="validation-item">
                <strong>Remetente:</strong> ${remetente.razao_social} (${remetente.documento}) já existe no banco de dados (ID: ${remetente.id})
            </div>`);
        }
        
        if (validacoes.nota_fiscal_existe && validacoes.detalhes.nota_fiscal) {
            const nf = validacoes.detalhes.nota_fiscal;
            mensagens.push(`<div class="validation-item">
                <strong>Nota Fiscal:</strong> Número ${nf.numero} de ${nf.data_emissao} no valor de R$ ${nf.valor_total.toFixed(2)} já existe no banco de dados (ID: ${nf.id})
            </div>`);
        }
        
        // Verificar classificações existentes
        if (validacoes.classificacoes_existem && validacoes.classificacoes_existem.length > 0) {
            validacoes.classificacoes_existem.forEach(classificacao => {
                mensagens.push(`<div class="validation-item">
                    <strong>Classificação:</strong> "${classificacao.nome}" já existe no banco de dados (ID: ${classificacao.id})
                </div>`);
            });
        }
        
        // Verificar classificações criadas
        if (validacoes.classificacoes_criadas && validacoes.classificacoes_criadas.length > 0) {
            validacoes.classificacoes_criadas.forEach(classificacao => {
                mensagens.push(`<div class="validation-item validation-success">
                    <strong>Nova Classificação:</strong> "${classificacao.nome}" foi criada no banco de dados (ID: ${classificacao.id})
                </div>`);
            });
        }
        
        if (mensagens.length > 0) {
            validationContent.innerHTML = mensagens.join('');
            validationMessages.style.display = 'block';
        } else {
            validationMessages.style.display = 'none';
        }
    }

    function showError(message) {
        errorMessage.textContent = message;
        showSection('error');
    }

    function saveToDatabase() {
        if (!currentData) {
            showSaveStatus('Nenhum dado disponível para salvamento', 'error');
            return;
        }

        // Desabilitar botão durante o salvamento
        saveToDatabaseBtn.disabled = true;
        saveToDatabaseBtn.textContent = 'Salvando...';
        
        // Limpar status anterior
        saveStatus.innerHTML = '';
        saveStatus.className = 'save-status';

        fetch('/salvar-dados', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(currentData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.sucesso) {
                showSaveStatus(data.mensagem, 'success');
                saveToDatabaseBtn.textContent = 'Dados Salvos!';
            } else {
                showSaveStatus(data.erro || 'Erro ao salvar dados', 'error');
                saveToDatabaseBtn.disabled = false;
                saveToDatabaseBtn.textContent = 'Enviar para o Banco';
            }
        })
        .catch(error => {
            showSaveStatus('Erro de conexão: ' + error.message, 'error');
            saveToDatabaseBtn.disabled = false;
            saveToDatabaseBtn.textContent = 'Enviar para o Banco';
        });
    }

    function showSaveStatus(message, type) {
        saveStatus.innerHTML = message;
        saveStatus.className = `save-status ${type}`;
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

    function showNewDataPreview(dadosNovos) {
        const newDataPreview = document.getElementById('newDataPreview');
        const newDataFrame = document.getElementById('newDataFrame');
        
        console.log('showNewDataPreview chamada com:', dadosNovos);
        
        if (!dadosNovos || (!dadosNovos.emitente && !dadosNovos.remetente && !dadosNovos.nota_fiscal && (!dadosNovos.classificacoes_novas || dadosNovos.classificacoes_novas.length === 0))) {
            console.log('Nenhum dado novo encontrado, ocultando frame');
            newDataPreview.style.display = 'none';
            return;
        }
        
        let htmlContent = '';
        
        if (dadosNovos.emitente) {
            console.log('Adicionando emitente:', dadosNovos.emitente);
            htmlContent += `
                <div class="new-data-section">
                    <h4>Novo Emitente:</h4>
                    <div class="data-item">
                        <strong>Razão Social:</strong> ${dadosNovos.emitente.razao_social || 'N/A'}
                    </div>
                    <div class="data-item">
                        <strong>CNPJ:</strong> ${dadosNovos.emitente.cnpj || 'N/A'}
                    </div>
                    <div class="data-item">
                        <strong>Endereço:</strong> ${dadosNovos.emitente.endereco || 'N/A'}
                    </div>
                </div>
            `;
        }
        
        if (dadosNovos.remetente) {
            console.log('Adicionando remetente:', dadosNovos.remetente);
            htmlContent += `
                <div class="new-data-section">
                    <h4>Novo Remetente:</h4>
                    <div class="data-item">
                        <strong>Nome:</strong> ${dadosNovos.remetente.nome || 'N/A'}
                    </div>
                    <div class="data-item">
                        <strong>CPF/CNPJ:</strong> ${dadosNovos.remetente.cpf_ou_cnpj || 'N/A'}
                    </div>
                    <div class="data-item">
                        <strong>Endereço:</strong> ${dadosNovos.remetente.endereco || 'N/A'}
                    </div>
                </div>
            `;
        }
        
        if (dadosNovos.nota_fiscal) {
            console.log('Adicionando nota fiscal:', dadosNovos.nota_fiscal);
            htmlContent += `
                <div class="new-data-section">
                    <h4>Nova Nota Fiscal:</h4>
                    <div class="data-item">
                        <strong>Número:</strong> ${dadosNovos.nota_fiscal.numero || 'N/A'}
                    </div>
                    <div class="data-item">
                        <strong>Data de Emissão:</strong> ${dadosNovos.nota_fiscal.data_emissao || 'N/A'}
                    </div>
                    <div class="data-item">
                        <strong>Valor Total:</strong> R$ ${dadosNovos.nota_fiscal.valor_total ? parseFloat(dadosNovos.nota_fiscal.valor_total).toFixed(2) : '0,00'}
                    </div>
                    <div class="data-item">
                        <strong>Descrição:</strong> ${dadosNovos.nota_fiscal.descricao || 'N/A'}
                    </div>
                </div>
            `;
        }
        
        if (dadosNovos.classificacoes_novas && dadosNovos.classificacoes_novas.length > 0) {
            console.log('Adicionando classificações novas:', dadosNovos.classificacoes_novas);
            htmlContent += `
                <div class="new-data-section">
                    <h4>Novas Classificações:</h4>
            `;
            dadosNovos.classificacoes_novas.forEach(classificacao => {
                htmlContent += `
                    <div class="data-item">
                        <strong>Classificação:</strong> ${classificacao}
                    </div>
                `;
            });
            htmlContent += `</div>`;
        }
        
        if (htmlContent) {
            console.log('Exibindo frame com conteúdo:', htmlContent);
            newDataFrame.innerHTML = htmlContent;
            newDataPreview.style.display = 'block';
        } else {
            console.log('Nenhum conteúdo para exibir, ocultando frame');
            newDataPreview.style.display = 'none';
        }
    }
});