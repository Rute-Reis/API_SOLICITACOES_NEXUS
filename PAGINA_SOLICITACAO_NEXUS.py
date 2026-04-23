import os
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    BackgroundTasks
)
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from datetime import datetime

from .app.database import get_db
from .app import models, schemas
from .notificacoes import registrar_evento

from .dispatcher_notificacoes import enviar_notificacao_por_id

# prints para debug das tabelas
print(models.Usuario.__table__)
print("DEBUG - Colunas de Solicitacao:", models.Solicitacao.__table__.columns.keys())
print("DEBUG - Atributos de Solicitacao:", [attr.key for attr in models.Solicitacao.__mapper__.attrs])
print('DEBUG - Arquivos - Tabela:', models.Arquivo.__table__.columns.keys())

load_dotenv()

router = APIRouter()

# extrai "PAGINA_SOLICITACAO_NEXUS" do nome do arquivo
file = os.path.basename(__file__)[:-3]

# -------------------------------------------------------------------
# Pasta de uploads_solicitacao_Nexus (dentro do projeto uploads_solicitacao_Nexus)
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads_solicitacao_Nexus")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------- POST /PAGINA_SOLICITACAO_NEXUS/criar ----------
@router.post(
    f"/{file}/criar",
    response_model=schemas.SolicitacaoRead,
    status_code=status.HTTP_201_CREATED,
)
async def criar_solicitacao(
    dados: schemas.SolicitacaoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):

    # 1) Validar área solicitante (por ID)
    area = (
        db.query(models.AreaSolicitante)
        .filter(models.AreaSolicitante.id_area == dados.id_area)
        .first()
    )
    if not area:
        raise HTTPException(
            status_code=400,
            detail="Área solicitante inválida.",
        )

    # 2) Validar prioridade do usuário (usando TBL_PRIORIDADES)
    prioridade = (
        db.query(models.Prioridade)
        .filter(models.Prioridade.id_prioridade == dados.prioridade_usuario)
        .first()
    )
    if not prioridade:
        raise HTTPException(
            status_code=400,
            detail="Prioridade do usuário inválida."
        )

    # 3) Criar solicitação
    nova = models.Solicitacao(
        matricula=dados.matricula,
        id_tipo_solicitacao=dados.id_tipo_solicitacao,
        prioridade_usuario=dados.prioridade_usuario,
        descricao_solicitacao=dados.descricao_solicitacao,
        titulo_solicitacao=dados.titulo_solicitacao,
        comentario_admin=dados.comentario_admin,
        id_status=0,
        id_area=area.id_area,
        data_hora_abertura=datetime.now(),
        data_hora_baixa=None,
        previsao_entrega=dados.previsao_entrega,
        responsavel_solicitacao=dados.responsavel_solicitacao,  
    )

    db.add(nova)
    db.commit()
    db.refresh(nova)

    # Registrar evento de criação da solicitação
    id_notificacao = registrar_evento(
        id_solicitacao=nova.id_solicitacao,
        tipo_evento="CRIACAO",
        matricula_destino=dados.matricula,
        descricao=f"Solicitação criada pelo usuário {dados.matricula}."
    )

    background_tasks.add_task(enviar_notificacao_por_id, id_notificacao)
    
    return nova


# ---------- POST /PAGINA_SOLICITACAO_NEXUS/buscar ----------
@router.post(
    f"/{file}/buscar",
    response_model=List[schemas.SolicitacaoComUsuario]
)
async def buscar_solicitacoes(
    filtro: schemas.BuscarPeriodo,
    db: Session = Depends(get_db),
):
    """
    Busca solicitações por período (DATA_HORA_ABERTURA) e faz JOIN com TBL_USUARIOS (NOC)
    usando a coluna MATRICULA.
    """

    query = (
        db.query(models.Solicitacao, models.Usuario)
        .join(
            models.Usuario,
            models.Usuario.matricula == models.Solicitacao.matricula,
            isouter=True,
        )
        .filter(
            models.Solicitacao.data_hora_abertura >= filtro.data_inicio,
            models.Solicitacao.data_hora_abertura <= filtro.data_fim,
        )
    )

    rows = query.all()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma solicitação encontrada no período informado.",
        )

    resultado: List[schemas.SolicitacaoComUsuario] = []

    for solic, user in rows:
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
            id_area=solic.id_area,
            descricao_solicitacao=solic.descricao_solicitacao,
            titulo_solicitacao=solic.titulo_solicitacao,
            previsao_entrega=solic.previsao_entrega,
            comentario_admin=solic.comentario_admin,
            responsavel_solicitacao=solic.responsavel_solicitacao,
            usuario=schemas.UsuarioRead(
                matricula=user.matricula,
                nome=user.nome,
                previsao_entrega=solic.previsao_entrega,
            ) if user else None,
            arquivo=[],  # preenchido apenas no /solicitacoes e /solicitacao/{id}
        )

        resultado.append(item)

    return resultado




# ---------- GET /PAGINA_SOLICITACAO_NEXUS/solicitacoes ----------
@router.get(
    f"/{file}/solicitacoes",
    response_model=List[schemas.SolicitacaoComUsuario],
)
async def listar_todas_as_solicitacoes(
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):

    if page < 1:
        raise HTTPException(status_code=400, detail="page deve ser >= 1")
    if page_size < 1 or page_size > 200:
        raise HTTPException(status_code=400, detail="page_size deve estar entre 1 e 200")

    offset = (page - 1) * page_size

    rows = (
        db.query(models.Solicitacao, models.Usuario)
        .join(
            models.Usuario,
            models.Usuario.matricula == models.Solicitacao.matricula,
            isouter=True,
        )
        .order_by(models.Solicitacao.data_hora_abertura.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    resultado: List[schemas.SolicitacaoComUsuario] = []

    for solic, user in rows:
        if solic.id_area is None:
            raise HTTPException(
                status_code=500,
                detail=f"Registro ID_SOLICITACAO={solic.id_solicitacao} está sem ID_AREA definido no banco."
            )

        arquivos_db = (
            db.query(models.Arquivo)
            .filter(models.Arquivo.ID_SOLICITACAO == solic.id_solicitacao)
            .all()
        )
        arquivos_out = [schemas.ArquivoOut.from_orm(a) for a in arquivos_db]

        resultado.append(
            schemas.SolicitacaoComUsuario(
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
                titulo_solicitacao=solic.titulo_solicitacao,
                previsao_entrega=solic.previsao_entrega,
                comentario_admin=solic.comentario_admin,
                responsavel_solicitacao=solic.responsavel_solicitacao,
                usuario=schemas.UsuarioRead(
                    matricula=user.matricula,
                    nome=user.nome,
                    previsao_entrega=solic.previsao_entrega,
                ) if user else None,
                arquivo=arquivos_out,
            )
        )

    return resultado


# ---------- GET /PAGINA_SOLICITACAO_NEXUS/solicitacao/{id_solicitacao} ----------
@router.get(
    f"/{file}/solicitacao/{{id_solicitacao}}",
    response_model=schemas.SolicitacaoComUsuario,
)
async def obter_solicitacao(
    id_solicitacao: int,
    db: Session = Depends(get_db),
):
    # Busca solicitação + usuário
    row = (
        db.query(models.Solicitacao, models.Usuario)
        .join(
            models.Usuario,
            models.Usuario.matricula == models.Solicitacao.matricula,
            isouter=True,
        )
        .filter(models.Solicitacao.id_solicitacao == id_solicitacao)
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")

    solic, user = row

    # Busca arquivos vinculados
    arquivos_db = (
        db.query(models.Arquivo)
        .filter(models.Arquivo.ID_SOLICITACAO == solic.id_solicitacao)
        .all()
    )
    arquivos_out = [schemas.ArquivoOut.from_orm(a) for a in arquivos_db]

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
        titulo_solicitacao=solic.titulo_solicitacao,
        previsao_entrega=solic.previsao_entrega,
        comentario_admin=solic.comentario_admin,
        responsavel_solicitacao=solic.responsavel_solicitacao,
        usuario=schemas.UsuarioRead(
            matricula=user.matricula,
            nome=user.nome,
            previsao_entrega=solic.previsao_entrega,
        ) if user else None,
        arquivo=arquivos_out,
    )





# ---------- GET /PAGINA_SOLICITACAO_NEXUS/areas ----------
@router.get(f"/{file}/areas", response_model=List[schemas.AreaRead])
async def listar_areas(db: Session = Depends(get_db)):
    areas = db.query(models.AreaSolicitante).all()
    return areas


# ---------- GET /PAGINA_SOLICITACAO_NEXUS/prioridades ----------
@router.get(f"/{file}/prioridades", response_model=List[schemas.PrioridadeRead])
async def listar_prioridades(db: Session = Depends(get_db)):
    prioridades = db.query(models.Prioridade).order_by(models.Prioridade.id_prioridade).all()
    return prioridades


# ===================================================================
# NOVAS ROTAS: UPLOAD E LISTAGEM DE ARQUIVOS
# ===================================================================


from typing import List
from fastapi import UploadFile, File, HTTPException


# ---------- NOVA ROTA: multi-upload | POST /PAGINA_SOLICITACAO_NEXUS/upload-arquivos ----------

@router.post(
    f"/{file}/upload-arquivos",
    response_model=List[schemas.ArquivoOut],
    status_code=status.HTTP_201_CREATED,
)
async def upload_arquivos(
    id_solicitacao: int,
    background_tasks: BackgroundTasks,
    arquivos: Optional[List[UploadFile]] = File(None),
    arquivo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    solic = (
        db.query(models.Solicitacao)
        .filter(models.Solicitacao.id_solicitacao == id_solicitacao)
        .first()
    )
    if not solic:
        raise HTTPException(404, "Solicitação não encontrada.")

    lista_arquivos: List[UploadFile] = []

    if arquivos:
        lista_arquivos.extend([a for a in arquivos if a and a.filename])

    if arquivo and arquivo.filename:
        lista_arquivos.append(arquivo)

    if not lista_arquivos:
        raise HTTPException(400, "Nenhum arquivo enviado.")

    arquivos_salvos: List[models.Arquivo] = []
    caminhos_fisicos = []

    try:
        for arq in lista_arquivos:
            nome_original = arq.filename
            _, ext = os.path.splitext(nome_original)
            novo_nome = f"{os.urandom(16).hex()}{ext}"

            caminho_fisico = os.path.join(UPLOAD_DIR, novo_nome)
            caminho_url = f"/files/{novo_nome}"

            conteudo = await arq.read()
            with open(caminho_fisico, "wb") as f:
                f.write(conteudo)

            caminhos_fisicos.append(caminho_fisico)

            arquivo_db = models.Arquivo(
                ID_SOLICITACAO=id_solicitacao,
                NOME_ORIGINAL=nome_original,
                NOME_ARQUIVO=novo_nome,
                CAMINHO=caminho_url,
                CONTENT_TYPE=arq.content_type,
                TAMANHO_BYTES=len(conteudo),
                DATA_UPLOAD=datetime.now(),
            )
            db.add(arquivo_db)
            arquivos_salvos.append(arquivo_db)

        db.commit()
        for a in arquivos_salvos:
            db.refresh(a)

    except Exception as e:
        db.rollback()
        for c in caminhos_fisicos:
            if os.path.exists(c):
                os.remove(c)
        raise HTTPException(500, f"Erro ao processar upload: {str(e)}")

    # Evento + tempo real
    id_notificacao = registrar_evento(
        id_solicitacao=id_solicitacao,
        tipo_evento="ARQUIVO_ENVIADO",
        matricula_destino=solic.matricula,
        descricao=f"{len(arquivos_salvos)} arquivo(s) anexado(s).",
    )

    background_tasks.add_task(enviar_notificacao_por_id, id_notificacao)

    return arquivos_salvos





# ------------------------------------------------------------------------------------
# ROTA ANTIGA DE UPLOAD DE ARQUIVO (MANTIDA PARA REFERÊNCIA, MAS COMENTADA)
# ------------------------------------------------------------------------------------

# # ---------- POST /PAGINA_SOLICITACAO_NEXUS/upload-arquivo ----------
# @router.post(
#     f"/{file}/upload-arquivo",
#     response_model=schemas.ArquivoOut,
#     status_code=status.HTTP_201_CREATED,
# )
# async def upload_arquivo(
#     id_solicitacao: int,
#     arquivo: UploadFile = File(...),
#     db: Session = Depends(get_db),
# ):
#     """
#     Recebe um arquivo, salva fisicamente e registra vínculo com a solicitação.
#     """

#     # Verifica se a solicitação existe
#     solic = (
#         db.query(models.Solicitacao)
#         .filter(models.Solicitacao.id_solicitacao == id_solicitacao)
#         .first()
#     )
#     if not solic:
#         raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

#     _, ext = os.path.splitext(arquivo.filename)
#     novo_nome = f"{os.urandom(16).hex()}{ext}"

#     caminho_fisico = os.path.join(UPLOAD_DIR, novo_nome)
#     caminho_url = f"/files/{novo_nome}"

#     conteudo = await arquivo.read()

#     try:
#         with open(caminho_fisico, "wb") as f:
#             f.write(conteudo)
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Erro ao salvar arquivo em disco: {str(e)}",
#         )

#     arquivo_db = models.Arquivo(
#         ID_SOLICITACAO=id_solicitacao,
#         NOME_ORIGINAL=arquivo.filename,
#         NOME_ARQUIVO=novo_nome,
#         CAMINHO=caminho_url,
#         CONTENT_TYPE=arquivo.content_type,
#         TAMANHO_BYTES=len(conteudo),
#         DATA_UPLOAD=datetime.now(),
#     )

#     db.add(arquivo_db)
#     db.commit()
#     db.refresh(arquivo_db)

#     # Notificação de arquivo enviado
#     registrar_evento(
#         id_solicitacao=id_solicitacao,
#         tipo_evento="ARQUIVO_ENVIADO",
#         matricula_destino=solic.matricula,
#         descricao=f"Novo arquivo anexado: {arquivo.filename}"
#     )

#     return arquivo_db


# print(models.Arquivo.__table__)
# print(models.Arquivo.__mapper__.primary_key)


# ---------- GET /PAGINA_SOLICITACAO_NEXUS/arquivos/{id_solicitacao} ----------
@router.get(
    f"/{file}/arquivos/{{id_solicitacao}}",
    response_model=List[schemas.ArquivoOut],
)
async def listar_arquivos_por_solicitacao(
    id_solicitacao: int,
    db: Session = Depends(get_db),
):
    arquivos = (
        db.query(models.Arquivo)
        .filter(models.Arquivo.ID_SOLICITACAO == id_solicitacao)
        .all()
    )
    return arquivos


print(models.Arquivo.__table__)
print(models.Arquivo.__mapper__.primary_key)




# ---------- PUT /PAGINA_SOLICITACAO_NEXUS/atualizar-arquivo/{id_arquivo} ----------
@router.put("/PAGINA_SOLICITACAO_NEXUS/atualizar-arquivo/{id_arquivo}",
    response_model=schemas.ArquivoOut,
)
async def atualizar_arquivo(
    id_arquivo: int,
    novo_arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    arquivo_db = db.query(models.Arquivo).filter(models.Arquivo.ID_ARQUIVO == id_arquivo).first()

    if not arquivo_db:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    _, ext = os.path.splitext(novo_arquivo.filename)
    novo_nome = f"{os.urandom(16).hex()}{ext}"

    caminho_fisico = os.path.join(UPLOAD_DIR, novo_nome)
    caminho_url = f"/files/{novo_nome}"

    conteudo = await novo_arquivo.read()

    try:
        with open(caminho_fisico, "wb") as f:
            f.write(conteudo)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao salvar arquivo em disco: {str(e)}",
        )

    # Remove o arquivo antigo do disco
    caminho_antigo = os.path.join(UPLOAD_DIR, os.path.basename(arquivo_db.CAMINHO))
    if os.path.exists(caminho_antigo):
        try:
            os.remove(caminho_antigo)
        except Exception as e:
            print(f"Warning: Não foi possível remover o arquivo antigo: {str(e)}")

    # Atualiza o registro no banco
    arquivo_db.NOME_ORIGINAL = novo_arquivo.filename
    arquivo_db.NOME_ARQUIVO = novo_nome
    arquivo_db.CAMINHO = caminho_url
    arquivo_db.CONTENT_TYPE = novo_arquivo.content_type
    arquivo_db.TAMANHO_BYTES = len(conteudo)
    arquivo_db.DATA_UPLOAD = datetime.now()
    

    db.commit()
    db.refresh(arquivo_db)

    return arquivo_db




# ---------- POST /PAGINA_SOLICITACAO_NEXUS/atualizar-status/{id_solicitacao} ----------
@router.post(f"/{file}/atualizar-status/{{id_solicitacao}}")
async def atualizar_status(
    id_solicitacao: int,
    payload: schemas.AtualizarStatus,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    solic = db.query(models.Solicitacao).filter(
        models.Solicitacao.id_solicitacao == id_solicitacao
    ).first()
    if not solic:
        raise HTTPException(404, "Solicitação não encontrada.")

    solic.id_status = payload.novo_status
    if payload.novo_status in (3, 4):
        solic.data_hora_baixa = datetime.now()
    else:
        solic.data_hora_baixa = None

    db.commit()
    db.refresh(solic)

    id_notificacao = registrar_evento(
        id_solicitacao=id_solicitacao,
        tipo_evento="STATUS_ATUALIZADO",
        matricula_destino=solic.matricula,
        descricao=f"Status alterado para {payload.novo_status}.",
    )

    background_tasks.add_task(enviar_notificacao_por_id, id_notificacao)

    return {"mensagem": "Status atualizado com sucesso."}


# ---------- POST /PAGINA_SOLICITACAO_NEXUS/atualizar-previsao-entrega/{id_solicitacao} ----------

@router.post(f"/{file}/atualizar-previsao-entrega/{{id_solicitacao}}")
async def atualizar_previsao_entrega(
    id_solicitacao: int,
    payload: schemas.AtualizarPrevisaoEntrega,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    solic = db.query(models.Solicitacao).filter(
        models.Solicitacao.id_solicitacao == id_solicitacao
    ).first()
    if not solic:
        raise HTTPException(404, "Solicitação não encontrada.")

    solic.previsao_entrega = payload.nova_previsao
    db.commit()
    db.refresh(solic)

    id_notificacao = registrar_evento(
        id_solicitacao=id_solicitacao,
        tipo_evento="PREVISAO_ENTREGA",
        matricula_destino=solic.matricula,
        descricao=f"Previsão de entrega atualizada para {payload.nova_previsao}.",
    )

    background_tasks.add_task(enviar_notificacao_por_id, id_notificacao)

    return {"mensagem": "Previsão de entrega atualizada com sucesso."}



# ---------- POST /PAGINA_SOLICITACAO_NEXUS/atualizar-comentario-admin/{id_solicitacao} ----------
@router.post(f"/{file}/atualizar-comentario-admin/{{id_solicitacao}}")
async def atualizar_comentario_admin(
    id_solicitacao: int,
    payload: schemas.AtualizarComentarioAdmin,
    db: Session = Depends(get_db),
):

    solic = (
        db.query(models.Solicitacao)
        .filter(models.Solicitacao.id_solicitacao == id_solicitacao)
        .first()
    )

    if not solic:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    solic.comentario_admin = payload.comentario_admin

    db.commit()
    db.refresh(solic)

    registrar_evento(
        id_solicitacao=solic.id_solicitacao,
        tipo_evento="COMENTARIO_ADMIN",
        matricula_destino=solic.matricula,
        descricao=f"Comentário do admin: {payload.comentario_admin}"
    )

    return {
        "mensagem": "Comentário do admin atualizado com sucesso!",
        "id_solicitacao": solic.id_solicitacao,
        "comentario_admin": solic.comentario_admin,
    }



# ---------- POST /PAGINA_SOLICITACAO_NEXUS/atualizar-descricao_solicitacao/{id_solicitacao} ----------
@router.post(f"/{file}/atualizar-descricao_solicitacao/{{id_solicitacao}}")
async def atualizar_descricao_solicitacao(
    id_solicitacao: int,
    payload: schemas.AtualizarDescricaoSolicitacao,
    db: Session = Depends(get_db),
):

    solic = (
        db.query(models.Solicitacao)
        .filter(models.Solicitacao.id_solicitacao == id_solicitacao)
        .first()
    )

    if not solic:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    solic.descricao_solicitacao = payload.descricao_solicitacao

    db.commit()
    db.refresh(solic)

    registrar_evento(
        id_solicitacao=solic.id_solicitacao,
        tipo_evento="DESCRICAO_ATUALIZADA",
        matricula_destino=solic.matricula,
        descricao="Descrição da solicitação atualizada."
    )

    return {
        "mensagem": "Descrição da solicitação atualizadoa com sucesso!",
        "id_solicitacao": solic.id_solicitacao,
        "descricao_solicitacao": solic.descricao_solicitacao,
    }


# ---------- POST /PAGINA_SOLICITACAO_NEXUS/atualizar-prioridade-area/{id_solicitacao} ----------
@router.post(f"/{file}/atualizar-prioridade-area/{{id_solicitacao}}")
async def atualizar_prioridade_area(
    id_solicitacao: int,
    payload: schemas.AtualizarPrioridadeArea,
    db: Session = Depends(get_db),
):
    """
    Atualiza a prioridade da área (prioridade_area) da solicitação.
    """

    # 1) Busca a solicitação
    solic = (
        db.query(models.Solicitacao)
        .filter(models.Solicitacao.id_solicitacao == id_solicitacao)
        .first()
    )

    if not solic:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    # 2) Valida se a prioridade da área existe na tabela TBL_PRIORIDADES
    prioridade_valida = (
        db.query(models.Prioridade)
        .filter(models.Prioridade.id_prioridade == payload.prioridade_area)
        .first()
    )

    if not prioridade_valida:
        raise HTTPException(
            status_code=400,
            detail="Prioridade da área inválida."
        )

    # 3) Atualiza a prioridade da área
    solic.prioridade_area = payload.prioridade_area

    # 4) Salva no banco
    db.commit()
    db.refresh(solic)

    # 5) Registrar evento
    registrar_evento(
        id_solicitacao=solic.id_solicitacao,
        tipo_evento="PRIORIDADE_AREA",
        matricula_destino=solic.matricula,
        descricao=f"A prioridade da área foi atualizada para {payload.prioridade_area}."
    )

    return {
        "mensagem": "Prioridade da área atualizada com sucesso!",
        "id_solicitacao": solic.id_solicitacao,
        "prioridade_area": solic.prioridade_area,
    }



# ---------- DELETE /PAGINA_SOLICITACAO_NEXUS/solicitacao/{id_solicitacao} ----------
@router.delete(f"/{file}/solicitacao/{{id_solicitacao}}")
async def deletar_solicitacao(
    id_solicitacao: int,
    db: Session = Depends(get_db),
):
    solic = (
        db.query(models.Solicitacao)
        .filter(models.Solicitacao.id_solicitacao == id_solicitacao)
        .first()
    )

    if not solic:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    # Deleta arquivos vinculados
    arquivos = (
        db.query(models.Arquivo)
        .filter(models.Arquivo.ID_SOLICITACAO == id_solicitacao)
        .all()
    )
    for arquivo in arquivos:
        caminho_fisico = os.path.join(UPLOAD_DIR, os.path.basename(arquivo.CAMINHO))
        if os.path.exists(caminho_fisico):
            try:
                os.remove(caminho_fisico)
            except Exception as e:
                print(f"Warning: Não foi possível remover o arquivo {arquivo.NOME_ORIGINAL}: {str(e)}")
        db.delete(arquivo)

    # Deleta a solicitação
    db.delete(solic)
    db.commit()

    registrar_evento(
        id_solicitacao=id_solicitacao,
        tipo_evento="SOLICITACAO_DELETADA",
        matricula_destino=solic.matricula,
        descricao="A solicitação foi deletada."
    )

    return {"mensagem": "Solicitação e arquivos vinculados deletados com sucesso."}



# ---------- DELETE /PAGINA_SOLICITACAO_NEXUS/arquivo/{id_arquivo} ----------
@router.delete("/PAGINA_SOLICITACAO_NEXUS/arquivo/{id_arquivo}")
async def deletar_arquivo(
    id_arquivo: int,
    db: Session = Depends(get_db),
):
    arquivo_db = (
        db.query(models.Arquivo)
        .filter(models.Arquivo.ID_ARQUIVO == id_arquivo)
        .first()
    )

    if not arquivo_db:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    # Guarda infos antes de deletar (para retornar/registrar evento)
    id_solicitacao = arquivo_db.ID_SOLICITACAO
    nome_original = arquivo_db.NOME_ORIGINAL
    caminho = arquivo_db.CAMINHO

    # 1) Tenta remover do disco (se falhar, você decide se bloqueia ou só avisa)
    caminho_fisico = os.path.join(UPLOAD_DIR, os.path.basename(caminho))
    erro_disco = None

    if os.path.exists(caminho_fisico):
        try:
            os.remove(caminho_fisico)
        except Exception as e:
            erro_disco = str(e)
            # Para bloquear quando falhar, trocar por:
            # raise HTTPException(status_code=500, detail=f"Falha ao remover arquivo do disco: {erro_disco}")

    # 2) Remove do banco
    try:
        db.delete(arquivo_db)
        db.commit()
    except Exception as e:
        db.rollback()
        # Caso o disco seja apagado mas o banco falhou, podemos logar isso
        raise HTTPException(status_code=500, detail=f"Erro ao deletar registro no banco: {str(e)}")

    # 3) (Opcional) Registrar evento de auditoria/notificação
    # Dependendo do modelo de dados, pode ser interessante registrar o ID da solicitação e o nome do arquivo deletado.
    # Aqui vou registrar só com id_solicitacao (ajuste a matrícula conforme o modelo).
    try:
        registrar_evento(
            id_solicitacao=id_solicitacao,
            tipo_evento="ARQUIVO_DELETADO",
            matricula_destino="",  # ajuste se tiver matricula no contexto
            descricao=f"Arquivo removido: {nome_original} (ID_ARQUIVO={id_arquivo})."
        )
    except Exception as e:
        # Não quebra o delete por falha de evento, só loga
        print(f"Warning: falha ao registrar evento de exclusão de arquivo: {e}")

    return {
        "mensagem": "Arquivo deletado com sucesso.",
        "id_arquivo": id_arquivo,
        "id_solicitacao": id_solicitacao,
        "arquivo_removido_disco": erro_disco is None,
        "warning_disco": erro_disco,
    }

