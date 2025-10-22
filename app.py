from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import google.generativeai as genai
import PyPDF2
import json
import os
from io import BytesIO

app = Flask(__name__)
CORS(app)


GEMINI_API_KEY = "AIzaSyAvag5ZD7lFydA4NVcM6a6AsMjUaSfmk7A"  
genai.configure(api_key=GEMINI_API_KEY)


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

def processar_nota_fiscal_gemini(texto_pdf):
    """Processa a nota fiscal usando Gemini AI"""
    try:
      
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""
        Analise o seguinte texto de uma nota fiscal e extraia as informações em formato JSON:

        {texto_pdf}

        Classifique a seguinte descrição de produtos em uma das categorias abaixo:
        
        Categorias de Despesas:
        
        INSUMOS AGRÍCOLAS:
        - Sementes, Fertilizantes, Defensivos Agrícolas, Corretivos
        
        MANUTENÇÃO E OPERAÇÃO:
        - Combustíveis e Lubrificantes (Ex: Óleo Diesel, Gasolina, Óleo Lubrificante)
        - Peças, Parafusos, Componentes Mecânicos
        - Manutenção de Máquinas e Equipamentos
        - Pneus, Filtros, Correias
        - Ferramentas e Utensílios
        
        RECURSOS HUMANOS:
        - Mão de Obra Temporária
        - Salários e Encargos
        
        SERVIÇOS OPERACIONAIS:
        - Frete e Transporte
        - Colheita Terceirizada
        - Secagem e Armazenagem
        - Pulverização e Aplicação
        
        INFRAESTRUTURA E UTILIDADES:
        - Energia Elétrica
        - Arrendamento de Terras
        - Construções e Reformas
        - Materiais de Construção (Ex: Material Hidráulico, Cimento, Ferro)
        
        ADMINISTRATIVAS:
        - Honorários (Contábeis, Advocatícios, Agronômicos)
        - Despesas Bancárias e Financeiras
        
        SEGUROS E PROTEÇÃO:
        - Seguro Agrícola
        - Seguro de Ativos (Máquinas/Veículos)
        - Seguro Prestamista
        
        IMPOSTOS E TAXAS:
        - ITR, IPTU, IPVA, INCRA-CCIR
        
        INVESTIMENTOS:
        - Aquisição de Máquinas e Implementos
        - Aquisição de Veículos
        - Aquisição de Imóveis
        - Infraestrutura Rural
        
        Outros: despesas que não se enquadram nas categorias acima
        
        EXEMPLOS DE CLASSIFICAÇÃO:
        - "Óleo Diesel" → MANUTENÇÃO E OPERAÇÃO
        - "Material Hidráulico" → INFRAESTRUTURA E UTILIDADES
        - "Sementes de Soja" → INSUMOS AGRÍCOLAS
        - "Frete de Mercadorias" → SERVIÇOS OPERACIONAIS
        - "Fertilizante NPK" → INSUMOS AGRÍCOLAS
        - "Pneu para Trator" → MANUTENÇÃO E OPERAÇÃO
        - "Energia Elétrica" → INFRAESTRUTURA E UTILIDADES

        Retorne APENAS um JSON válido com a seguinte estrutura:
        {{
            "nota_fiscal": {{
                "numero": "string",
                "serie": "string",
                "data_emissao": "string (DD/MM/YYYY)"
            }},
            "emitente": {{
                "razao_social": "string",
                "nome_fantasia": "string",
                "cnpj": "string",
                "endereco": "string"
            }},
            "remetente": {{
                "nome_completo": "string",
                "cpf_ou_cnpj": "string",
                "endereco": "string"
            }},
            "itens": {{
                "descricao_produtos": "string",
                "quantidade": number,
                "parcelas": number,
                "valor_total": number
            }},
            "classificacoes": [
                "CATEGORIA_DESPESA_1",
                "CATEGORIA_DESPESA_2"
            ]
        }}

        IMPORTANTE: Analise cuidadosamente a descrição e classifique com base no uso principal do produto.
        Se a descrição não se enquadrar claramente em nenhuma das categorias específicas, classifique como "Outros".
        Responda apenas com o nome da categoria mais adequada (em MAIÚSCULAS).
        """
        
        response = model.generate_content(prompt)
        
        
        resposta_texto = response.text.strip()
        
        
        if resposta_texto.startswith('```json'):
            resposta_texto = resposta_texto.replace('```json', '').replace('```', '').strip()
        elif resposta_texto.startswith('```'):
            resposta_texto = resposta_texto.replace('```', '').strip()
        
        
        dados_extraidos = json.loads(resposta_texto)
        
        # Classificar a despesa baseada nos itens se não houver classificação
        if "itens" in dados_extraidos and "descricao_produtos" in dados_extraidos["itens"]:
            descricao_produtos = dados_extraidos["itens"]["descricao_produtos"]
            categoria_automatica = classificar_despesa(descricao_produtos)
            
            # Adicionar classificação automática se não houver
            if not dados_extraidos.get("classificacoes") or not dados_extraidos["classificacoes"]:
                dados_extraidos["classificacoes"] = [categoria_automatica]
        
        return dados_extraidos
        
    except json.JSONDecodeError as e:
        return {"erro": f"Erro ao processar JSON: {str(e)}", "resposta_bruta": resposta_texto}
    except Exception as e:
        return {"erro": f"Erro ao processar com Gemini: {str(e)}"}

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
        
        
        texto_pdf = extrair_texto_pdf(BytesIO(arquivo.read()))
        
        if texto_pdf.startswith("Erro"):
            return jsonify({"erro": texto_pdf}), 400
        
        
        dados_extraidos = processar_nota_fiscal_gemini(texto_pdf)
        
        return jsonify(dados_extraidos)
        
    except Exception as e:
        return jsonify({"erro": f"Erro interno do servidor: {str(e)}"}), 500

@app.route('/categorias')
def get_categorias():
    return jsonify(list(CATEGORIAS_DESPESAS.keys()))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)