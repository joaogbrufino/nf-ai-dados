import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any

from google import genai
from google.genai import types
import time
import random

from database import db, Pessoas, Classificacao, MovimentoContas, ParcelasContas


class Agent3:
    """
    Motor RAG centralizado: entendimento -> recuperação -> geração de resposta.
    """

    def __init__(self, model_name: str = 'gemini-2.5-flash'):
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise RuntimeError('GEMINI_API_KEY não configurada.')
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def run_query(self, user_query: str) -> Dict[str, Any]:
        if not user_query or not user_query.strip():
            return {"sucesso": False, "erro": "Pergunta vazia."}

        filtros = self._extract_filters(user_query)
        context_lines = self._retrieve_data(user_query, filtros)

        # Se não houver dados para o recorte solicitado, tentar uma amostra recente
        amostra_prefix = ""
        if not context_lines:
            amostra = self._fallback_context(n=10)
            if amostra:
                amostra_prefix = "[AMOSTRA RECENTE – sem correspondência direta à pergunta]\n"
                context_lines = amostra

        # Converte o contexto em texto estruturado
        dados_texto = (amostra_prefix + "\n".join(context_lines)) if context_lines else "(sem dados)"

        resposta_texto = self._generate_response(user_query, dados_texto)
        return {
            "sucesso": True,
            "resposta": resposta_texto,
            "contexto": context_lines,
        }

    def _extract_filters(self, q: str) -> Dict[str, Any]:
        ql = (q or '').lower()
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

        # Alvo principal
        if any(k in ql for k in ['parcela', 'parcelas']):
            filtros['alvo'] = 'parcelas'
        else:
            filtros['alvo'] = 'movimentos'

        # Datas relativas simples
        def inicio_mes(d):
            return d.replace(day=1)

        def inicio_semana(d):
            return d - timedelta(days=d.weekday())

        if 'mês atual' in ql or 'mes atual' in ql:
            filtros['data_inicio'] = inicio_mes(hoje)
            filtros['data_fim'] = hoje
        elif 'último mês' in ql or 'ultimo mes' in ql:
            m = hoje.month - 1 or 12
            y = hoje.year - 1 if hoje.month == 1 else hoje.year
            filtros['data_inicio'] = datetime(year=y, month=m, day=1).date()
            # fim do mês anterior
            if m == 12:
                filtros['data_fim'] = datetime(year=y, month=12, day=31).date()
            else:
                filtros['data_fim'] = (datetime(year=y, month=m+1, day=1).date() - timedelta(days=1))
        elif 'esta semana' in ql or 'semana atual' in ql:
            filtros['data_inicio'] = inicio_semana(hoje)
            filtros['data_fim'] = hoje
        elif 'este trimestre' in ql or 'trimestre atual' in ql:
            qm = ((hoje.month - 1)//3)*3 + 1
            filtros['data_inicio'] = datetime(year=hoje.year, month=qm, day=1).date()
            filtros['data_fim'] = hoje
        elif 'último trimestre' in ql or 'ultimo trimestre' in ql:
            qm = ((hoje.month - 1)//3)*3 + 1
            prev_qm = qm - 3
            y = hoje.year
            if prev_qm < 1:
                prev_qm += 12
                y -= 1
            inicio = datetime(year=y, month=prev_qm, day=1).date()
            fim = (datetime(year=y, month=prev_qm+3 if prev_qm+3 <= 12 else 1, day=1).date() - timedelta(days=1))
            filtros['data_inicio'] = inicio
            filtros['data_fim'] = fim
        elif 'este ano' in ql or 'ano atual' in ql:
            filtros['data_inicio'] = datetime(year=hoje.year, month=1, day=1).date()
            filtros['data_fim'] = hoje

        # Datas explícitas dd/mm/yyyy
        try:
            matches = re.findall(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', ql)
            if matches:
                def parse_pt(s):
                    s = s.replace('-', '/')
                    d, m, y = s.split('/')
                    d, m, y = int(d), int(m), int(y)
                    if y < 100: y += 2000
                    return datetime(year=y, month=m, day=d).date()
                if len(matches) >= 2:
                    filtros['data_inicio'] = parse_pt(matches[0])
                    filtros['data_fim'] = parse_pt(matches[1])
                elif len(matches) == 1:
                    filtros['data_inicio'] = parse_pt(matches[0])
        except Exception:
            pass

        # Faixas de valor
        def parse_val(txt):
            try:
                txt = txt.replace('.', '').replace(',', '.')
                return float(txt)
            except Exception:
                return None
        m_maior = re.search(r'(acima de|maior que)\s*(\d+[\.,]?\d*)', ql)
        m_menor = re.search(r'(menor que|até)\s*(\d+[\.,]?\d*)', ql)
        if m_maior:
            filtros['min_valor'] = parse_val(m_maior.group(2))
        if m_menor:
            filtros['max_valor'] = parse_val(m_menor.group(2))

        # Classificações mencionadas
        try:
            for c in Classificacao.query.all():
                nm = (c.descricao or '').lower()
                if nm and nm in ql:
                    filtros['classificacoes_incluidas'].append(c.descricao)
        except Exception:
            pass

        # Pessoas mencionadas
        try:
            for p in Pessoas.query.all():
                nm = (p.razaosocial or '').lower()
                fn = (p.fantasia or '').lower()
                if nm and nm in ql:
                    filtros['pessoas_nomes'].append(p.razaosocial)
                if fn and fn in ql:
                    filtros['pessoas_nomes'].append(p.fantasia)
        except Exception:
            pass

        return filtros

    def _retrieve_data(self, query: str, filtros: Dict[str, Any]) -> List[str]:
        """Recupera dados reais do banco e retorna como linhas de contexto estruturadas."""
        alvo = filtros.get('alvo') or 'movimentos'
        di = filtros.get('data_inicio')
        df = filtros.get('data_fim')
        minv = filtros.get('min_valor')
        maxv = filtros.get('max_valor')
        pessoas_n = set(filtros.get('pessoas_nomes') or [])
        cls_in = set(filtros.get('classificacoes_incluidas') or [])

        linhas: List[str] = []
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
                itens = q.order_by(ParcelasContas.datavencimento.desc()).limit(20).all()
                for p in itens:
                    linhas.append(
                        f"[parcelas:{p.idParcelasContas}] Parcela {p.identificacao}; Vencimento {p.datavencimento}; "
                        f"Valor {float(p.valorparcela):.2f}; Pago {float(p.valorpago or 0):.2f}; Saldo {float(p.valorsaldo or 0):.2f}; "
                        f"Status {p.statusparcela}"
                    )
            else:
                q = MovimentoContas.query.filter(MovimentoContas.status == 'ATIVO')
                if di:
                    q = q.filter(MovimentoContas.dataemissao >= di)
                if df:
                    q = q.filter(MovimentoContas.dataemissao <= df)
                if minv is not None:
                    q = q.filter(MovimentoContas.valortotal >= minv)
                if maxv is not None:
                    q = q.filter(MovimentoContas.valortotal <= maxv)
                itens = q.order_by(MovimentoContas.dataemissao.desc()).limit(20).all()
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
                    destinatario = m.faturado.razaosocial if m.faturado else '-'
                    classes = ', '.join([c.descricao for c in (m.classificacoes or [])]) or '-'
                    linhas.append(
                        f"[movimentos:{m.idMovimentoContas}] NF {m.numeronotafiscal or '-'}; Emissão {m.dataemissao}; "
                        f"Valor {float(m.valortotal):.2f}; Emitente {fornecedor}; Destinatário {destinatario}; "
                        f"Classificações {classes}; Descrição {(m.descricao or '').strip()}"
                    )
        except Exception:
            # Em caso de falha de consulta, retorna vazio para evitar quebrar a geração
            pass

        return linhas

    def _fallback_context(self, n: int = 10) -> List[str]:
        """Retorna uma amostra recente genérica para nunca deixar a resposta vazia."""
        linhas: List[str] = []
        try:
            itens = (
                MovimentoContas.query
                .filter(MovimentoContas.status == 'ATIVO')
                .order_by(MovimentoContas.dataemissao.desc())
                .limit(n)
                .all()
            )
            for m in itens:
                fornecedor = m.fornecedor_cliente.razaosocial if m.fornecedor_cliente else '-'
                destinatario = m.faturado.razaosocial if m.faturado else '-'
                classes = ', '.join([c.descricao for c in (m.classificacoes or [])]) or '-'
                linhas.append(
                    f"[movimentos:{m.idMovimentoContas}] NF {m.numeronotafiscal or '-'}; Emissão {m.dataemissao}; "
                    f"Valor {float(m.valortotal):.2f}; Emitente {fornecedor}; Destinatário {destinatario}; "
                    f"Classificações {classes}; Descrição {(m.descricao or '').strip()}"
                )
        except Exception:
            pass
        return linhas

    def _generate_response(self, user_query: str, retrieved_data: str) -> str:
        prompt = (
            "Você é um assistente de gestão financeira. Use EXCLUSIVAMENTE os DADOS a seguir (sem inventar nada). "
            "Responda em português do Brasil com tom casual, didático e amigável.\n\n"
            "Como responder:\n"
            "- Comece com um RESUMO curto (1–2 frases) dizendo o que foi encontrado.\n"
            "- Em seguida, traga DETALHES em tópicos simples: data, valor, emitente/destinatário e classificação.\n"
            "- Se a pergunta pedir 'maiores' ou 'top', foque nos registros de maior valor presentes nos DADOS.\n"
            "- Cite fontes quando útil usando o identificador entre colchetes (ex.: [movimentos:123], [parcelas:45]).\n"
            "- Caso os dados sejam insuficientes, diga isso de forma objetiva e cordial.\n\n"
            "Regras para ausência de dados:\n"
            "- Se os DADOS vierem com o rótulo 'AMOSTRA RECENTE – sem correspondência direta à pergunta', informe claramente que não há dados para a pergunta do usuário.\n"
            "  Depois, apresente a AMOSTRA apenas como referência (sem concluir que responde à pergunta).\n"
            "- Se não houver nenhum dado, diga que não há registros para o recorte solicitado e sugira ampliar período ou remover filtros.\n\n"
            f"DADOS:\n{retrieved_data}\n\n"
            f"PERGUNTA: {user_query}\n\n"
            "Formato: RESUMO; depois DETALHES em tópicos. Evite jargões e respostas confusas."
        )
        content = types.Content(role='user', parts=[types.Part.from_text(text=prompt)])

        def call_model(model_name: str) -> str:
            resp = self.client.models.generate_content(model=model_name, contents=[content])
            txt = (getattr(resp, 'text', None) or '').strip()
            if not txt:
                try:
                    txt = resp.candidates[0].content.parts[0].text.strip()
                except Exception:
                    txt = ''
            return txt

        def generate_with_retry(model_name: str, attempts: int = 3) -> str:
            last_err = None
            for i in range(attempts):
                try:
                    return call_model(model_name)
                except Exception as e:
                    last_err = e
                    msg = str(e).lower()
                    if '503' in msg or 'unavailable' in msg or 'overload' in msg:
                        delay = (0.5 * (2 ** i)) + random.uniform(0, 0.5)
                        time.sleep(delay)
                        continue
                    break
            if last_err:
                raise last_err
            return ''

        try:
            texto = generate_with_retry(self.model_name, attempts=3)
            if texto:
                return texto
        except Exception:
            pass

        for fallback_model in ['gemini-1.5-flash', 'gemini-1.5-pro']:
            try:
                texto = generate_with_retry(fallback_model, attempts=3)
                if texto:
                    return texto
            except Exception:
                continue

        linhas = [ln for ln in (retrieved_data.splitlines()) if ln.strip()][:3]
        resumo = (
            "Ops, o modelo está indisponível agora. Para não te deixar sem resposta, segue um resumo rápido do que encontrei:\n"
            + ('\n'.join(f"- {ln}" for ln in linhas) if linhas else "(sem dados)")
        )
        return resumo