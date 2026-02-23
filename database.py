from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import urllib.parse
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()  # isso lê o .env e preenche os os.getenv(...)

#configurações do banco NOC
NOC_USER = "dev"
NOC_HOST = "10.126.112.251"
NOC_PORT = 3306
NOC_DB = "NEXUS"

#senha em uma variável de ambiente chamada noc_password
noc_password = os.getenv('noc_password')

if not noc_password:
    raise RuntimeError('A variável de ambiente noc_password não está definida.')

# senhas com caracteres especiais (@, !, %, etc.), fazemos URL encode
# encoded_pwd = urllib.parse.quote_plus(noc_password)
encoded_pwd = noc_password

DATABASE_URL = (
    f"mysql+pymysql://{NOC_USER}:{encoded_pwd}@{NOC_HOST}:{NOC_PORT}/{NOC_DB}"
)


# criação do "motor" de conexão com o banco
engine = create_engine(
    DATABASE_URL,
    echo=False,        # colocar True para ver os SQLs no terminal
    pool_pre_ping=True
)

#fábrica de sessões
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

#classe base para os modelos ORM
Base = declarative_base()

#dependência que o FastAPI usa para fornecer "db" nos endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()