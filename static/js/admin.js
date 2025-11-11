// Configurações das tabelas
const tabelasConfig = {
    pessoas: {
        titulo: 'Pessoas',
        endpoint: '/admin/api/pessoas',
        colunas: ['ID', 'Nome', 'CPF/CNPJ', 'Tipo', 'Fantasia', 'Status', 'Ações']
    },
    movimentos: {
        titulo: 'Movimentações',
        endpoint: '/admin/api/movimentos',
        colunas: ['ID', 'Pessoa', 'Classificação', 'Descrição', 'Valor', 'Tipo', 'Data Movimento', 'Data Criação']
    },
    classificacoes: {
        titulo: 'Classificações',
        endpoint: '/admin/api/classificacoes',
        colunas: ['ID', 'Nome', 'Descrição', 'Data Criação']
    }
};

// Função para carregar tabela
function carregarTabela(tipo) {
    const config = tabelasConfig[tipo];
    if (!config) return;

    mostrarLoading();
    esconderErro();

    fetch(config.endpoint)
        .then(response => {
            if (!response.ok) {
                throw new Error('Falha ao carregar (' + response.status + ')');
            }
            return response.json();
        })
        .then(data => {
            esconderLoading();
            if (data && data.erro) {
                mostrarErro('Não foi possível carregar. Tente novamente.');
            } else {
                renderizarTabela(data, config);
            }
        })
        .catch(error => {
            esconderLoading();
            console.error('Erro ao carregar dados:', error);
            mostrarErro('Não foi possível carregar. Tente novamente.');
        });
}

// Função para renderizar tabela
function renderizarTabela(dados, config) {
    const container = document.getElementById('table-container');
    
    let html = '<h2>' + config.titulo + '</h2>';
    
    if (dados.length === 0) {
        html += '<p>Nenhum registro encontrado.</p>';
    } else {
        html += '<table>';
        html += '<thead><tr>';
        
        // Cabeçalhos
        config.colunas.forEach(coluna => {
            html += '<th>' + coluna + '</th>';
        });
        html += '</tr></thead>';
        
        // Dados
        html += '<tbody>';
        dados.forEach(item => {
            html += '<tr>';
            html += '<td>' + item.id + '</td>';
            
            if (config.titulo === 'Pessoas') {
                html += '<td>' + item.nome + '</td>';
                html += '<td>' + item.cpf_cnpj + '</td>';
                html += '<td>' + item.tipo + '</td>';
                html += '<td>' + item.endereco + '</td>';
                html += '<td>' + item.status + '</td>';
                html += '<td class="acoes">';
                html += '<button class="btn-editar" onclick="editarPessoa(' + item.id + ')" title="Editar">✏️</button>';
                html += '<button class="btn-inativar" onclick="inativarPessoa(' + item.id + ', \'' + item.status + '\')" title="' + (item.status === 'Ativo' ? 'Inativar' : 'Ativar') + '">';
                html += item.status === 'Ativo' ? '🔓' : '🔒';
                html += '</button>';
                html += '</td>';
            } else if (config.titulo === 'Movimentações') {
                html += '<td>' + item.pessoa_nome + '</td>';
                html += '<td>' + item.classificacao_nome + '</td>';
                html += '<td>' + item.descricao + '</td>';
                html += '<td>R$ ' + formatarMoeda(item.valor) + '</td>';
                html += '<td>' + item.tipo_movimento + '</td>';
                html += '<td>' + item.data_movimento + '</td>';
                html += '<td>' + item.data_criacao + '</td>';
            } else if (config.titulo === 'Classificações') {
                html += '<td>' + item.nome + '</td>';
                html += '<td>' + item.descricao + '</td>';
                html += '<td>' + item.data_criacao + '</td>';
            }
            
            html += '</tr>';
        });
        html += '</tbody>';
        html += '</table>';
    }
    
    container.innerHTML = html;
}

// Funções auxiliares
function mostrarLoading() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('table-container').innerHTML = '';
}

function esconderLoading() {
    document.getElementById('loading').style.display = 'none';
}

function mostrarErro(mensagem) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = mensagem;
    errorDiv.style.display = 'block';
}

function esconderErro() {
    document.getElementById('error').style.display = 'none';
}

function formatarMoeda(valor) {
    return parseFloat(valor).toFixed(2).replace('.', ',');
}

// Funções para edição e inativação
function editarPessoa(id) {
    // Buscar dados da pessoa
    fetch(`/admin/api/pessoas/${id}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                mostrarModalEdicao(data.pessoa);
            } else {
                mostrarErro('Erro ao carregar dados da pessoa');
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            mostrarErro('Erro ao carregar dados da pessoa');
        });
}

function inativarPessoa(id, statusAtual) {
    const novoStatus = statusAtual === 'Ativo' ? 'Inativo' : 'Ativo';
    const acao = novoStatus === 'Ativo' ? 'ativar' : 'inativar';
    
    if (confirm(`Tem certeza que deseja ${acao} este registro?`)) {
        fetch(`/admin/api/pessoas/${id}/status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ status: novoStatus })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                carregarTabela('pessoas'); // Recarregar tabela
            } else {
                mostrarErro('Erro ao alterar status da pessoa');
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            mostrarErro('Erro ao alterar status da pessoa');
        });
    }
}

function mostrarModalEdicao(pessoa) {
    // Criar modal de edição
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <span class="close" onclick="fecharModal()">&times;</span>
            <h2>Editar Pessoa</h2>
            <form id="form-edicao">
                <div class="form-group">
                    <label for="razaosocial">Razão Social:</label>
                    <input type="text" id="razaosocial" name="razaosocial" value="${pessoa.razaosocial}" required>
                </div>
                <div class="form-group">
                    <label for="documento">CPF/CNPJ:</label>
                    <input type="text" id="documento" name="documento" value="${pessoa.documento}" required>
                </div>
                <div class="form-group">
                    <label for="tipo">Tipo (Cliente/Fornecedor):</label>
                    <select id="tipo" name="tipo" required>
                        <option value="CLIENTE" ${pessoa.tipo === 'CLIENTE' ? 'selected' : ''}>Cliente</option>
                        <option value="FORNECEDOR" ${pessoa.tipo === 'FORNECEDOR' ? 'selected' : ''}>Fornecedor</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="fantasia">Fantasia:</label>
                    <input type="text" id="fantasia" name="fantasia" value="${pessoa.fantasia || ''}">
                </div>
                <div class="form-actions">
                    <button type="button" onclick="fecharModal()">Cancelar</button>
                    <button type="submit">Salvar</button>
                </div>
            </form>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Adicionar evento de submit
    document.getElementById('form-edicao').addEventListener('submit', function(e) {
        e.preventDefault();
        salvarEdicao(pessoa.id);
    });
}

function salvarEdicao(id) {
    const form = document.getElementById('form-edicao');
    const formData = new FormData(form);
    const dados = Object.fromEntries(formData);
    
    fetch(`/admin/api/pessoas/${id}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(dados)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            fecharModal();
            carregarTabela('pessoas'); // Recarregar tabela
        } else {
            mostrarErro('Erro ao salvar alterações');
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        mostrarErro('Erro ao salvar alterações');
    });
}

function fecharModal() {
    const modal = document.querySelector('.modal');
    if (modal) {
        modal.remove();
    }
}