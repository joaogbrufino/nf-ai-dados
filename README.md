# 📊 Sistema de Processamento de Notas Fiscais com IA

Sistema completo para processamento inteligente de notas fiscais utilizando Inteligência Artificial (Gemini AI) com recursos de extração de dados, classificação automática e busca inteligente com RAG (Retrieval Augmented Generation).

## 🚀 Funcionalidades

### 1. **Processamento de Notas Fiscais**
- ✅ Upload de PDFs de notas fiscais
- ✅ Extração automática de dados usando Gemini AI
- ✅ Identificação de emitente, destinatário, itens e valores
- ✅ Classificação automática de despesas

### 2. **Busca Inteligente (RAG)**
- ✅ **RAG Simples**: Busca por palavras-chave
- ✅ **RAG com Embeddings**: Busca semântica avançada
- ✅ **RAG Híbrido (Agent3)**: Combina ambas abordagens com filtros inteligentes
- ✅ Geração de respostas elaboradas com LLM
- ✅ Interface web intuitiva

### 3. **Gestão de Dados**
- ✅ CRUD completo de pessoas (fornecedores/clientes)
- ✅ Gerenciamento de movimentos de contas
- ✅ Controle de classificações e categorias
- ✅ Painel administrativo

### 4. **Agente IA Secundário**
- ✅ Análise de fluxo de caixa
- ✅ Classificação automática de despesas
- ✅ Relatórios por categorias
- ✅ Previsão de fluxo de caixa

---

## 📋 Tecnologias Utilizadas

### Backend
- **Python 3.10+**
- **Flask 3.0** - Framework web
- **SQLAlchemy 2.0** - ORM para banco de dados
- **PostgreSQL 15** - Banco de dados relacional
- **Google Gemini AI** - Inteligência Artificial
- **PyPDF2** - Processamento de PDFs

### Frontend
- **HTML5** / **CSS3** / **JavaScript**
- **Nginx** - Servidor web (produção)

### DevOps
- **Docker** & **Docker Compose**
- **Git** - Controle de versão

---

## 🏗️ Arquitetura do Sistema

```
┌─────────────────────────────────────────────────┐
│              Frontend (Nginx)                   │
│  - Interface de Upload                          │
│  - Sistema RAG                                  │
│  - Painel Admin                                 │
└──────────────────┬──────────────────────────────┘
                   │
                   v
┌─────────────────────────────────────────────────┐
│            Backend (Flask)                      │
│  - API REST                                     │
│  - Processamento IA (Gemini)                    │
│  - Sistema RAG (3 métodos)                      │
│  - Agent3 (Motor RAG Híbrido)                   │
└──────────────────┬──────────────────────────────┘
                   │
                   v
┌─────────────────────────────────────────────────┐
│        Banco de Dados (PostgreSQL)              │
│  - pessoas                                      │
│  - classificacao                                │
│  - movimento_contas                             │
│  - parcelas_contas                              │
│  - MovimentoContas_has_Classificacao            │
└─────────────────────────────────────────────────┘
```

---

## 🔧 Instalação e Configuração

### Opção 1: Docker (Recomendado)

#### Pré-requisitos
- Docker 20.10+
- Docker Compose 2.0+

#### Passo a Passo

1. **Clone o repositório**
```bash
git clone <url-do-repositorio>
cd nf-ai-dados
```

2. **Configure as variáveis de ambiente**
```bash
cat > .env << 'EOF'
# Configurações do Banco de dados
DATABASE_URL=postgresql://postgres:postgres@db:5432/nf_ai
DB_HOST=db
DB_PORT=5432
DB_NAME=nf_ai
DB_USER=postgres
DB_PASSWORD=postgres

# Chave da API Gemini (OBRIGATÓRIO - substitua pela sua chave)
GEMINI_API_KEY=sua_chave_aqui

# Configurações da aplicação
FLASK_ENV=development
FLASK_DEBUG=True
EOF
```

3. **Construa e inicie os containers**
```bash
# Construir as imagens
docker-compose build

# Iniciar todos os serviços
docker-compose up -d

# Verificar status
docker-compose ps

# Ver logs
docker-compose logs -f
```

4. **Acesse o sistema**
- **Frontend**: http://localhost
- **Backend**: http://localhost:5000
- **Sistema RAG**: http://localhost:5000/rag
- **Painel Admin**: http://localhost:5000/admin

---

### Opção 2: Instalação Local

#### Pré-requisitos
- Python 3.10 ou superior
- PostgreSQL 15 ou superior
- pip (gerenciador de pacotes Python)

#### Passo a Passo

1. **Clone o repositório**
```bash
git clone <url-do-repositorio>
cd nf-ai-dados
```

2. **Configure o PostgreSQL**
```bash
# Iniciar o serviço
sudo service postgresql start

# Criar o banco de dados
sudo -u postgres psql
CREATE DATABASE nf_ai_dados;
ALTER USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE nf_ai_dados TO postgres;
\q

# Executar o schema SQL
sudo -u postgres psql -d nf_ai_dados < database_schema.sql
```

3. **Configure o ambiente Python**
```bash
# Criar ambiente virtual
python3 -m venv venv

# Ativar ambiente virtual
source venv/bin/activate

# Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt
```

4. **Configure as variáveis de ambiente**
```bash
cat > .env << 'EOF'
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/nf_ai_dados
DB_HOST=localhost
DB_PORT=5432
DB_NAME=nf_ai_dados
DB_USER=postgres
DB_PASSWORD=postgres
GEMINI_API_KEY=sua_chave_aqui
FLASK_ENV=development
FLASK_DEBUG=True
EOF
```

5. **Execute a aplicação**
```bash
python app.py
```

6. **Acesse o sistema**
- **Sistema**: http://localhost:5000
- **Sistema RAG**: http://localhost:5000/rag
- **Painel Admin**: http://localhost:5000/admin

---

## 📖 Como Usar

### 1. Upload de Notas Fiscais

1. Acesse http://localhost:5000
2. Clique em "Escolher arquivo" e selecione um PDF de nota fiscal
3. Clique em "Processar PDF"
4. O sistema irá extrair automaticamente:
   - Dados do emitente (razão social, CNPJ, endereço)
   - Dados do destinatário
   - Informações da nota fiscal (número, série, data)
   - Itens e valores
   - Classificação automática da despesa
5. Revise os dados e clique em "Salvar no Banco de Dados"

### 2. Busca Inteligente (RAG)

1. Acesse http://localhost:5000/rag
2. Digite sua pergunta no campo de texto, por exemplo:
   - "Quais despesas maiores do mês atual?"
   - "Mostre parcelas vencendo esta semana"
   - "Qual fornecedor tem mais movimentos?"
3. Escolha o método de busca:
   - **Híbrido (Agent3)**: Recomendado - combina filtros inteligentes
   - **RAG Simples**: Rápido - busca por palavras-chave
   - **RAG Embeddings**: Avançado - busca semântica
4. Clique em "Buscar Resposta"
5. Veja a resposta elaborada pela IA e o contexto recuperado

### 3. Painel Administrativo

1. Acesse http://localhost:5000/admin
2. Clique nas abas para visualizar:
   - **Pessoas**: Fornecedores e clientes cadastrados
   - **Movimentações**: Notas fiscais e movimentos
   - **Classificações**: Categorias de despesas e receitas
3. Use os botões de ação para editar ou inativar registros

---

## 🔍 Exemplos de Queries RAG

### Filtros Temporais
```
"Despesas do mês atual"
"Movimentos do último trimestre"
"Parcelas vencendo esta semana"
"Notas fiscais entre 01/10/2024 e 31/10/2024"
```

### Filtros de Valor
```
"Despesas acima de 5000"
"Movimentos menor que 1000"
"Parcelas até 500"
```

### Por Classificação
```
"Movimentos da classificação MANUTENÇÃO E OPERAÇÃO"
"Despesas de INSUMOS AGRÍCOLAS"
"Receitas de VENDAS"
```

### Por Fornecedor/Cliente
```
"Despesas do fornecedor ACME Ltda"
"Movimentos da empresa XYZ"
```

### Analíticas
```
"Quais fornecedores tiveram maiores despesas?"
"Resumo das despesas por categoria"
"Top 5 notas fiscais por valor"
```

---

## 🌐 Endpoints da API

### Processamento de Notas Fiscais
```bash
POST /upload
Content-Type: multipart/form-data

# Resposta
{
  "nota_fiscal": {...},
  "emitente": {...},
  "remetente": {...},
  "itens": {...},
  "classificacoes": ["..."],
  "validacoes": {...}
}
```

### Busca RAG
```bash
# RAG Híbrido
POST /rag/query
Content-Type: application/json
{"pergunta": "Quais despesas maiores do mês atual?"}

# RAG Simples
POST /rag/query-simples
Content-Type: application/json
{"pergunta": "Fornecedor ACME"}

# RAG Embeddings
POST /rag/query-embeddings
Content-Type: application/json
{"pergunta": "Custos com manutenção"}
```

### Gestão de Dados
```bash
# Listar pessoas
GET /pessoas

# Criar pessoa
POST /pessoas
Content-Type: application/json
{
  "tipo": "FORNECEDOR",
  "razaosocial": "Empresa XYZ",
  "documento": "12.345.678/0001-90",
  "fantasia": "XYZ",
  "status": "ATIVO"
}

# Listar movimentos
GET /movimentos

# Listar classificações
GET /classificacoes
```

---

## 📊 Estrutura do Banco de Dados

### Tabelas Principais

#### `pessoas`
- Armazena fornecedores e clientes
- Campos: idPessoas, tipo, razaosocial, fantasia, documento, status

#### `classificacao`
- Categorias de despesas e receitas
- Campos: idClassificacao, tipo, descricao, status

#### `movimento_contas`
- Notas fiscais e movimentações financeiras
- Campos: idMovimentoContas, tipo, numeronotafiscal, dataemissao, descricao, status, valortotal, etc.

#### `parcelas_contas`
- Parcelas de pagamento
- Campos: idParcelasContas, identificacao, datavencimento, valorparcela, valorpago, valorsaldo, statusparcela

#### `MovimentoContas_has_Classificacao`
- Relacionamento N:N entre movimentos e classificações

---

## 🛠️ Comandos Úteis

### Docker

```bash
# Parar todos os containers
docker-compose stop

# Reiniciar os containers
docker-compose restart

# Ver logs
docker-compose logs -f backend

# Acessar container do backend
docker-compose exec backend bash

# Acessar PostgreSQL
docker-compose exec db psql -U postgres -d nf_ai

# Remover tudo e reconstruir
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Banco de Dados

```bash
# Conectar ao PostgreSQL localmente
psql -h localhost -U postgres -d nf_ai_dados

# Verificar tabelas
\dt

# Ver classificações
SELECT * FROM classificacao;

# Ver pessoas
SELECT * FROM pessoas;

# Contar registros
SELECT COUNT(*) FROM movimento_contas;
```

---

## 🐛 Troubleshooting

### Erro: "Não foi possível conectar ao banco de dados"

**Solução:**
```bash
# Verificar se PostgreSQL está rodando
sudo service postgresql status
sudo service postgresql start

# Verificar conexão
psql -h localhost -U postgres -d nf_ai_dados -c "SELECT 1"
```

### Erro: "GEMINI_API_KEY não configurada"

**Solução:**
```bash
# Adicionar chave no .env
echo "GEMINI_API_KEY=sua_chave_aqui" >> .env

# Reiniciar aplicação
docker-compose restart backend  # Docker
# ou
python app.py  # Local
```

### Erro: "Porta já em uso"

**Solução:**
```bash
# Ver o que está usando a porta 5000
sudo lsof -i :5000

# Matar o processo
kill -9 <PID>
```

---

## 📚 Documentação Adicional

- [Documentação RAG Completa](RAG_DOCUMENTATION.md) *(se existir)*
- [Guia de Execução Detalhado](GUIA_EXECUCAO.md) *(se existir)*

---

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

---

## 📝 Licença

Este projeto está sob a licença MIT.

---

## 👨‍💻 Autor

Sistema desenvolvido para processamento inteligente de notas fiscais e gestão financeira.

**Versão:** 2.0  
**Data:** Novembro 2024

---

## 🎯 Roadmap

- [x] Processamento de PDFs com IA
- [x] Extração de dados de notas fiscais
- [x] Sistema RAG com 3 métodos
- [x] Painel administrativo
- [x] CRUD completo
- [x] Agente IA secundário
- [ ] Autenticação e autorização
- [ ] Dashboard de analytics
- [ ] Exportação de relatórios
- [ ] API REST documentada (Swagger)
- [ ] Testes automatizados
- [ ] Deploy em produção

---

## ❓ FAQ

### Como obter uma chave da API Gemini?
1. Acesse https://ai.google.dev/
2. Faça login com sua conta Google
3. Vá em "Get API Key"
4. Copie a chave e adicione no arquivo `.env`

### O sistema funciona offline?
Não. O sistema requer conexão com a internet para acessar a API do Gemini para processamento de IA.

### Posso usar outra IA além do Gemini?
Sim, mas será necessário modificar o código. O sistema foi desenvolvido especificamente para a API do Gemini, mas pode ser adaptado para outras LLMs como OpenAI GPT, Claude, etc.

### Como faço backup do banco de dados?
```bash
# Docker
docker-compose exec db pg_dump -U postgres nf_ai > backup.sql

# Local
pg_dump -U postgres nf_ai_dados > backup.sql
```

### Como restaurar um backup?
```bash
# Docker
cat backup.sql | docker-compose exec -T db psql -U postgres -d nf_ai

# Local
psql -U postgres -d nf_ai_dados < backup.sql
```

---

## 📞 Suporte

Para problemas ou dúvidas:
1. Verifique os logs: `docker-compose logs -f` ou `tail -f app.log`
2. Consulte a seção de Troubleshooting
3. Abra uma issue no repositório

