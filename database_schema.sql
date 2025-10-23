-- Script de criação do banco de dados PostgreSQL
-- Baseado na modelagem fornecida

-- Criação da tabela pessoas
CREATE TABLE IF NOT EXISTS pessoas (
    "idPessoas" SERIAL PRIMARY KEY,
    tipo VARCHAR(45) NOT NULL,
    razaosocial VARCHAR(150) NOT NULL,
    fantasia VARCHAR(150),
    documento VARCHAR(45) NOT NULL,
    status VARCHAR(45) DEFAULT 'ATIVO'
);

-- Criação da tabela classificacao
CREATE TABLE IF NOT EXISTS classificacao (
    "idClassificacao" SERIAL PRIMARY KEY,
    tipo VARCHAR(45) NOT NULL,
    descricao VARCHAR(300) NOT NULL,
    status VARCHAR(45) DEFAULT 'ATIVO'
);

-- Criação da tabela parcelas_contas
CREATE TABLE IF NOT EXISTS parcelas_contas (
    "idParcelasContas" SERIAL PRIMARY KEY,
    identificacao VARCHAR(45) NOT NULL,
    datavencimento DATE NOT NULL,
    valorparcela DECIMAL(10,2) NOT NULL,
    valorpago DECIMAL(10,2) DEFAULT 0.00,
    valorsaldo DECIMAL(10,2) NOT NULL,
    statusparcela VARCHAR(45) DEFAULT 'PENDENTE'
);

-- Criação da tabela movimento_contas
CREATE TABLE IF NOT EXISTS movimento_contas (
    "idMovimentoContas" SERIAL PRIMARY KEY,
    tipo VARCHAR(45) NOT NULL,
    numeronotafiscal VARCHAR(45),
    dataemissao DATE NOT NULL,
    descricao VARCHAR(300),
    status VARCHAR(45) DEFAULT 'ATIVO',
    valortotal DECIMAL(10,2) NOT NULL,
    "Pessoas_idFornecedorCliente" INT NOT NULL,
    "Pessoas_idFaturado" INT NOT NULL,
    FOREIGN KEY ("Pessoas_idFornecedorCliente") REFERENCES pessoas ("idPessoas"),
    FOREIGN KEY ("Pessoas_idFaturado") REFERENCES pessoas ("idPessoas")
);

-- Criação da tabela de relacionamento MovimentoContas_has_Classificacao
CREATE TABLE IF NOT EXISTS "MovimentoContas_has_Classificacao" (
    "MovimentoContas_idMovimentoContas" INT NOT NULL,
    "Classificacao_idClassificacao" INT NOT NULL,
    PRIMARY KEY ("MovimentoContas_idMovimentoContas", "Classificacao_idClassificacao"),
    FOREIGN KEY ("MovimentoContas_idMovimentoContas") REFERENCES movimento_contas("idMovimentoContas") ON DELETE CASCADE,
    FOREIGN KEY ("Classificacao_idClassificacao") REFERENCES classificacao("idClassificacao") ON DELETE CASCADE
);

-- Criação de índices para melhor performance
CREATE INDEX IF NOT EXISTS idx_pessoas_documento ON pessoas(documento);
CREATE INDEX IF NOT EXISTS idx_pessoas_tipo ON pessoas(tipo);
CREATE INDEX IF NOT EXISTS idx_movimento_dataemissao ON movimento_contas(dataemissao);
CREATE INDEX IF NOT EXISTS idx_movimento_tipo ON movimento_contas(tipo);
CREATE INDEX IF NOT EXISTS idx_parcelas_datavencimento ON parcelas_contas(datavencimento);
CREATE INDEX IF NOT EXISTS idx_parcelas_status ON parcelas_contas(statusparcela);

-- Inserção das classificações padrão baseadas nas categorias existentes
INSERT INTO classificacao (tipo, descricao, status) VALUES
('DESPESA', 'INSUMOS AGRÍCOLAS', 'ATIVO'),
('DESPESA', 'MANUTENÇÃO E OPERAÇÃO', 'ATIVO'),
('DESPESA', 'RECURSOS HUMANOS', 'ATIVO'),
('DESPESA', 'SERVIÇOS OPERACIONAIS', 'ATIVO'),
('DESPESA', 'INFRAESTRUTURA E UTILIDADES', 'ATIVO'),
('DESPESA', 'ADMINISTRATIVAS', 'ATIVO'),
('DESPESA', 'SEGUROS E PROTEÇÃO', 'ATIVO'),
('DESPESA', 'IMPOSTOS E TAXAS', 'ATIVO'),
('DESPESA', 'INVESTIMENTOS', 'ATIVO'),
('DESPESA', 'OUTROS', 'ATIVO'),
('RECEITA', 'VENDAS', 'ATIVO'),
('RECEITA', 'SERVIÇOS', 'ATIVO'),
('RECEITA', 'OUTRAS RECEITAS', 'ATIVO')
ON CONFLICT DO NOTHING;