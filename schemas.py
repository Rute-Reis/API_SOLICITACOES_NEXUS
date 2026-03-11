from pydantic import BaseModel
# from pydantic import Field
from typing import Optional
from datetime import datetime

# ---------- SAÍDA: USUÁRIO ----------
class UsuarioRead(BaseModel):
    matricula: str
    nome: str
    # email: Optional[str] = None
    # acesso: Optional[str] = None
    # ativo: int

    class Config:
        orm_mode = True

# ---------- ENTRADA: CRIAR SOLICITAÇÃO ----------
class SolicitacaoCreate(BaseModel):
    matricula: str
    id_tipo_solicitacao: int
    prioridade_usuario: int
    descricao_solicitacao: str
    id_area: int  # obrigatório (vem do dropdown do front)
    previsao_entrega: Optional[datetime] = None  # nova previsão de entrega (opcional)


# ---------- SAÍDA: SOLICITAÇÃO (USADA EM /solicitacoes/criar) ----------
class SolicitacaoRead(BaseModel):
    id_solicitacao: int
    matricula: str
    id_tipo_solicitacao: int
    id_status: int

    data_hora_abertura: datetime
    data_hora_baixa: Optional[datetime] = None

    prioridade_usuario: int
    prioridade_area: int

    id_area: int
    descricao_solicitacao: str
    # acompanhamento_area_solicitante: Optional[str] = None
    previsao_entrega: Optional[datetime] = None  # nova previsão de entrega

    # class SolicitacaoRead(BaseModel):
    #     id_area: int
    #     area_solicitante: Optional[str] = None
    #     descricao_solicitacao: str

    class Config:
        orm_mode = True



# ---------- SAÍDA: SOLICITAÇÃO + USUÁRIO (USADA EM /solicitacoes/buscar) ----------
class SolicitacaoComUsuario(SolicitacaoRead):
    usuario: Optional[UsuarioRead] = None


# ---------- ENTRADA: BUSCAR POR PERÍODO (USADA EM /solicitacoes/buscar) ----------
class BuscarPeriodo(BaseModel):
    data_inicio: datetime
    data_fim: datetime
    prioridade_usuario: Optional[int] = None
    prioridade_area: Optional[int] = None



# ---------- SAÍDA: ÁREA (USADA EM /solicitacoes/areas) ----------
class AreaRead(BaseModel):
    id_area: int
    nome_area: str

    class Config:
        orm_mode = True


# ---------- SAÍDA: PRIORIDADE (usada em /solicitacoes/prioridades) ----------
class PrioridadeRead(BaseModel):
    id_prioridade: int
    descricao: str

    class Config:
        orm_mode = True


# ---------- SAÍDA: ARQUIVOS (USADA EM /solicitacoes/upload-arquivo e listar) ----------
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

# ---------- SAÍDA: LISTA DE ARQUIVOS POR SOLICITAÇÃO ----------
class ArquivoList(BaseModel):
    arquivos: list[ArquivoOut]


# ---------- ENTRADA: ATUALIZAR STATUS (USADA EM /solicitacoes/atualizar-status) ----------
class AtualizarStatus(BaseModel):
    novo_status: int




