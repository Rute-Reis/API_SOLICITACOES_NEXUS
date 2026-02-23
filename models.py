from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.dialects.mysql import TINYINT
from .database import Base
from datetime import datetime


class Usuario(Base):
    """
    tabela de usuários do banco NOC.
    usada apenas para validar e puxar matricula.
    """
    __tablename__ = "TBL_USUARIOS"

    matricula = Column("MATRICULA", String(255), primary_key=True, index=True)
    nome = Column("NOME", String(200), nullable=False)
    email = Column("EMAIL", String(200))
    acesso = Column("ACESSO", String(200))  # não usado como área
    ativo = Column("ATIVO", TINYINT, nullable=False, default=1)


class AreaSolicitante(Base):
    """
    tabela de domínio com as áreas definidas .
    """
    __tablename__ = "TBL_AREAS_SOLICITANTES"
    __table_args__ = {"schema": "NEXUS"}  # essa tabela está em outro schema, então preciso especificar

    id_area = Column("ID_AREA", Integer, primary_key=True, index=True)
    nome_area = Column("NOME_AREA", String(100), unique=True, nullable=False)


class Solicitacao(Base):
    """
    Tabela final de solicitações.
    Aqui guardamos:
    - MATRÍCULA do solicitante
    - ÁREA_SOLICITANTE escolhida no front (domínio controlado)
    """
    __tablename__ = "TBL_SOLICITACOES_NEXUS"
    __table_args__ = {"schema": "NEXUS"} # essa tabela está em outro schema, então preciso especificar

    id_solicitacao = Column("ID_SOLICITACAO", Integer, primary_key=True, index=True)
    matricula = Column("MATRICULA", String(100), nullable=False, index=True)

    id_tipo_solicitacao = Column("ID_TIPO_SOLICITACAO", Integer, nullable=False)
    id_status = Column("ID_STATUS", TINYINT, nullable=False, default=0)

    data_hora_abertura = Column("DATA_HORA_ABERTURA", DateTime)
    data_hora_baixa = Column("DATA_HORA_BAIXA", DateTime)

    prioridade_usuario = Column("PRIORIDADE_USUARIO", TINYINT, default=0)
    prioridade_area = Column("PRIORIDADE_AREA", TINYINT, default=0)

    id_area = Column("ID_AREA", Integer, nullable=False)

    descricao_solicitacao = Column("DESCRICAO_SOLICITACAO", Text, nullable=False)
    acompanhamento_area_solicitante = Column("ACOMPANHAMENTO_AREA_SOLICITANTE", Text)
    
class Arquivo(Base):

    __tablename__ = "TBL_ARQUIVOS"
    __table_args__ = {"schema": "NEXUS"}

    ID_ARQUIVO = Column("ID_ARQUIVO", Integer, primary_key=True, autoincrement=True, index=True)
    ID_SOLICITACAO = Column("ID_SOLICITACAO", Integer, nullable=True)

    NOME_ORIGINAL = Column("NOME_ORIGINAL", String(255), nullable=False)
    NOME_ARQUIVO = Column("NOME_ARQUIVO", String(255), nullable=False)
    CAMINHO = Column("CAMINHO", String(500), nullable=False)
    CONTENT_TYPE = Column("CONTENT_TYPE", String(100))
    TAMANHO_BYTES = Column("TAMANHO_BYTES", Integer)
    DATA_UPLOAD = Column("DATA_UPLOAD", DateTime)
