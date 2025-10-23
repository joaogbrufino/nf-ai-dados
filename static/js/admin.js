// Configurações das tabelas
const tabelasConfig = {
    pessoas: {
        titulo: 'Pessoas',
        endpoint: '/admin/api/pessoas',
        colunas: ['ID', 'Nome', 'CPF/CNPJ', 'Tipo', 'Fantasia', 'Status']
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
        .then(response => response.json())
        .then(data => {
            esconderLoading();
            if (data.erro) {
                mostrarErro(data.erro);
            } else {
                renderizarTabela(data, config);
            }
        })
        .catch(error => {
            esconderLoading();
            mostrarErro('Erro ao carregar dados: ' + error.message);
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