from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ---------- SAÍDA: USUÁRIO ----------
class UsuarioRead(BaseModel):
    matricula: str
    nome: str

    class Config:
        from_attributes = True


# ---------- SAÍDA: ARQUIVO ----------
class ArquivoOut(BaseModel):
    ID_ARQUIVO: int
    ID_SOLICITACAO: Optional[int]
    NOME_ORIGINAL: str
    NOME_ARQUIVO: str
    CAMINHO: str
    CONTENT_TYPE: Optional[str] = None
    TAMANHO_BYTES: Optional[int] = None
    DATA_UPLOAD: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- ENTRADA: CRIAR SOLICITAÇÃO ----------
class SolicitacaoCreate(BaseModel):
    matricula: str
    id_tipo_solicitacao: int
    prioridade_usuario: int
    titulo_solicitacao: str
    descricao_solicitacao: str
    id_area: int
    previsao_entrega: Optional[datetime] = None
    comentario_admin: Optional[str] = None
    responsavel_solicitacao: Optional[str] = None


# ---------- SAÍDA: SOLICITAÇÃO ----------
class SolicitacaoRead(BaseModel):
    id_solicitacao: int
    matricula: str
    id_tipo_solicitacao: int
    id_status: int
    data_hora_abertura: datetime
    data_hora_baixa: Optional[datetime] = None
    previsao_entrega: Optional[datetime] = None
    prioridade_usuario: int
    prioridade_area: int
    id_area: int
    descricao_solicitacao: str
    comentario_admin: Optional[str] = None
    titulo_solicitacao: Optional[str] = None
    responsavel_solicitacao: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- SAÍDA: SOLICITAÇÃO + USUÁRIO + ARQUIVO(S) ----------
class SolicitacaoComUsuario(SolicitacaoRead):
    usuario: Optional[UsuarioRead] = None
    arquivo: Optional[List[ArquivoOut]] = None


# --------- SAÍDA: PAGINAÇÃO DE SOLICITAÇÕES ----------
class PaginacaoSolicitacao(BaseModel):
    data: List[SolicitacaoComUsuario]
    page: int
    page_size: int
    total: int
    total_pages: int


# ---------- ENTRADA: BUSCA POR PERÍODO ----------
class BuscarPeriodo(BaseModel):
    data_inicio: datetime
    data_fim: datetime
    prioridade_usuario: Optional[int] = None
    prioridade_area: Optional[int] = None


# ---------- SAÍDA: ÁREA ----------
class AreaRead(BaseModel):
    id_area: int
    nome_area: str

    class Config:
        from_attributes = True


# ---------- SAÍDA: PRIORIDADE ----------
class PrioridadeRead(BaseModel):
    id_prioridade: int
    descricao: str

    class Config:
        from_attributes = True


# ---------- SAÍDA: LISTA DE ARQUIVOS ----------
class ArquivoList(BaseModel):
    arquivo: List[ArquivoOut]

    class Config:
        from_attributes = True


# ---------- ENTRADAS DE UPDATE ----------
class AtualizarStatus(BaseModel):
    novo_status: int


class AtualizarPrevisaoEntrega(BaseModel):
    nova_previsao: datetime


class AtualizarPrioridadeArea(BaseModel):
    prioridade_area: int

    class Config:
        from_attributes = True


class AtualizarComentarioAdmin(BaseModel):
    comentario_admin: str

    class Config:
        from_attributes = True


class AtualizarDescricaoSolicitacao(BaseModel):
    descricao_solicitacao: str

    class Config:
        from_attributes = True
