import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def setup_postgresql():
    """Configura o PostgreSQL criando o banco de dados e executando o schema"""
    
    # Tentar diferentes configurações de conexão
    connection_configs = [
        {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'password': 'admin'
        },
        {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'password': 'postgres'
        },
        {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'password': ''
        }
    ]
    
    connection = None
    
    for config in connection_configs:
        try:
            print(f"Tentando conectar com usuário: {config['user']}, senha: {'***' if config['password'] else 'sem senha'}")
            
            # Conectar ao PostgreSQL (banco padrão)
            connection = psycopg2.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database='postgres'  # Conectar ao banco padrão primeiro
            )
            connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            print("✅ Conexão estabelecida com sucesso!")
            
            # Criar cursor
            cursor = connection.cursor()
            
            # Verificar se o banco já existe e removê-lo se necessário
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'nf_ai_dados'")
            exists = cursor.fetchone()
            
            if exists:
                print("🗑️ Removendo banco existente...")
                cursor.execute("DROP DATABASE nf_ai_dados")
                print("✅ Banco existente removido")
            
            # Criar banco de dados
            cursor.execute("CREATE DATABASE nf_ai_dados")
            print("✅ Banco de dados 'nf_ai_dados' criado com sucesso!")
            
            # Fechar conexão com banco padrão
            cursor.close()
            connection.close()
            
            # Conectar ao banco específico para criar tabelas
            connection = psycopg2.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database='nf_ai_dados'
            )
            connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            # Executar script de criação das tabelas
            with open('database_schema.sql', 'r', encoding='utf-8') as file:
                schema_sql = file.read()
            
            cursor = connection.cursor()
            cursor.execute(schema_sql)
            print("✅ Schema do banco criado com sucesso!")
            
            # Atualizar arquivo .env com as credenciais corretas
            update_env_file(config)
            
            cursor.close()
            connection.close()
            
            print("🎉 PostgreSQL configurado com sucesso!")
            return True
            
        except psycopg2.Error as e:
            print(f"❌ Erro de PostgreSQL: {e}")
            if connection:
                connection.close()
            continue
        except Exception as e:
            print(f"❌ Erro geral: {e}")
            if connection:
                connection.close()
            continue
    
    print("❌ Não foi possível conectar ao PostgreSQL com nenhuma configuração")
    return False

def update_env_file(config):
    """Atualiza o arquivo .env com as credenciais corretas"""
    database_url = f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/nf_ai_dados"
    
    env_content = f"""# Configurações do Banco de dados PostgreSQL
DATABASE_URL={database_url}
DB_HOST={config['host']}
DB_PORT={config['port']}
DB_NAME=nf_ai_dados
DB_USER={config['user']}
DB_PASSWORD={config['password']}

# Chave da API Gemini
GEMINI_API_KEY=AIzaSyAvag5ZD7lFydA4NVcM6a6AsMjUaSfmk7A

# Configurações da aplicação Flask
FLASK_ENV=development
FLASK_DEBUG=True"""
    
    with open('.env', 'w', encoding='utf-8') as file:
        file.write(env_content)
    
    print("✅ Arquivo .env atualizado com credenciais corretas")

if __name__ == "__main__":
    setup_postgresql()