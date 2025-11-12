from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from google import genai
import PyPDF2
import json
import os
import time
import logging
from io import BytesIO
from datetime import datetime
import re
import math
from dotenv import load_dotenv
# Voltando para PostgreSQL conforme solicitado
from database import db, init_db, Pessoas, Classificacao, MovimentoContas, ParcelasContas
from agente_ia import AgenteIA
from agent3 import Agent3

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Para exibir no terminal
        logging.FileHandler('app.log')  # Para salvar em arquivo
    ]
)
logger = logging.getLogger(__name__)

# Configurações do banco de dados PostgreSQL
db_url = os.getenv('DATABASE_URL', 'postgresql+psycopg://postgres:postgres@localhost:5432/nf_ai_dados')
# Garantir uso do driver psycopg (psycopg3) mesmo se a URL vier sem o "+psycopg"
if db_url.startswith('postgresql://') and '+psycopg' not in db_url:
    db_url = db_url.replace('postgresql://', 'postgresql+psycopg://')
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300
}

# Configurar Gemini AI
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai_client = genai.Client(api_key=GEMINI_API_KEY)

# Inicializar banco de dados
init_db(app)

# Inicializar segundo agente IA
agente_ia = AgenteIA()


CATEGORIAS_DESPESAS = {
    "INSUMOS AGRÍCOLAS": ["sementes", "fertilizantes", "defensivos agrícolas", "corretivos", "soja", "milho", "npk"],
    "MANUTENÇÃO E OPERAÇÃO": ["combustíveis", "lubrificantes", "óleo diesel", "gasolina", "óleo lubrificante", "peças", "parafusos", "componentes mecânicos", "manutenção", "pneus", "filtros", "correias", "ferramentas", "utensílios", "diesel", "óleo", "trator"],
    "RECURSOS HUMANOS": ["mão de obra temporária", "salários", "encargos"],
    "SERVIÇOS OPERACIONAIS": ["frete", "transporte", "colheita terceirizada", "secagem", "armazenagem", "pulverização", "aplicação", "mercadorias"],
    "INFRAESTRUTURA E UTILIDADES": ["energia elétrica", "arrendamento de terras", "construções", "reformas", "materiais de construção", "material hidráulico", "cimento", "ferro"],
    "ADMINISTRATIVAS": ["honorários", "contábeis", "advocatícios", "agronômicos", "despesas bancárias", "financeiras"],
    "SEGUROS E PROTEÇÃO": ["seguro agrícola", "seguro de ativos", "seguro prestamista", "máquinas", "veículos"],
    "IMPOSTOS E TAXAS": ["ITR", "IPTU", "IPVA", "INCRA-CCIR"],
    "INVESTIMENTOS": ["aquisição de máquinas", "implementos", "aquisição de veículos", "aquisição de imóveis", "infraestrutura rural"],
    "Outros": []
}

def extrair_texto_pdf(arquivo_pdf):
    """Extrai texto do arquivo PDF"""
    try:
        pdf_reader = PyPDF2.PdfReader(arquivo_pdf)
        texto_completo = ""
        
        for pagina in pdf_reader.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        return texto_completo
    except Exception as e:
        return f"Erro ao extrair texto do PDF: {str(e)}"

def classificar_despesa(descricao_produtos):
    """Classifica a despesa com base na descrição dos produtos."""
    descricao_lower = descricao_produtos.lower()
    
    
    for categoria, palavras_chave in CATEGORIAS_DESPESAS.items():
        if categoria == "Outros":
            continue
        if any(palavra in descricao_lower for palavra in palavras_chave):
            return categoria
    
    return "Outros"

def verificar_dados_existentes(dados_extraidos):
    """Verifica se os dados já existem no banco de dados"""
    validacoes = {
        'emitente_existe': False,
        'remetente_existe': False,
        'nota_fiscal_existe': False,
        'classificacoes_existem': [],
        'classificacoes_novas': [],
        'detalhes': {},
        'dados_novos': {
            'emitente': None,
            'remetente': None,
            'nota_fiscal': None,
            'classificacoes_novas': []
        }
    }
    
    try:
        # Verificar emitente
        emitente_data = dados_extraidos.get('emitente', {})
        cnpj_emitente = emitente_data.get('cnpj', '')
        if cnpj_emitente:
            emitente_existente = Pessoas.query.filter_by(documento=cnpj_emitente).first()
            if emitente_existente:
                validacoes['emitente_existe'] = True
                validacoes['detalhes']['emitente'] = {
                    'id': emitente_existente.idPessoas,
                    'razao_social': emitente_existente.razaosocial,
                    'documento': emitente_existente.documento,
                    'tipo': emitente_existente.tipo
                }
        
        # Verificar remetente
        remetente_data = dados_extraidos.get('remetente', {})
        doc_remetente = remetente_data.get('cpf_ou_cnpj', '')
        if doc_remetente:
            remetente_existente = Pessoas.query.filter_by(documento=doc_remetente).first()
            if remetente_existente:
                validacoes['remetente_existe'] = True
                validacoes['detalhes']['remetente'] = {
                    'id': remetente_existente.idPessoas,
                    'razao_social': remetente_existente.razaosocial,
                    'documento': remetente_existente.documento,
                    'tipo': remetente_existente.tipo
                }
        
        # Verificar nota fiscal
        nota_fiscal_data = dados_extraidos.get('nota_fiscal', {})
        numero_nf = nota_fiscal_data.get('numero', '')
        if numero_nf:
            nf_existente = MovimentoContas.query.filter_by(numeronotafiscal=numero_nf).first()
            if nf_existente:
                validacoes['nota_fiscal_existe'] = True
                validacoes['detalhes']['nota_fiscal'] = {
                    'id': nf_existente.idMovimentoContas,
                    'numero': nf_existente.numeronotafiscal,
                    'data_emissao': nf_existente.dataemissao.strftime('%d/%m/%Y') if nf_existente.dataemissao else '',
                    'valor_total': float(nf_existente.valortotal) if nf_existente.valortotal else 0,
                    'descricao': nf_existente.descricao
                }
        
        # Verificar classificações
        classificacoes = dados_extraidos.get('classificacoes', [])
        if classificacoes:
            for classificacao_nome in classificacoes:
                classificacao_existente = Classificacao.query.filter_by(nome=classificacao_nome).first()
                if classificacao_existente:
                    validacoes['classificacoes_existem'].append({
                        'id': classificacao_existente.idClassificacao,
                        'nome': classificacao_existente.nome,
                        'descricao': classificacao_existente.descricao
                    })
                else:
                    validacoes['classificacoes_novas'].append(classificacao_nome)
        
        # Preparar dados novos para exibição
        if not validacoes['emitente_existe']:
            validacoes['dados_novos']['emitente'] = dados_extraidos.get('emitente', {})
        
        if not validacoes['remetente_existe']:
            validacoes['dados_novos']['remetente'] = dados_extraidos.get('remetente', {})
        
        if not validacoes['nota_fiscal_existe']:
            validacoes['dados_novos']['nota_fiscal'] = dados_extraidos.get('nota_fiscal', {})
        
        if validacoes['classificacoes_novas']:
            validacoes['dados_novos']['classificacoes_novas'] = validacoes['classificacoes_novas']
        
        return validacoes
        
    except Exception as e:
        print(f"Erro ao verificar dados existentes: {str(e)}")
        return validacoes

def criar_classificacoes_novas(classificacoes_novas):
    """Cria novas classificações no banco de dados"""
    classificacoes_criadas = []
    
    try:
        for nome_classificacao in classificacoes_novas:
            # Verificar se já existe (dupla verificação)
            classificacao_existente = Classificacao.query.filter_by(nome=nome_classificacao).first()
            if not classificacao_existente:
                nova_classificacao = Classificacao(
                    nome=nome_classificacao,
                    descricao=f"Classificação criada automaticamente: {nome_classificacao}"
                )
                db.session.add(nova_classificacao)
                db.session.flush()  # Para obter o ID
                
                classificacoes_criadas.append({
                    'id': nova_classificacao.idClassificacao,
                    'nome': nova_classificacao.nome,
                    'descricao': nova_classificacao.descricao
                })
        
        db.session.commit()
        return classificacoes_criadas
        
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao criar classificações: {str(e)}")
        return []

def salvar_dados_banco(dados_extraidos):
    """Salva os dados extraídos no banco de dados"""
    try:
        # Buscar ou criar pessoa emitente
        emitente_data = dados_extraidos.get('emitente', {})
        emitente = Pessoas.query.filter_by(documento=emitente_data.get('cnpj', '')).first()
        
        if not emitente:
            emitente = Pessoas(
                tipo='FORNECEDOR',
                razaosocial=emitente_data.get('razao_social', ''),
                fantasia=emitente_data.get('nome_fantasia', ''),
                documento=emitente_data.get('cnpj', ''),
                status='ATIVO'
            )
            db.session.add(emitente)
            db.session.flush()  # Para obter o ID
        
        # Buscar ou criar pessoa remetente/destinatário
        remetente_data = dados_extraidos.get('remetente', {})
        remetente = Pessoas.query.filter_by(documento=remetente_data.get('cpf_ou_cnpj', '')).first()
        
        if not remetente:
            remetente = Pessoas(
                tipo='CLIENTE',
                razaosocial=remetente_data.get('nome_completo', ''),
                fantasia=remetente_data.get('nome_completo', ''),
                documento=remetente_data.get('cpf_ou_cnpj', ''),
                status='ATIVO'
            )
            db.session.add(remetente)
            db.session.flush()  # Para obter o ID
        
        # Criar movimento de conta
        nota_fiscal_data = dados_extraidos.get('nota_fiscal', {})
        itens_data = dados_extraidos.get('itens', {})
        
        # Converter data de emissão
        data_emissao_str = nota_fiscal_data.get('data_emissao', '')
        try:
            data_emissao = datetime.strptime(data_emissao_str, '%d/%m/%Y').date()
        except:
            data_emissao = datetime.now().date()
        
        movimento = MovimentoContas(
            tipo='DESPESA',
            numeronotafiscal=nota_fiscal_data.get('numero', ''),
            dataemissao=data_emissao,
            descricao=itens_data.get('descricao_produtos', ''),
            status='ATIVO',
            valortotal=itens_data.get('valor_total', 0),
            Pessoas_idFornecedorCliente=emitente.idPessoas,
            Pessoas_idFaturado=remetente.idPessoas
        )
        db.session.add(movimento)
        db.session.flush()  # Para obter o ID
        
        # Associar classificações
        classificacoes_nomes = dados_extraidos.get('classificacoes', [])
        for classificacao_nome in classificacoes_nomes:
            classificacao = Classificacao.query.filter_by(descricao=classificacao_nome, tipo='DESPESA').first()
            if classificacao:
                movimento.classificacoes.append(classificacao)
        
        # Criar parcelas se especificado
        num_parcelas = itens_data.get('parcelas', 1)
        valor_parcela = float(itens_data.get('valor_total', 0)) / num_parcelas
        
        for i in range(num_parcelas):
            parcela = ParcelasContas(
                identificacao=f"{nota_fiscal_data.get('numero', '')}-{i+1}",
                datavencimento=data_emissao,  # Pode ser ajustado conforme necessário
                valorparcela=valor_parcela,
                valorpago=0.00,
                valorsaldo=valor_parcela,
                statusparcela='PENDENTE'
            )
            db.session.add(parcela)
        
        db.session.commit()
        
        return {
            'sucesso': True,
            'movimento_id': movimento.idMovimentoContas,
            'emitente_id': emitente.idPessoas,
            'remetente_id': remetente.idPessoas
        }
        
    except Exception as e:
        db.session.rollback()
        return {'sucesso': False, 'erro': str(e)}

def processar_nota_fiscal_gemini(texto_pdf):
    """Processa a nota fiscal usando Gemini AI - versão simplificada e estável"""
    
    # Prompt original (funcionava bem)
    prompt = f"""
    Analise a seguinte nota fiscal e extraia as informações em formato JSON:

    {texto_pdf}

    Categorias de despesas disponíveis:
    - INSUMOS AGRÍCOLAS: sementes, fertilizantes, defensivos agrícolas, corretivos, soja, milho, npk
    - MANUTENÇÃO E OPERAÇÃO: combustíveis, lubrificantes, óleo diesel, gasolina, peças, manutenção, pneus, filtros, ferramentas, diesel, óleo, trator
    - RECURSOS HUMANOS: mão de obra temporária, salários, encargos
    - SERVIÇOS OPERACIONAIS: frete, transporte, colheita terceirizada, secagem, armazenagem, pulverização, aplicação, mercadorias
    - INFRAESTRUTURA E UTILIDADES: energia elétrica, arrendamento de terras, construções, reformas, materiais de construção, material hidráulico, cimento, ferro
    - ADMINISTRATIVAS: honorários, contábeis, advocatícios, agronômicos, despesas bancárias, financeiras
    - SEGUROS E PROTEÇÃO: seguro agrícola, seguro de ativos, seguro prestamista, máquinas, veículos
    - IMPOSTOS E TAXAS: ITR, IPTU, IPVA, INCRA-CCIR
    - INVESTIMENTOS: aquisição de máquinas, implementos, aquisição de veículos, aquisição de imóveis, infraestrutura rural
    - Outros: para itens que não se encaixam nas categorias acima

    Exemplo de resposta esperada:
    {{
        "nota_fiscal": {{
            "numero": "123456",
            "serie": "1",
            "data_emissao": "2024-01-15"
        }},
        "emitente": {{
            "razao_social": "Empresa ABC Ltda",
            "cnpj": "12.345.678/0001-90",
            "endereco": "Rua das Flores, 123, São Paulo, SP"
        }},
        "remetente": {{
            "nome_completo": "João Silva",
            "cpf_ou_cnpj": "123.456.789-00",
            "endereco": "Fazenda Santa Maria, Zona Rural, Cidade, Estado"
        }},
        "itens": {{
            "descricao_produtos": "Fertilizante NPK 20-05-20",
            "quantidade": 10,
            "parcelas": 1,
            "valor_total": 1500.00
        }},
        "classificacoes": ["INSUMOS AGRÍCOLAS"]
    }}

    Retorne APENAS o JSON, sem texto adicional.
    """
    
    try:
        print("Processando com Gemini...")
        
        # Usar a nova API do Google Gen AI SDK
        from google.genai import types
        
        # Estruturar o conteúdo usando types.Content
        content = types.Content(
            role="user",
            parts=[types.Part.from_text(prompt)]
        )
        
        # Fazer a requisição usando o cliente configurado
        response = genai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[content]
        )
        
        print("Processamento concluído")
        
        # Processar resposta usando a nova estrutura
        try:
            resposta_texto = response.candidates[0].content.parts[0].text.strip()
        except:
            return {"erro": "Não foi possível extrair texto da resposta do Gemini"}
        
        # Limpar formatação markdown
        if resposta_texto.startswith('```json'):
            resposta_texto = resposta_texto.replace('```json', '').replace('```', '').strip()
        elif resposta_texto.startswith('```'):
            resposta_texto = resposta_texto.replace('```', '').strip()
        
        # Tentar fazer parse do JSON
        try:
            dados_extraidos = json.loads(resposta_texto)
            
            # Classificar automaticamente se não tiver classificação
            if 'classificacoes' not in dados_extraidos or not dados_extraidos['classificacoes']:
                if 'itens' in dados_extraidos and 'descricao_produtos' in dados_extraidos['itens']:
                    categoria = classificar_despesa(dados_extraidos['itens']['descricao_produtos'])
                    dados_extraidos['classificacoes'] = [categoria]
            
            return dados_extraidos
            
        except json.JSONDecodeError as e:
            return {"erro": f"Erro ao processar JSON: {str(e)}", "resposta_bruta": resposta_texto}
            
    except Exception as e:
        error_msg = str(e)
        print(f"Erro ao processar com Gemini: {error_msg}")
        return {"erro": f"Erro ao processar com Gemini: {error_msg}"}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_pdf():
    try:
        if 'pdf' not in request.files:
            return jsonify({"erro": "Nenhum arquivo PDF foi enviado"}), 400
        
        arquivo = request.files['pdf']
        
        if arquivo.filename == '':
            return jsonify({"erro": "Nenhum arquivo selecionado"}), 400
        
        if not arquivo.filename.lower().endswith('.pdf'):
            return jsonify({"erro": "Arquivo deve ser um PDF"}), 400
        
        # Extrair texto do PDF
        texto_pdf = extrair_texto_pdf(BytesIO(arquivo.read()))
        
        if texto_pdf.startswith("Erro"):
            return jsonify({"erro": texto_pdf}), 400
        
        # Processar com Gemini AI
        dados_extraidos = processar_nota_fiscal_gemini(texto_pdf)
        
        if "erro" in dados_extraidos:
            return jsonify(dados_extraidos), 400
        
        # Verificar se dados já existem no banco
        validacoes = verificar_dados_existentes(dados_extraidos)
        
        # Processar classificações novas
        classificacoes_criadas = []
        if validacoes['classificacoes_novas']:
            classificacoes_criadas = criar_classificacoes_novas(validacoes['classificacoes_novas'])
            validacoes['classificacoes_criadas'] = classificacoes_criadas
        
        # Filtrar dados que já existem do JSON de resposta
        dados_filtrados = dados_extraidos.copy()
        
        if validacoes['emitente_existe']:
            dados_filtrados.pop('emitente', None)
        
        if validacoes['remetente_existe']:
            dados_filtrados.pop('remetente', None)
        
        if validacoes['nota_fiscal_existe']:
            dados_filtrados.pop('nota_fiscal', None)
        
        # Adicionar informações de validação ao retorno
        dados_filtrados['validacoes'] = validacoes
        
        # Adicionar dados originais para possível salvamento posterior
        dados_filtrados['dados_originais'] = dados_extraidos
        
        return jsonify(dados_filtrados)
        
    except Exception as e:
        return jsonify({"erro": f"Erro interno do servidor: {str(e)}"}), 500

@app.route('/salvar-dados', methods=['POST'])
def salvar_dados():
    """Rota para salvar dados extraídos no banco de dados"""
    try:
        dados = request.get_json()
        
        if not dados:
            return jsonify({"erro": "Nenhum dado foi enviado"}), 400
        
        # Verificar se os dados originais estão presentes
        if 'dados_originais' not in dados:
            return jsonify({"erro": "Dados originais não encontrados"}), 400
        
        dados_extraidos = dados['dados_originais']
        
        # Verificar novamente se dados já existem no banco (segurança)
        validacoes = verificar_dados_existentes(dados_extraidos)
        
        # Se a nota fiscal já existe, não salvar
        if validacoes['nota_fiscal_existe']:
            return jsonify({
                "erro": "Nota fiscal já existe no banco de dados",
                "detalhes": validacoes['detalhes']['nota_fiscal']
            }), 409
        
        # Processar classificações novas se necessário
        if validacoes['classificacoes_novas']:
            criar_classificacoes_novas(validacoes['classificacoes_novas'])
        
        # Salvar dados no banco
        resultado_banco = salvar_dados_banco(dados_extraidos)
        
        return jsonify({
            "sucesso": True,
            "mensagem": "Dados salvos com sucesso no banco de dados",
            "resultado": resultado_banco
        })
        
    except Exception as e:
        return jsonify({"erro": f"Erro ao salvar dados: {str(e)}"}), 500

@app.route('/categorias')
def get_categorias():
    """Retorna as categorias do banco de dados"""
    try:
        classificacoes = Classificacao.query.filter_by(status='ATIVO').all()
        categorias = {}
        
        for classificacao in classificacoes:
            if classificacao.tipo not in categorias:
                categorias[classificacao.tipo] = []
            categorias[classificacao.tipo].append(classificacao.descricao)
        
        return jsonify(categorias)
    except Exception as e:
        return jsonify({"erro": f"Erro ao buscar categorias: {str(e)}"}), 500

# Novas rotas para gerenciamento de dados

@app.route('/pessoas', methods=['GET'])
def listar_pessoas():
    """Lista todas as pessoas cadastradas"""
    try:
        pessoas = Pessoas.query.filter_by(status='ATIVO').all()
        return jsonify([pessoa.to_dict() for pessoa in pessoas])
    except Exception as e:
        return jsonify({"erro": f"Erro ao listar pessoas: {str(e)}"}), 500

@app.route('/pessoas', methods=['POST'])
def criar_pessoa():
    """Cria uma nova pessoa"""
    try:
        dados = request.get_json()
        
        # Verificar se já existe pessoa com o mesmo documento
        pessoa_existente = Pessoas.query.filter_by(documento=dados.get('documento')).first()
        if pessoa_existente:
            return jsonify({"erro": "Já existe uma pessoa com este documento"}), 400
        
        nova_pessoa = Pessoas(
            tipo=dados.get('tipo'),
            razaosocial=dados.get('razaosocial'),
            fantasia=dados.get('fantasia'),
            documento=dados.get('documento'),
            status=dados.get('status', 'ATIVO')
        )
        
        db.session.add(nova_pessoa)
        db.session.commit()
        
        return jsonify(nova_pessoa.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": f"Erro ao criar pessoa: {str(e)}"}), 500

@app.route('/movimentos', methods=['GET'])
def listar_movimentos():
    """Lista todos os movimentos de contas"""
    try:
        movimentos = MovimentoContas.query.filter_by(status='ATIVO').all()
        return jsonify([movimento.to_dict() for movimento in movimentos])
    except Exception as e:
        return jsonify({"erro": f"Erro ao listar movimentos: {str(e)}"}), 500

@app.route('/parcelas', methods=['GET'])
def listar_parcelas():
    """Lista todas as parcelas"""
    try:
        parcelas = ParcelasContas.query.all()
        return jsonify([parcela.to_dict() for parcela in parcelas])
    except Exception as e:
        return jsonify({"erro": f"Erro ao listar parcelas: {str(e)}"}), 500

@app.route('/classificacoes', methods=['GET'])
def listar_classificacoes():
    """Lista todas as classificações"""
    try:
        classificacoes = Classificacao.query.filter_by(status='ATIVO').all()
        return jsonify([classificacao.to_dict() for classificacao in classificacoes])
    except Exception as e:
        return jsonify({"erro": f"Erro ao listar classificações: {str(e)}"}), 500

# Rotas do segundo agente IA

@app.route('/agente-ia/analisar-fluxo-caixa', methods=['GET'])
def analisar_fluxo_caixa():
    """Analisa o fluxo de caixa usando o segundo agente IA"""
    try:
        periodo_dias = request.args.get('periodo', 30, type=int)
        resultado = agente_ia.analisar_fluxo_caixa(periodo_dias)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"erro": f"Erro na análise de fluxo de caixa: {str(e)}"}), 500

@app.route('/agente-ia/classificar-despesas', methods=['POST'])
def classificar_despesas_automaticamente():
    """Reclassifica despesas automaticamente usando IA"""
    try:
        resultado = agente_ia.classificar_despesas_automaticamente()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"erro": f"Erro na classificação automática: {str(e)}"}), 500

@app.route('/agente-ia/relatorio-categorias', methods=['GET'])
def gerar_relatorio_categorias():
    """Gera relatório detalhado por categorias"""
    try:
        resultado = agente_ia.gerar_relatorio_categorias()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"erro": f"Erro ao gerar relatório: {str(e)}"}), 500

@app.route('/agente-ia/prever-fluxo-caixa', methods=['GET'])
def prever_fluxo_caixa():
    """Prevê o fluxo de caixa para os próximos dias"""
    try:
        dias_previsao = request.args.get('dias', 30, type=int)
        resultado = agente_ia.prever_fluxo_caixa(dias_previsao)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"erro": f"Erro ao prever fluxo de caixa: {str(e)}"}), 500

@app.route('/admin')
def admin():
    """Interface administrativa para visualização das tabelas do banco"""
    return render_template('admin.html')

# -----------------------------
# Página e API de Busca Inteligente (RAG)
# -----------------------------

def _cosine_similarity(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)

def _simple_corpus(limit=150, filtros=None):
    ctx = []
    filtros = filtros or {}
    data_inicio = filtros.get('data_inicio')
    data_fim = filtros.get('data_fim')
    min_valor = filtros.get('min_valor')
    max_valor = filtros.get('max_valor')

    # Pessoas
    pessoas = Pessoas.query.limit(limit).all()
    for p in pessoas:
        texto = (
            f"Pessoa: {p.razaosocial or ''} | Documento: {p.documento or ''} | "
            f"Tipo: {p.tipo or ''} | Fantasia: {p.fantasia or ''} | Status: {p.status or ''}"
        )
        ctx.append({"texto": texto, "fonte": f"pessoas:{p.idPessoas}"})

    # Movimentos (com filtros)
    qmov = MovimentoContas.query
    if data_inicio:
        qmov = qmov.filter(MovimentoContas.dataemissao >= data_inicio)
    if data_fim:
        qmov = qmov.filter(MovimentoContas.dataemissao <= data_fim)
    if min_valor is not None:
        qmov = qmov.filter(MovimentoContas.valortotal >= min_valor)
    if max_valor is not None:
        qmov = qmov.filter(MovimentoContas.valortotal <= max_valor)
    movimentos = qmov.limit(limit).all()
    for m in movimentos:
        pessoa_nome = m.fornecedor_cliente.razaosocial if m.fornecedor_cliente else ''
        classificacoes = ', '.join([c.descricao for c in m.classificacoes]) if m.classificacoes else ''
        texto = (
            f"Movimento: {m.tipo or ''} | Valor: {float(m.valortotal) if m.valortotal else 0} | "
            f"NF: {m.numeronotafiscal or ''} | Data: {m.dataemissao.strftime('%d/%m/%Y') if m.dataemissao else ''} | "
            f"Pessoa: {pessoa_nome} | Classificações: {classificacoes} | Status: {m.status or ''}"
        )
        ctx.append({"texto": texto, "fonte": f"movimentos:{m.idMovimentoContas}"})

    # Parcelas (com filtros)
    qpar = ParcelasContas.query
    if data_inicio:
        qpar = qpar.filter(ParcelasContas.datavencimento >= data_inicio)
    if data_fim:
        qpar = qpar.filter(ParcelasContas.datavencimento <= data_fim)
    if min_valor is not None:
        qpar = qpar.filter(ParcelasContas.valorparcela >= min_valor)
    if max_valor is not None:
        qpar = qpar.filter(ParcelasContas.valorparcela <= max_valor)
    parcelas = qpar.limit(limit).all()
    for p in parcelas:
        texto = (
            f"Parcela: {p.identificacao} | Vencimento: {p.datavencimento.strftime('%d/%m/%Y') if p.datavencimento else ''} | "
            f"Valor: {float(p.valorparcela) if p.valorparcela else 0} | Pago: {float(p.valorpago) if p.valorpago else 0} | "
            f"Saldo: {float(p.valorsaldo) if p.valorsaldo else 0} | Status: {p.statusparcela or ''}"
        )
        ctx.append({"texto": texto, "fonte": f"parcela:{p.idParcelasContas}"})

    # Classificações
    classificacoes = Classificacao.query.limit(limit).all()
    for c in classificacoes:
        texto = (
            f"Classificação: {c.descricao} | Tipo: {c.tipo} | Status: {c.status}"
        )
        ctx.append({"texto": texto, "fonte": f"classificacao:{c.idClassificacao}"})
    return ctx

def _embed_texts(texts):
    try:
        embeddings = []
        for t in texts:
            emb = genai_client.models.embed_content(model='text-embedding-004', content=t)
            vec = None
            if isinstance(emb, dict):
                vec = emb.get('embedding', {}).get('values') or emb.get('embedding')
            elif hasattr(emb, 'embedding'):
                e = getattr(emb, 'embedding')
                if isinstance(e, dict):
                    vec = e.get('values') or e
                else:
                    vec = e
            if not vec:
                vec = []
            embeddings.append(vec)
        return embeddings
    except Exception:
        return [[] for _ in texts]

def _rag_simples(pergunta: str, corpus, top_k=6):
    q = pergunta.lower()
    scores = []
    for item in corpus:
        txt = item["texto"].lower()
        terms = [t for t in q.split() if len(t) > 2]
        score = sum(1 for t in terms if t in txt)
        scores.append((score, item))
    scores.sort(key=lambda x: x[0], reverse=True)
    top = [it for sc, it in scores[:top_k] if sc > 0]
    return top

def _rag_embeddings(pergunta: str, corpus, top_k=6):
    textos = [c["texto"] for c in corpus]
    vecs = _embed_texts(textos + [pergunta])
    if not vecs or len(vecs) != len(textos) + 1:
        return _rag_simples(pergunta, corpus, top_k)
    qvec = vecs[-1]
    sims = []
    for i, c in enumerate(corpus):
        sim = _cosine_similarity(vecs[i], qvec)
        sims.append((sim, c))
    sims.sort(key=lambda x: x[0], reverse=True)
    top = [it for sc, it in sims[:top_k] if sc > 0]
    return top

def _extract_filters_from_question(pergunta: str):
    q = (pergunta or '').lower()
    hoje = datetime.today().date()
    filtros = {
        'alvo': None,
        'data_inicio': None,
        'data_fim': None,
        'min_valor': None,
        'max_valor': None,
        'classificacoes_incluidas': [],
        'pessoas_nomes': []
    }

    if any(k in q for k in ['parcela', 'parcelas']):
        filtros['alvo'] = 'parcelas'
    elif any(k in q for k in ['nota fiscal', 'nf', 'movimento', 'despesa', 'receita']):
        filtros['alvo'] = 'movimentos'
    elif 'classific' in q:
        filtros['alvo'] = 'classificacoes'
    elif any(k in q for k in ['fornecedor', 'cliente', 'pessoa', 'empresa']):
        filtros['alvo'] = 'pessoas'
    else:
        filtros['alvo'] = 'movimentos'

    def inicio_mes(d):
        return d.replace(day=1)

    def inicio_semana(d):
        return d - timedelta(days=d.weekday())

    # Datas relativas
    try:
        from datetime import timedelta
        if 'mês atual' in q or 'mes atual' in q:
            filtros['data_inicio'] = inicio_mes(hoje)
            filtros['data_fim'] = hoje
        elif 'último mês' in q or 'ultimo mes' in q:
            m = hoje.month - 1 or 12
            y = hoje.year - 1 if hoje.month == 1 else hoje.year
            inicio = datetime(year=y, month=m, day=1).date()
            if m == 12:
                fim = datetime(year=y, month=12, day=31).date()
            else:
                fim = (datetime(year=y, month=m+1, day=1).date() - timedelta(days=1))
            filtros['data_inicio'] = inicio
            filtros['data_fim'] = fim
        elif 'esta semana' in q or 'semana atual' in q:
            filtros['data_inicio'] = inicio_semana(hoje)
            filtros['data_fim'] = hoje
        elif 'este trimestre' in q or 'trimestre atual' in q:
            qm = ((hoje.month - 1)//3)*3 + 1
            filtros['data_inicio'] = datetime(year=hoje.year, month=qm, day=1).date()
            filtros['data_fim'] = hoje
        elif 'último trimestre' in q or 'ultimo trimestre' in q:
            qm = ((hoje.month - 1)//3)*3 + 1
            # Trimestre anterior
            prev_qm = qm - 3
            y = hoje.year
            if prev_qm < 1:
                prev_qm += 12
                y -= 1
            inicio = datetime(year=y, month=prev_qm, day=1).date()
            fim = (datetime(year=y, month=prev_qm+3 if prev_qm+3 <= 12 else 1, day=1).date() - timedelta(days=1))
            filtros['data_inicio'] = inicio
            filtros['data_fim'] = fim
        elif 'este ano' in q or 'ano atual' in q:
            filtros['data_inicio'] = datetime(year=hoje.year, month=1, day=1).date()
            filtros['data_fim'] = hoje
    except Exception:
        pass

    # Datas explícitas dd/mm/yyyy
    try:
        matches = re.findall(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', q)
        if matches:
            def parse_pt(s):
                s = s.replace('-', '/')
                parts = s.split('/')
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 100: y += 2000
                return datetime(year=y, month=m, day=d).date()
            if len(matches) >= 2:
                filtros['data_inicio'] = parse_pt(matches[0])
                filtros['data_fim'] = parse_pt(matches[1])
            elif len(matches) == 1:
                filtros['data_inicio'] = parse_pt(matches[0])
    except Exception:
        pass

    # Valores
    def parse_val(txt):
        try:
            txt = txt.replace('.', '').replace(',', '.')
            return float(txt)
        except Exception:
            return None
    m_maior = re.search(r'(acima de|maior que)\s*(\d+[\.,]?\d*)', q)
    m_menor = re.search(r'(menor que|até)\s*(\d+[\.,]?\d*)', q)
    if m_maior:
        filtros['min_valor'] = parse_val(m_maior.group(2))
    if m_menor:
        filtros['max_valor'] = parse_val(m_menor.group(2))

    # Classificações mencionadas
    try:
        cls = Classificacao.query.all()
        for c in cls:
            name = (c.descricao or '').lower()
            if name and name in q:
                filtros['classificacoes_incluidas'].append(c.descricao)
    except Exception:
        pass

    # Pessoas mencionadas (fornecedor/cliente)
    try:
        ps = Pessoas.query.all()
        for p in ps:
            nm = (p.razaosocial or '').lower()
            if nm and nm in q:
                filtros['pessoas_nomes'].append(p.razaosocial)
            fn = (p.fantasia or '').lower()
            if fn and fn in q:
                filtros['pessoas_nomes'].append(p.fantasia)
    except Exception:
        pass

    return filtros

def _query_db_by_filters(filtros, limit=200):
    alvo = filtros.get('alvo')
    di = filtros.get('data_inicio')
    df = filtros.get('data_fim')
    minv = filtros.get('min_valor')
    maxv = filtros.get('max_valor')
    cls_in = set(filtros.get('classificacoes_incluidas') or [])
    pessoas_n = set((filtros.get('pessoas_nomes') or []))

    corpus = []
    try:
        if alvo == 'parcelas':
            q = ParcelasContas.query
            if di:
                q = q.filter(ParcelasContas.datavencimento >= di)
            if df:
                q = q.filter(ParcelasContas.datavencimento <= df)
            if minv is not None:
                q = q.filter(ParcelasContas.valorparcela >= minv)
            if maxv is not None:
                q = q.filter(ParcelasContas.valorparcela <= maxv)
            itens = q.order_by(ParcelasContas.datavencimento.desc()).limit(limit).all()
            for p in itens:
                texto = (
                    f"Parcela {p.identificacao} vencimento {p.datavencimento} "
                    f"valor {float(p.valorparcela):.2f} pago {float(p.valorpago or 0):.2f} saldo {float(p.valorsaldo or 0):.2f} "
                    f"status {p.statusparcela}"
                )
                corpus.append({"texto": texto, "fonte": f"parcelas:{p.idParcelasContas}"})
        elif alvo == 'classificacoes':
            q = Classificacao.query
            if cls_in:
                q = q.filter(Classificacao.descricao.in_(list(cls_in)))
            itens = q.limit(limit).all()
            for c in itens:
                texto = f"Classificação {c.tipo} - {c.descricao} status {c.status}"
                corpus.append({"texto": texto, "fonte": f"classificacoes:{c.idClassificacao}"})
        elif alvo == 'pessoas':
            q = Pessoas.query
            itens = q.limit(limit).all()
            for p in itens:
                if pessoas_n:
                    nm = (p.razaosocial or '')
                    fn = (p.fantasia or '')
                    if not any(x.lower() in (nm.lower() + ' ' + fn.lower()) for x in pessoas_n):
                        continue
                texto = f"Pessoa {p.tipo} {p.razaosocial} ({p.fantasia or '-'}) doc {p.documento} status {p.status}"
                corpus.append({"texto": texto, "fonte": f"pessoas:{p.idPessoas}"})
        else:
            q = MovimentoContas.query
            if di:
                q = q.filter(MovimentoContas.dataemissao >= di)
            if df:
                q = q.filter(MovimentoContas.dataemissao <= df)
            if minv is not None:
                q = q.filter(MovimentoContas.valortotal >= minv)
            if maxv is not None:
                q = q.filter(MovimentoContas.valortotal <= maxv)
            itens = q.order_by(MovimentoContas.dataemissao.desc()).limit(limit).all()
            for m in itens:
                if cls_in:
                    nomes = [c.descricao for c in (m.classificacoes or [])]
                    if not any(n in cls_in for n in nomes):
                        continue
                if pessoas_n:
                    fc = getattr(m, 'fornecedor_cliente', None)
                    nm = ((fc.razaosocial if fc else '') + ' ' + (fc.fantasia if fc and fc.fantasia else '')).lower()
                    if not any(x.lower() in nm for x in pessoas_n):
                        continue
                fornecedor = m.fornecedor_cliente.razaosocial if m.fornecedor_cliente else '-'
                classes = ', '.join([c.descricao for c in (m.classificacoes or [])]) or '-'
                texto = (
                    f"Movimento {m.tipo} NF {m.numeronotafiscal or '-'} emissão {m.dataemissao} "
                    f"valor {float(m.valortotal):.2f} fornecedor {fornecedor} classificações {classes} "
                    f"descrição {(m.descricao or '').strip()}"
                )
                corpus.append({"texto": texto, "fonte": f"movimentos:{m.idMovimentoContas}"})
    except Exception:
        pass

    return corpus

@app.route('/rag')
def rag_page():
    return render_template('rag.html')

@app.route('/rag/query', methods=['POST'])
def rag_query():
    """Rota principal RAG - usa Agent3 com estratégia híbrida"""
    try:
        data = request.get_json(force=True)
        pergunta = (data.get('pergunta') or '').strip()
    except Exception:
        return jsonify({"sucesso": False, "erro": "JSON inválido."}), 400

    if not pergunta:
        return jsonify({"sucesso": False, "erro": "Pergunta vazia."}), 400

    if not GEMINI_API_KEY:
        return jsonify({"sucesso": False, "erro": "GEMINI_API_KEY não configurada."}), 500

    # Usar Agent3 para centralizar entendimento, recuperação e geração
    try:
        agent = Agent3(model_name='gemini-2.5-flash')
        result = agent.run_query(pergunta)
        result['metodo'] = 'Híbrido (Agent3)'
        return jsonify(result)
    except Exception as e:
        return jsonify({"sucesso": False, "erro": f"Falha no agente RAG: {str(e)}"}), 500

@app.route('/rag/query-simples', methods=['POST'])
def rag_query_simples():
    """RAG Simples - busca por palavras-chave"""
    try:
        data = request.get_json(force=True)
        pergunta = (data.get('pergunta') or '').strip()
    except Exception:
        return jsonify({"sucesso": False, "erro": "JSON inválido."}), 400

    if not pergunta:
        return jsonify({"sucesso": False, "erro": "Pergunta vazia."}), 400

    try:
        # Buscar dados do banco
        filtros = _extract_filters_from_question(pergunta)
        corpus = _query_db_by_filters(filtros, limit=100)
        
        # Se não encontrou nada, usar corpus geral
        if not corpus:
            corpus = _simple_corpus(limit=50, filtros=filtros)
        
        # Aplicar RAG simples (busca por palavras-chave)
        import time
        start_time = time.time()
        resultados = _rag_simples(pergunta, corpus, top_k=8)
        tempo_busca = round((time.time() - start_time) * 1000, 2)
        
        # Montar contexto
        contexto_textos = [r["texto"] for r in resultados]
        contexto_str = "\n\n".join(contexto_textos) if contexto_textos else "(sem dados)"
        
        # Gerar resposta com LLM
        if GEMINI_API_KEY and contexto_textos:
            prompt = f"""Você é um assistente financeiro. Analise os dados abaixo e responda a pergunta de forma clara e objetiva em português do Brasil.

DADOS ENCONTRADOS:
{contexto_str}

PERGUNTA: {pergunta}

Responda de forma estruturada, citando valores e datas quando relevante."""
            
            try:
                content = types.Content(
                    role="user",
                    parts=[types.Part.from_text(prompt)]
                )
                response = genai_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[content]
                )
                resposta = response.candidates[0].content.parts[0].text.strip()
            except Exception as e:
                resposta = f"Erro ao gerar resposta com LLM: {str(e)}\n\nDados encontrados:\n" + contexto_str
        else:
            resposta = f"Encontrados {len(resultados)} registros:\n\n" + contexto_str
        
        return jsonify({
            "sucesso": True,
            "resposta": resposta,
            "contexto": contexto_textos,
            "metodo": "RAG Simples (Palavras-chave)",
            "tempo_busca_ms": tempo_busca,
            "registros_encontrados": len(resultados)
        })
    except Exception as e:
        return jsonify({"sucesso": False, "erro": f"Erro no RAG simples: {str(e)}"}), 500

@app.route('/rag/query-embeddings', methods=['POST'])
def rag_query_embeddings():
    """RAG com Embeddings - busca semântica"""
    try:
        data = request.get_json(force=True)
        pergunta = (data.get('pergunta') or '').strip()
    except Exception:
        return jsonify({"sucesso": False, "erro": "JSON inválido."}), 400

    if not pergunta:
        return jsonify({"sucesso": False, "erro": "Pergunta vazia."}), 400

    if not GEMINI_API_KEY:
        return jsonify({"sucesso": False, "erro": "GEMINI_API_KEY não configurada."}), 500

    try:
        # Buscar dados do banco
        filtros = _extract_filters_from_question(pergunta)
        corpus = _query_db_by_filters(filtros, limit=100)
        
        # Se não encontrou nada, usar corpus geral
        if not corpus:
            corpus = _simple_corpus(limit=50, filtros=filtros)
        
        # Aplicar RAG com embeddings
        import time
        start_time = time.time()
        resultados = _rag_embeddings(pergunta, corpus, top_k=8)
        tempo_busca = round((time.time() - start_time) * 1000, 2)
        
        # Montar contexto
        contexto_textos = [r["texto"] for r in resultados]
        contexto_str = "\n\n".join(contexto_textos) if contexto_textos else "(sem dados)"
        
        # Gerar resposta com LLM
        if contexto_textos:
            prompt = f"""Você é um assistente financeiro avançado. Analise os dados abaixo (recuperados por busca semântica) e responda a pergunta de forma clara e objetiva em português do Brasil.

DADOS ENCONTRADOS (por similaridade semântica):
{contexto_str}

PERGUNTA: {pergunta}

Responda de forma estruturada, citando valores e datas quando relevante. Use os dados mais relevantes encontrados pela busca semântica."""
            
            try:
                content = types.Content(
                    role="user",
                    parts=[types.Part.from_text(prompt)]
                )
                response = genai_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[content]
                )
                resposta = response.candidates[0].content.parts[0].text.strip()
            except Exception as e:
                resposta = f"Erro ao gerar resposta com LLM: {str(e)}\n\nDados encontrados:\n" + contexto_str
        else:
            resposta = "Nenhum dado relevante encontrado para a pergunta."
        
        return jsonify({
            "sucesso": True,
            "resposta": resposta,
            "contexto": contexto_textos,
            "metodo": "RAG com Embeddings (Busca Semântica)",
            "tempo_busca_ms": tempo_busca,
            "registros_encontrados": len(resultados)
        })
    except Exception as e:
        return jsonify({"sucesso": False, "erro": f"Erro no RAG embeddings: {str(e)}"}), 500

@app.route('/admin/api/pessoas')
def admin_api_pessoas():
    """API para obter dados da tabela Pessoas para o admin"""
    try:
        pessoas = Pessoas.query.all()
        dados = []
        for pessoa in pessoas:
            dados.append({
                'id': pessoa.idPessoas,
                'nome': pessoa.razaosocial,
                'cpf_cnpj': pessoa.documento,
                'tipo': pessoa.tipo,
                'fantasia': pessoa.fantasia or '-',
                'status': pessoa.status
            })
        return jsonify(dados)
    except Exception as e:
        # Log detalhado no terminal/arquivo sem expor detalhes ao usuário
        logger.exception("Erro ao buscar pessoas na rota /admin/api/pessoas")
        return jsonify({"erro": "Não foi possível carregar. Tente novamente."}), 500

@app.route('/admin/api/pessoas/<int:id>')
def admin_api_pessoa_por_id(id):
    """API para obter dados de uma pessoa específica"""
    try:
        pessoa = Pessoas.query.get(id)
        if not pessoa:
            return jsonify({"success": False, "message": "Pessoa não encontrada"}), 404
        
        dados = {
            'id': pessoa.idPessoas,
            'razaosocial': pessoa.razaosocial,
            'documento': pessoa.documento,
            'tipo': pessoa.tipo,
            'fantasia': pessoa.fantasia or '',
            'status': pessoa.status
        }
        return jsonify({"success": True, "pessoa": dados})
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro ao buscar pessoa: {str(e)}"}), 500

@app.route('/admin/api/pessoas/<int:id>', methods=['PUT'])
def admin_api_editar_pessoa(id):
    """API para editar dados de uma pessoa"""
    try:
        pessoa = Pessoas.query.get(id)
        if not pessoa:
            return jsonify({"success": False, "message": "Pessoa não encontrada"}), 404
        
        dados = request.get_json()
        
        # Atualizar campos
        if 'razaosocial' in dados:
            pessoa.razaosocial = dados['razaosocial']
        if 'documento' in dados:
            pessoa.documento = dados['documento']
        if 'tipo' in dados:
            pessoa.tipo = dados['tipo']
        if 'fantasia' in dados:
            pessoa.fantasia = dados['fantasia']
        if 'status' in dados:
            status_val = str(dados['status']).upper()
            if status_val not in ['ATIVO', 'INATIVO']:
                return jsonify({"success": False, "message": "Status inválido"}), 400
            pessoa.status = status_val
        
        db.session.commit()
        return jsonify({"success": True, "message": "Pessoa atualizada com sucesso"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Erro ao atualizar pessoa: {str(e)}"}), 500

@app.route('/admin/api/pessoas/<int:id>/status', methods=['PUT'])
def admin_api_alterar_status_pessoa(id):
    """API para alterar status de uma pessoa (ativar/inativar)"""
    try:
        pessoa = Pessoas.query.get(id)
        if not pessoa:
            return jsonify({"success": False, "message": "Pessoa não encontrada"}), 404
        
        dados = request.get_json()
        novo_status = str(dados.get('status', '')).upper()
        
        if novo_status not in ['ATIVO', 'INATIVO']:
            return jsonify({"success": False, "message": "Status inválido"}), 400
        
        pessoa.status = novo_status
        db.session.commit()
        
        return jsonify({"success": True, "message": f"Status alterado"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Erro ao alterar status: {str(e)}"}), 500

@app.route('/admin/api/movimentos')
def admin_api_movimentos():
    """API para obter dados da tabela MovimentoContas para o admin"""
    try:
        movimentos = MovimentoContas.query.all()
        dados = []
        for movimento in movimentos:
            # Buscar pessoa fornecedor/cliente
            pessoa_nome = 'N/A'
            if movimento.fornecedor_cliente:
                pessoa_nome = movimento.fornecedor_cliente.razaosocial
            
            # Buscar classificações
            classificacao_nome = 'N/A'
            if movimento.classificacoes:
                classificacao_nome = ', '.join([c.descricao for c in movimento.classificacoes])
            
            dados.append({
                'id': movimento.idMovimentoContas,
                'pessoa_nome': pessoa_nome,
                'classificacao_nome': classificacao_nome,
                'descricao': movimento.descricao or '-',
                'valor': float(movimento.valortotal),
                'tipo_movimento': movimento.tipo,
                'data_movimento': movimento.dataemissao.strftime('%d/%m/%Y') if movimento.dataemissao else None,
                'data_criacao': '-'
            })
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": f"Erro ao buscar movimentos: {str(e)}"}), 500

@app.route('/admin/api/classificacoes')
def admin_api_classificacoes():
    """API para obter dados da tabela Classificacao para o admin"""
    try:
        classificacoes = Classificacao.query.all()
        dados = []
        for classificacao in classificacoes:
            dados.append({
                'id': classificacao.idClassificacao,
                'nome': classificacao.tipo,
                'descricao': classificacao.descricao,
                'data_criacao': '-'
            })
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": f"Erro ao buscar classificações: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)