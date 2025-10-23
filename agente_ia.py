from google import genai
from google.genai import types
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sqlalchemy import func
# Voltando para PostgreSQL conforme solicitado
from database import db, Pessoas, Classificacao, MovimentoContas, ParcelasContas

# Carregar variáveis de ambiente
load_dotenv()

class AgenteIA:
    """
    Segundo agente IA especializado em análise financeira e relatórios
    """
    
    def __init__(self):
        try:
            self.api_key = os.getenv('GEMINI_API_KEY')
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY não encontrada nas variáveis de ambiente")
            
            # Configurar o cliente do Gemini com a chave API
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            print(f"Erro ao inicializar AgenteIA: {str(e)}")
            raise
    
    def analisar_fluxo_caixa(self, periodo_dias=30):
        """
        Analisa o fluxo de caixa dos últimos N dias
        """
        try:
            data_inicio = datetime.now().date() - timedelta(days=periodo_dias)
            
            # Buscar movimentos do período
            movimentos = MovimentoContas.query.filter(
                MovimentoContas.dataemissao >= data_inicio,
                MovimentoContas.status == 'ATIVO'
            ).all()
            
            # Organizar dados para análise
            dados_analise = {
                'periodo': f'{data_inicio.strftime("%d/%m/%Y")} a {datetime.now().strftime("%d/%m/%Y")}',
                'total_movimentos': len(movimentos),
                'movimentos': []
            }
            
            total_despesas = 0
            total_receitas = 0
            
            for movimento in movimentos:
                movimento_dict = movimento.to_dict()
                dados_analise['movimentos'].append(movimento_dict)
                
                if movimento.tipo == 'DESPESA':
                    total_despesas += float(movimento.valortotal)
                elif movimento.tipo == 'RECEITA':
                    total_receitas += float(movimento.valortotal)
            
            dados_analise['total_despesas'] = total_despesas
            dados_analise['total_receitas'] = total_receitas
            dados_analise['saldo_liquido'] = total_receitas - total_despesas
            
            # Prompt para análise da IA
            prompt = f"""
            Analise o seguinte fluxo de caixa e forneça insights financeiros:
            
            {json.dumps(dados_analise, indent=2, ensure_ascii=False)}
            
            Forneça uma análise detalhada incluindo:
            1. Resumo executivo do período
            2. Principais categorias de despesas
            3. Tendências identificadas
            4. Recomendações para otimização
            5. Alertas sobre possíveis problemas
            
            Retorne a resposta em formato JSON estruturado.
            """
            
            # Criar o conteúdo para o modelo
            content = types.Content(
                role='user',
                parts=[types.Part.from_text(text=prompt)]
            )
            
            # Gerar a resposta
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=content
            )
            analise_ia = response.text.strip()
            
            # Limpar formatação markdown se presente
            if analise_ia.startswith('```json'):
                analise_ia = analise_ia.replace('```json', '').replace('```', '').strip()
            
            try:
                analise_estruturada = json.loads(analise_ia)
            except:
                analise_estruturada = {"analise_texto": analise_ia}
            
            return {
                'dados_financeiros': dados_analise,
                'analise_ia': analise_estruturada,
                'sucesso': True
            }
            
        except Exception as e:
            return {'sucesso': False, 'erro': f"Erro ao processar com Gemini: {str(e)}"}
    
    def classificar_despesas_automaticamente(self):
        """
        Reclassifica despesas usando IA baseada em padrões históricos
        """
        try:
            # Buscar movimentos sem classificação ou com classificação "OUTROS"
            movimentos_sem_classificacao = MovimentoContas.query.filter(
                MovimentoContas.tipo == 'DESPESA',
                MovimentoContas.status == 'ATIVO'
            ).all()
            
            reclassificacoes = []
            
            for movimento in movimentos_sem_classificacao:
                # Verificar se tem classificação "OUTROS" ou nenhuma
                classificacoes_atuais = [c.descricao for c in movimento.classificacoes]
                
                if not classificacoes_atuais or 'OUTROS' in classificacoes_atuais:
                    # Usar IA para sugerir nova classificação
                    prompt = f"""
                    Analise a seguinte despesa e sugira a melhor classificação:
                    
                    Descrição: {movimento.descricao}
                    Valor: R$ {movimento.valortotal}
                    Fornecedor: {movimento.fornecedor_cliente.razaosocial if movimento.fornecedor_cliente else 'N/A'}
                    
                    Classificações disponíveis:
                    - INSUMOS AGRÍCOLAS
                    - MANUTENÇÃO E OPERAÇÃO
                    - RECURSOS HUMANOS
                    - SERVIÇOS OPERACIONAIS
                    - INFRAESTRUTURA E UTILIDADES
                    - ADMINISTRATIVAS
                    - SEGUROS E PROTEÇÃO
                    - IMPOSTOS E TAXAS
                    - INVESTIMENTOS
                    - OUTROS
                    
                    Retorne apenas o nome da classificação mais adequada.
                    """
                    
                    # Criar o conteúdo para o modelo
                    content = types.Content(
                        role='user',
                        parts=[types.Part.from_text(text=prompt)]
                    )
                    
                    # Gerar a resposta
                    response = self.client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=content
                    )
                    nova_classificacao = response.text.strip().upper()
                    
                    # Buscar classificação no banco
                    classificacao_obj = Classificacao.query.filter_by(
                        descricao=nova_classificacao,
                        tipo='DESPESA',
                        status='ATIVO'
                    ).first()
                    
                    if classificacao_obj:
                        # Remover classificações antigas
                        movimento.classificacoes.clear()
                        # Adicionar nova classificação
                        movimento.classificacoes.append(classificacao_obj)
                        
                        reclassificacoes.append({
                            'movimento_id': movimento.idMovimentoContas,
                            'descricao': movimento.descricao,
                            'classificacao_anterior': classificacoes_atuais,
                            'nova_classificacao': nova_classificacao
                        })
            
            db.session.commit()
            
            return {
                'sucesso': True,
                'total_reclassificacoes': len(reclassificacoes),
                'reclassificacoes': reclassificacoes
            }
            
        except Exception as e:
            db.session.rollback()
            return {'sucesso': False, 'erro': f"Erro ao processar com Gemini: {str(e)}"}
    
    def gerar_relatorio_categorias(self):
        """
        Gera relatório detalhado por categorias de despesas
        """
        try:
            # Buscar todas as classificações de despesas
            classificacoes = Classificacao.query.filter_by(tipo='DESPESA', status='ATIVO').all()
            
            relatorio = {
                'data_geracao': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                'categorias': []
            }
            
            for classificacao in classificacoes:
                # Buscar movimentos desta classificação
                movimentos = []
                for movimento in classificacao.movimentos:
                    if movimento.status == 'ATIVO' and movimento.tipo == 'DESPESA':
                        movimentos.append(movimento)
                
                if movimentos:
                    total_categoria = sum(float(m.valortotal) for m in movimentos)
                    
                    categoria_info = {
                        'nome': classificacao.descricao,
                        'total_movimentos': len(movimentos),
                        'valor_total': total_categoria,
                        'movimentos_recentes': [
                            {
                                'data': m.dataemissao.strftime('%d/%m/%Y'),
                                'descricao': m.descricao,
                                'valor': float(m.valortotal),
                                'fornecedor': m.fornecedor_cliente.razaosocial if m.fornecedor_cliente else 'N/A'
                            }
                            for m in sorted(movimentos, key=lambda x: x.dataemissao, reverse=True)[:5]
                        ]
                    }
                    
                    relatorio['categorias'].append(categoria_info)
            
            # Ordenar por valor total decrescente
            relatorio['categorias'].sort(key=lambda x: x['valor_total'], reverse=True)
            
            # Usar IA para análise do relatório
            prompt = f"""
            Analise o seguinte relatório de categorias de despesas e forneça insights:
            
            {json.dumps(relatorio, indent=2, ensure_ascii=False)}
            
            Forneça:
            1. Análise das principais categorias de gastos
            2. Identificação de oportunidades de economia
            3. Sugestões de controle de custos
            4. Alertas sobre gastos excessivos
            
            Retorne em formato JSON estruturado.
            """
            
            # Criar o conteúdo para o modelo
            content = types.Content(
                role='user',
                parts=[types.Part.from_text(text=prompt)]
            )
            
            # Gerar a resposta
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=content
            )
            analise_ia = response.text.strip()
            
            if analise_ia.startswith('```json'):
                analise_ia = analise_ia.replace('```json', '').replace('```', '').strip()
            
            try:
                analise_estruturada = json.loads(analise_ia)
            except:
                analise_estruturada = {"analise_texto": analise_ia}
            
            return {
                'dados_relatorio': relatorio,
                'analise_ia': analise_estruturada,
                'sucesso': True
            }
            
        except Exception as e:
            return {'sucesso': False, 'erro': f"Erro ao processar com Gemini: {str(e)}"}