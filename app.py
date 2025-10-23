from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from google import genai
import PyPDF2
import json
import os
import time
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv
# Voltando para PostgreSQL conforme solicitado
from database import db, init_db, Pessoas, Classificacao, MovimentoContas, ParcelasContas
from agente_ia import AgenteIA

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configurações do banco de dados PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/nf_ai_dados')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
                'endereco': pessoa.fantasia or '-',
                'telefone': '-',  # Campo não existe na tabela
                'email': '-',     # Campo não existe na tabela
                'data_criacao': '-',  # Campo não existe na tabela
                'status': pessoa.status
            })
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": f"Erro ao buscar pessoas: {str(e)}"}), 500

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