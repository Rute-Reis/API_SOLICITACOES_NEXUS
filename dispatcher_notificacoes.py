import os
import smtplib
import requests
from email.message import EmailMessage
from sqlalchemy import text
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from datetime import datetime


# =====================================================================
# CONFIGURAÇÕES DE E-MAIL
# =====================================================================
EMAIL_REMETENTE = "nexusanalytics.br@telefonica.com"
SMTP_SERVIDOR = "10.128.11.229"
SMTP_PORTA = 25


# =====================================================================
# CONFIGURAÇÕES DE BANCO
# =====================================================================
DB_USER = "dev"
DB_PASSWORD = os.getenv("NOC_PASSWORD")
DB_HOST = "10.126.112.251"
DB_PORT = 3306
DB_NAME = "NEXUS"


def _engine():
    if not DB_PASSWORD:
        raise RuntimeError("NOC_PASSWORD não definida no ambiente.")
    pwd = quote_plus(DB_PASSWORD)
    return create_engine(
        f"mysql+pymysql://{DB_USER}:{pwd}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )


# =====================================================================
# CONFIGURAÇÃO DO TEAMS (POWER AUTOMATE)
# =====================================================================
POWER_AUTOMATE_URL = os.getenv("POWER_AUTOMATE_TEAMS_URL")


def enviar_teams_power_automate(
    id_solicitacao: int,
    mensagem: str,
    tipo_evento: str = "ATUALIZACAO",
):
    if not POWER_AUTOMATE_URL:
        return

    payload = {
        "id_solicitacao": id_solicitacao,
        "tipo_evento": tipo_evento,
        "mensagem": mensagem,
    }

    try:
        requests.post(
            POWER_AUTOMATE_URL,
            json=payload,
            timeout=5,
        )
    except Exception as e:
        print(f"[POWER_AUTOMATE] Erro ao enviar para Teams: {e}")


# =====================================================================
# MAPA DE EVENTOS (TÉCNICO -> MENSAGEM PARA USUÁRIO)
# =====================================================================
EVENTO_PARA_MENSAGEM_USUARIO = {
    "CRIACAO": "Sua solicitação foi criada com sucesso.",
    "STATUS_ATUALIZADO": "Sua solicitação foi atualizada.",
    "PREVISAO_ENTREGA": "Sua solicitação foi atualizada.",
    "COMENTARIO_ADMIN": "Sua solicitação foi atualizada.",
    "ARQUIVO_ENVIADO": "Sua solicitação foi atualizada.",
    "PRIORIDADE_AREA": "Sua solicitação foi atualizada.",
    "RESPONSAVEL_ATUALIZADO": "Sua solicitação foi atualizada.",
    "SOLICITACAO_DELETADA": "Sua solicitação foi removida.",
}


# =====================================================================
# FUNÇÃO PRINCIPAL: ENVIO DE NOTIFICAÇÃO EM TEMPO REAL
# =====================================================================
def enviar_notificacao_por_id(id_notificacao: int):
    eng = _engine()

    query = text("""
        SELECT 
            N.ID_NOTIFICACAO,
            N.ID_SOLICITACAO,
            N.TIPO_EVENTO,
            N.MATRICULA_DESTINO,
            N.DESCRICAO_EVENTO,
            N.DATA_EVENTO,
            U.EMAIL AS EMAIL_DESTINO,
            U.NOME AS NOME_DESTINO
        FROM TBL_NOTIFICACOES_NEXUS N
        LEFT JOIN NOC.TBL_USUARIOS U
               ON U.MATRICULA = N.MATRICULA_DESTINO
        WHERE N.ID_NOTIFICACAO = :id
          AND N.ENVIADO = 0
    """)

    with eng.begin() as conn:
        row = conn.execute(query, {"id": int(id_notificacao)}).mappings().first()

    if not row:
        return

    email_destino = (
        row["EMAIL_DESTINO"]
        if row["EMAIL_DESTINO"]
        else f"{row['MATRICULA_DESTINO']}@telefonica.com"
    )

    mensagem_usuario = EVENTO_PARA_MENSAGEM_USUARIO.get(
        row["TIPO_EVENTO"],
        "Sua solicitação foi atualizada."
    )

    assunto = f"[NEXUS] Atualização da Solicitação #{row['ID_SOLICITACAO']}"

    corpo_email = f"""
Olá, {row['NOME_DESTINO']}!

{mensagem_usuario}

Você pode acompanhar os detalhes da sua solicitação acessando o Portal Nexus.

Atenciosamente,
Equipe Nexus
"""

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = email_destino
    msg.set_content(corpo_email)

    try:
        with smtplib.SMTP(SMTP_SERVIDOR, SMTP_PORTA) as smtp:
            smtp.send_message(msg)

        update_ok = text("""
            UPDATE TBL_NOTIFICACOES_NEXUS
            SET ENVIADO = 1
            WHERE ID_NOTIFICACAO = :id
        """)
        with eng.begin() as conn:
            conn.execute(update_ok, {"id": int(id_notificacao)})

        # ✅ AJUSTE — Teams chamado somente aqui (local correto)
        enviar_teams_power_automate(
            id_solicitacao=row["ID_SOLICITACAO"],
            mensagem=mensagem_usuario,
            tipo_evento=row["TIPO_EVENTO"],
        )

    except Exception as e:
        update_err = text("""
            UPDATE TBL_NOTIFICACOES_NEXUS
            SET 
                TENTATIVAS = COALESCE(TENTATIVAS, 0) + 1,
                ERRO_ULTIMO = :err
            WHERE ID_NOTIFICACAO = :id
        """)
        with eng.begin() as conn:
            conn.execute(
                update_err,
                {"id": int(id_notificacao), "err": str(e)}
            )
