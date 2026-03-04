from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.dialects.mysql import TINYINT
from .database import Base
from datetime import datetime


# ===============================================================
#  TABELA: USUÁRIO (NOC.TBL_USUARIOS)
#  ---------------------------------------------------------------
#  Finalidade:
#    - Tabela do banco NOC usada como "fonte de verdade" de usuários.
#    - Serve para validar matrícula e obter o nome do colaborador.
#    - Não é atualizada pela API, apenas consultada.
#
#  Observações:
#    - A tabela é externa ao módulo Nexus, por isso schema = "NOC".
#    - Campos como email e ativo podem ser reativados no futuro se necessário.
# ===============================================================
class Usuario(Base):
    __tablename__ = "TBL_USUARIOS"
    __table_args__ = {"schema": "NOC"}

    matricula = Column("MATRICULA", String(255), primary_key=True, index=True)
    nome = Column("NOME", String(200), nullable=False)
    acesso = Column("ACESSO", String(200))  # não usado como área, apenas informativo



# ===============================================================
#  TABELA: Áreas solicitantes (NEXUS.TBL_AREAS_SOLICITANTES)
#  ---------------------------------------------------------------
#  Finalidade:
#    - Domínio com todas as áreas disponíveis para seleção no front.
#    - Usada no momento da criação da solicitação.
#
#  Observações:
#    - id_area é chave primária e também chave estrangeira lógica
#      em TBL_SOLICITACOES_NEXUS.
# ===============================================================
class AreaSolicitante(Base):
    __tablename__ = "TBL_AREAS_SOLICITANTES"
    __table_args__ = {"schema": "NEXUS"}

    id_area = Column("ID_AREA", Integer, primary_key=True, index=True)
    nome_area = Column("NOME_AREA", String(100), unique=True, nullable=False)



# ===============================================================
#  TABELA: Solicitações (NEXUS.TBL_SOLICITACOES_NEXUS)
#  ---------------------------------------------------------------
#  Finalidade:
#    - Tabela principal do módulo Nexus.
#    - Registra todas as solicitações criadas pelos usuários.
#    - Controla: status, prioridade, área, datas, descrições.
#
#  Campos importantes:
#    - prioridade_usuario: enviada pelo solicitante (input humano)
#    - prioridade_area: redefinida pela área responsável (prioridade real)
#    - data_hora_abertura: preenchida automaticamente pelo backend
#    - id_area: referência à área solicitante
#
#  Observações:
#    - É recomendável deixar data_hora_abertura como NOT NULL.
# ===============================================================
class Solicitacao(Base):
    __tablename__ = "TBL_SOLICITACOES_NEXUS"
    __table_args__ = {"schema": "NEXUS"}

    # Identificador da solicitação
    id_solicitacao = Column("ID_SOLICITACAO", Integer, primary_key=True, index=True)

    # Matrícula do criador da solicitação
    matricula = Column("MATRICULA", String(100), nullable=False, index=True)

    # Tipo e status da solicitação
    id_tipo_solicitacao = Column("ID_TIPO_SOLICITACAO", Integer, nullable=False)
    id_status = Column("ID_STATUS", TINYINT, nullable=False, default=0)

    # Datas de abertura e baixa (fechamento)
    data_hora_abertura = Column("DATA_HORA_ABERTURA", DateTime, nullable=False)
    data_hora_baixa = Column("DATA_HORA_BAIXA", DateTime)

    # Prioridades
    prioridade_usuario = Column("PRIORIDADE_USUARIO", TINYINT, default=0)
    prioridade_area = Column("PRIORIDADE_AREA", TINYINT, default=0)

    # Área do solicitante (domínio)
    id_area = Column("ID_AREA", Integer, nullable=False)

    # Descrições da solicitação
    descricao_solicitacao = Column("DESCRICAO_SOLICITACAO", Text, nullable=False)
    acompanhamento_area_solicitante = Column("ACOMPANHAMENTO_AREA_SOLICITANTE", Text)



# ===============================================================
#  TABELA: Arquivos anexados (NEXUS.TBL_ARQUIVOS)
#  ---------------------------------------------------------------
#  Finalidade:
#    - Armazena metadados dos arquivos enviados pelo usuário.
#    - Relaciona arquivo → solicitação via ID_SOLICITACAO.
#    - Permite que o front liste todos os anexos de uma solicitação.
#
#  Observações:
#    - ID_SOLICITACAO agora corretamente como nullable=False.
#    - Conteúdo do arquivo NÃO é armazenado no banco (boa prática).
# ===============================================================
class Arquivo(Base):

    __tablename__ = "TBL_ARQUIVOS"
    __table_args__ = {"schema": "NEXUS"}

    ID_ARQUIVO = Column("ID_ARQUIVO", Integer, primary_key=True, autoincrement=True, index=True)

    # Relacionamento lógico com a tabela de solicitações
    ID_SOLICITACAO = Column("ID_SOLICITACAO", Integer, nullable=False)

    # Metadados do arquivo físico
    NOME_ORIGINAL = Column("NOME_ORIGINAL", String(255), nullable=False)
    NOME_ARQUIVO = Column("NOME_ARQUIVO", String(255), nullable=False)
    CAMINHO = Column("CAMINHO", String(500), nullable=False)
    CONTENT_TYPE = Column("CONTENT_TYPE", String(100))
    TAMANHO_BYTES = Column("TAMANHO_BYTES", Integer)
    DATA_UPLOAD = Column("DATA_UPLOAD", DateTime)



# ===============================================================
#  TABELA: Prioridades (NEXUS.TBL_PRIORIDADES)
#  ---------------------------------------------------------------
#  Finalidade:
#    - Domínio contendo valores de prioridade (0 a 3).
#    - Permite padronização e governança para PRIORIDADE_USUARIO e PRIORIDADE_AREA.
#
#  Observações:
#    - Pode ser usada para retornar nome da prioridade no /buscar (JOIN).
# ===============================================================
class Prioridade(Base):
    __tablename__ = "TBL_PRIORIDADES"
    __table_args__ = {"schema": "NEXUS"}

    id_prioridade = Column("ID_PRIORIDADE", Integer, primary_key=True)
    descricao = Column("DESCRICAO", String(50), nullable=False)
