import os
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
)
from sqlalchemy.orm import Session

from .app.database import get_db
from .app import models, schemas

from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text
import oracledb
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from datetime import datetime

print(models.Usuario.__table__)

load_dotenv()

router = APIRouter()
# extrai "PAGINA_SOLICITACAO_NEXUS" do nome do arquivo
file = os.path.basename(__file__)[:-3]

# -------------------------------------------------------------------
# Pasta de uploads_solicitacao_Nexus (dentro do projeto uploads_solicitacao_Nexus)
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads_solicitacao_Nexus")  # pasta onde os arquivos serão salvos
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------- POST /PAGINA_SOLICITACAO_NEXUS/criar ----------
@router.post(
    f"/{file}/criar",
    response_model=schemas.SolicitacaoRead,
    status_code=status.HTTP_201_CREATED,
)
async def criar_solicitacao(
    dados: schemas.SolicitacaoCreate,
    db: Session = Depends(get_db),
):

    # 1) Validar área solicitante
    area_valida = (
        db.query(models.AreaSolicitante)
        .filter(models.AreaSolicitante.nome_area == dados.area_solicitante)
        .first()
    )

    if not area_valida:
        raise HTTPException(
            status_code=400,
            detail="Área solicitante inválida.",
        )

    # 2) Validar prioridade do usuário (usando TBL_PRIORIDADES)
    prioridade_valida = (
        db.query(models.Prioridade)
        .filter(models.Prioridade.id_prioridade == dados.prioridade_usuario)
        .first()
    )

    if not prioridade_valida:
        raise HTTPException(
            status_code=400,
            detail="Prioridade do usuário inválida."
        )

    # 3) Criar solicitação (AGORA SIM UMA VEZ SÓ)
    nova = models.Solicitacao(
        matricula=dados.matricula,
        id_tipo_solicitacao=dados.id_tipo_solicitacao,
        prioridade_usuario=dados.prioridade_usuario,
        descricao_solicitacao=dados.descricao_solicitacao,
        id_status=0,
        id_area=area_valida.id_area,
        data_hora_abertura=datetime.now(),
        data_hora_baixa=None,
    )

    db.add(nova)
    db.commit()
    db.refresh(nova)

    return nova



# ---------- POST /PAGINA_SOLICITACAO_NEXUS/buscar ----------
@router.post(
    f"/{file}/buscar", response_model=List[schemas.SolicitacaoComUsuario]
)
async def buscar_solicitacoes(
    filtro: schemas.BuscarPeriodo,
    db: Session = Depends(get_db),
):
    """
    Busca solicitações por período (DATA_HORA_ABERTURA) e faz JOIN com TBL_USUARIOS (NOC)
    usando a coluna MATRICULA.
    """

    # 1) Monta a query com JOIN em Usuário (LEFT JOIN)
    query = (
        db.query(models.Solicitacao, models.Usuario)
        .join(
            models.Usuario,
            models.Usuario.matricula == models.Solicitacao.matricula,
            isouter=True,  # se não achar usuário, ainda retorna a solicitação
        )
        .filter(
            models.Solicitacao.data_hora_abertura >= filtro.data_inicio,
            models.Solicitacao.data_hora_abertura <= filtro.data_fim,
        )
    )

    # 2) Executa a query
    rows = query.all()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma solicitação encontrada no período informado.",
        )

    resultado: List[schemas.SolicitacaoComUsuario] = []

    # 3) Monta a resposta no formato do schema Pydantic
    for solic, user in rows:

        # (opcional, mas recomendado) – garante que ID_AREA nunca esteja nulo
        if solic.id_area is None:
            raise HTTPException(
                status_code=500,
                detail=f"Registro ID_SOLICITACAO={solic.id_solicitacao} está sem ID_AREA definido no banco."
            )

        item = schemas.SolicitacaoComUsuario(
            id_solicitacao=solic.id_solicitacao,
            matricula=solic.matricula,
            id_tipo_solicitacao=solic.id_tipo_solicitacao,
            id_status=solic.id_status,
            data_hora_abertura=solic.data_hora_abertura,
            data_hora_baixa=solic.data_hora_baixa,
            prioridade_usuario=solic.prioridade_usuario,
            prioridade_area=solic.prioridade_area,
            id_area=solic.id_area,  # ← AGORA ESTÁ SENDO PREENCHIDO
            descricao_solicitacao=solic.descricao_solicitacao,
            acompanhamento_area_solicitante=solic.acompanhamento_area_solicitante,
            usuario=schemas.UsuarioRead(
                matricula=user.matricula,
                nome=user.nome,
            )
            if user
            else None,
        )

        resultado.append(item)

    return resultado


# ---------- GET /PAGINA_SOLICITACAO_NEXUS/areas ----------
@router.get(f"/{file}/areas", response_model=List[schemas.AreaRead])
async def listar_areas(db: Session = Depends(get_db)):
    """
    Retorna todas as áreas cadastradas em TBL_AREAS_SOLICITANTES.
    Essa lista é usada pelo front para montar o dropdown de áreas solicitantes.
    """
    areas = db.query(models.AreaSolicitante).all()
    return areas


# ---------- GET /PAGINA_SOLICITACAO_NEXUS/prioridades ----------
@router.get(f"/{file}/prioridades", response_model=List[schemas.PrioridadeRead])
async def listar_prioridades(db: Session = Depends(get_db)):
    """
    Retorna a lista de prioridades cadastradas em TBL_PRIORIDADES.
    Usado pelo front para montar o dropdown de prioridade (Normal, Média, Alta, Crítica).
    """
    prioridades = db.query(models.Prioridade).order_by(models.Prioridade.id_prioridade).all()
    return prioridades



# ===================================================================
# NOVAS ROTAS: UPLOAD E LISTAGEM DE ARQUIVOS
# ===================================================================

# ---------- POST /PAGINA_SOLICITACAO_NEXUS/upload-arquivo ----------
@router.post(
    f"/{file}/upload-arquivo",
    response_model=schemas.ArquivoOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_arquivo(
    id_solicitacao: int,
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Recebe um arquivo (qualquer tipo: imagem, PDF, planilha, etc),
    salva na pasta 'uploads_solicitacao_Nexus' e registra um vínculo na tabela ARQUIVOS
    com a solicitação (ID_SOLICITACAO).
    """

    # Gera nome único para o arquivo
    _, ext = os.path.splitext(arquivo.filename)
    novo_nome = f"{os.urandom(16).hex()}{ext}"

    caminho_fisico = os.path.join(UPLOAD_DIR, novo_nome)
    caminho_url = f"/uploads_solicitacao_Nexus/{novo_nome}"  # usado pelo front

    conteudo = await arquivo.read()

    # Salvar arquivo fisicamente
    try:
        with open(caminho_fisico, "wb") as f:
            f.write(conteudo)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao salvar arquivo em disco: {str(e)}",
        )

    # Criar registro no banco
    arquivo_db = models.Arquivo(
        ID_SOLICITACAO=id_solicitacao,
        NOME_ORIGINAL=arquivo.filename,
        NOME_ARQUIVO=novo_nome,
        CAMINHO=caminho_url,
        CONTENT_TYPE=arquivo.content_type,
        TAMANHO_BYTES=len(conteudo),
        DATA_UPLOAD=datetime.now(),  # o banco já preenche com CURRENT_TIMESTAMP, mas é bom ter aqui também para garantir que o campo não fique vazio. Se quiser confiar só no banco, pode remover essa linha e deixar o campo DATA_UPLOAD sem valor aqui.
        # DATA_UPLOAD: o banco já preenche com CURRENT_TIMESTAMP
    )

    db.add(arquivo_db)
    db.commit()
    # db.refresh(arquivo_db)
    

    return arquivo_db

print(models.Arquivo.__table__)
print(models.Arquivo.__mapper__.primary_key)


# ---------- GET /PAGINA_SOLICITACAO_NEXUS/arquivos/{id_solicitacao} ----------
@router.get(
    f"/{file}/arquivos/{{id_solicitacao}}",
    response_model=List[schemas.ArquivoOut],
)
async def listar_arquivos_por_solicitacao(
    id_solicitacao: int,
    db: Session = Depends(get_db),
):
    """
    Retorna todos os arquivos vinculados a uma solicitação (ID_SOLICITACAO)
    a partir da tabela ARQUIVOS.
    """
    arquivos = (
        db.query(models.Arquivo)
        .filter(models.Arquivo.ID_SOLICITACAO == id_solicitacao)
        .all()
    )
    return arquivos
print(models.Arquivo.__table__)
print(models.Arquivo.__mapper__.primary_key)



# ---------- POST /PAGINA_SOLICITACAO_NEXUS/finalizar/{id_solicitacao} ----------
@router.post(f"/{file}/finalizar/{{id_solicitacao}}")
async def finalizar_solicitacao(id_solicitacao: int, db: Session = Depends(get_db)):
    """
    Finaliza a solicitação:
    - Define data_hora_baixa = agora
    - Atualiza o id_status para 'concluído' (ajuste conforme seu sistema)
    """

    solic = (
        db.query(models.Solicitacao)
        .filter(models.Solicitacao.id_solicitacao == id_solicitacao)
        .first()
    )

    if not solic:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    # Atualiza os campos de finalização
    solic.data_hora_baixa = datetime.now()
    solic.id_status = 3  # ajuste para o status correto da tabela

    db.commit()
    db.refresh(solic)

    return {"mensagem": "Solicitação finalizada com sucesso!", "id": solic.id_solicitacao}


# Teste -> GET /PAGINA_SOLICITACAO_NEXUS/solicitacao/{id}

@router.get(f"/{file}/solicitacao/{{id_solicitacao}}", response_model=schemas.SolicitacaoComUsuario)
async def obter_solicitacao(id_solicitacao: int, db: Session = Depends(get_db)):

    solic = (
        db.query(models.Solicitacao, models.Usuario)
        .join(models.Usuario,
              models.Usuario.matricula == models.Solicitacao.matricula,
              isouter=True)
        .filter(models.Solicitacao.id_solicitacao == id_solicitacao)
        .first()
    )

    if not solic:
        raise HTTPException(404, "Solicitação não encontrada")

    solic, user = solic

    return schemas.SolicitacaoComUsuario(
        id_solicitacao=solic.id_solicitacao,
        matricula=solic.matricula,
        id_tipo_solicitacao=solic.id_tipo_solicitacao,
        id_status=solic.id_status,
        data_hora_abertura=solic.data_hora_abertura,
        data_hora_baixa=solic.data_hora_baixa,
        prioridade_usuario=solic.prioridade_usuario,
        prioridade_area=solic.prioridade_area,
        id_area=solic.id_area,
        descricao_solicitacao=solic.descricao_solicitacao,
        acompanhamento_area_solicitante=solic.acompanhamento_area_solicitante,
        usuario=schemas.UsuarioRead(
            matricula=user.matricula,
            nome=user.nome,
        ) if user else None
    )



# Teste -> GET /PAGINA_SOLICITACAO_NEXUS/prioridades
@router.get(f"/{file}/prioridades", response_model=List[schemas.PrioridadeRead])
async def listar_prioridades(db: Session = Depends(get_db)):
    return db.query(models.Prioridade).all()
