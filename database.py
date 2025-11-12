from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import Table, Column, Integer, ForeignKey

db = SQLAlchemy()

# Tabela de relacionamento many-to-many
movimento_classificacao = Table('MovimentoContas_has_Classificacao',
    db.Model.metadata,
    Column('MovimentoContas_idMovimentoContas', Integer, ForeignKey('movimento_contas.idMovimentoContas'), primary_key=True),
    Column('Classificacao_idClassificacao', Integer, ForeignKey('classificacao.idClassificacao'), primary_key=True)
)

class Pessoas(db.Model):
    __tablename__ = 'pessoas'
    
    idPessoas = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tipo = db.Column(db.String(45), nullable=False)
    razaosocial = db.Column(db.String(150), nullable=False)
    fantasia = db.Column(db.String(150))
    documento = db.Column(db.String(45), nullable=False)
    status = db.Column(db.String(45), default='ATIVO')
    
    # Relacionamentos
    movimentos_fornecedor = db.relationship('MovimentoContas', foreign_keys='MovimentoContas.Pessoas_idFornecedorCliente', backref='fornecedor_cliente')
    movimentos_faturado = db.relationship('MovimentoContas', foreign_keys='MovimentoContas.Pessoas_idFaturado', backref='faturado')
    
    def to_dict(self):
        return {
            'idPessoas': self.idPessoas,
            'tipo': self.tipo,
            'razaosocial': self.razaosocial,
            'fantasia': self.fantasia,
            'documento': self.documento,
            'status': self.status
        }

class Classificacao(db.Model):
    __tablename__ = 'classificacao'
    
    idClassificacao = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tipo = db.Column(db.String(45), nullable=False)
    descricao = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(45), default='ATIVO')
    
    def to_dict(self):
        return {
            'idClassificacao': self.idClassificacao,
            'tipo': self.tipo,
            'descricao': self.descricao,
            'status': self.status
        }

class ParcelasContas(db.Model):
    __tablename__ = 'parcelas_contas'
    
    idParcelasContas = db.Column(db.Integer, primary_key=True, autoincrement=True)
    identificacao = db.Column(db.String(45), nullable=False)
    datavencimento = db.Column(db.Date, nullable=False)
    valorparcela = db.Column(db.Numeric(10, 2), nullable=False)
    valorpago = db.Column(db.Numeric(10, 2), default=0.00)
    valorsaldo = db.Column(db.Numeric(10, 2), nullable=False)
    statusparcela = db.Column(db.String(45), default='PENDENTE')
    
    def to_dict(self):
        return {
            'idParcelasContas': self.idParcelasContas,
            'identificacao': self.identificacao,
            'datavencimento': self.datavencimento.strftime('%d/%m/%Y') if self.datavencimento else None,
            'valorparcela': float(self.valorparcela) if self.valorparcela else 0,
            'valorpago': float(self.valorpago) if self.valorpago else 0,
            'valorsaldo': float(self.valorsaldo) if self.valorsaldo else 0,
            'statusparcela': self.statusparcela
        }

class MovimentoContas(db.Model):
    __tablename__ = 'movimento_contas'
    
    idMovimentoContas = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tipo = db.Column(db.String(45), nullable=False)
    numeronotafiscal = db.Column(db.String(45))
    dataemissao = db.Column(db.Date, nullable=False)
    descricao = db.Column(db.String(300))
    status = db.Column(db.String(45), default='ATIVO')
    valortotal = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Chaves estrangeiras
    Pessoas_idFornecedorCliente = db.Column(db.Integer, db.ForeignKey('pessoas.idPessoas'), nullable=False)
    Pessoas_idFaturado = db.Column(db.Integer, db.ForeignKey('pessoas.idPessoas'), nullable=False)
    
    # Relacionamento many-to-many com Classificacao
    classificacoes = db.relationship('Classificacao', secondary=movimento_classificacao, backref='movimentos')
    
    def to_dict(self):
        return {
            'idMovimentoContas': self.idMovimentoContas,
            'tipo': self.tipo,
            'numeronotafiscal': self.numeronotafiscal,
            'dataemissao': self.dataemissao.strftime('%d/%m/%Y') if self.dataemissao else None,
            'descricao': self.descricao,
            'status': self.status,
            'valortotal': float(self.valortotal) if self.valortotal else 0,
            'fornecedor_cliente': self.fornecedor_cliente.to_dict() if self.fornecedor_cliente else None,
            'faturado': self.faturado.to_dict() if self.faturado else None,
            'classificacoes': [c.to_dict() for c in self.classificacoes]
        }

def init_db(app):
    """Inicializa o banco de dados"""
    db.init_app(app)
    
    try:
        with app.app_context():
            # Criar todas as tabelas
            db.create_all()
            
            # Inserir classificações padrão se não existirem
            classificacoes_padrao = [
                ('DESPESA', 'INSUMOS AGRÍCOLAS'),
                ('DESPESA', 'MANUTENÇÃO E OPERAÇÃO'),
                ('DESPESA', 'RECURSOS HUMANOS'),
                ('DESPESA', 'SERVIÇOS OPERACIONAIS'),
                ('DESPESA', 'INFRAESTRUTURA E UTILIDADES'),
                ('DESPESA', 'ADMINISTRATIVAS'),
                ('DESPESA', 'SEGUROS E PROTEÇÃO'),
                ('DESPESA', 'IMPOSTOS E TAXAS'),
                ('DESPESA', 'INVESTIMENTOS'),
                ('DESPESA', 'OUTROS'),
                ('RECEITA', 'VENDAS'),
                ('RECEITA', 'SERVIÇOS'),
                ('RECEITA', 'OUTRAS RECEITAS')
            ]
            
            for tipo, descricao in classificacoes_padrao:
                classificacao_existente = Classificacao.query.filter_by(tipo=tipo, descricao=descricao).first()
                if not classificacao_existente:
                    nova_classificacao = Classificacao(tipo=tipo, descricao=descricao, status='ATIVO')
                    db.session.add(nova_classificacao)
            
            db.session.commit()
            print("✅ Banco de dados inicializado com sucesso!")
    except Exception as e:
        print(f"⚠️  AVISO: Não foi possível conectar ao banco de dados PostgreSQL")
        print(f"   Erro: {str(e)}")
        print(f"   A aplicação iniciará sem conexão com o banco de dados.")
        print(f"   Configure o arquivo .env ou variáveis de ambiente para conectar ao banco.")
        print()