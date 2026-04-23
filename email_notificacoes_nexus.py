import os
from datetime import datetime
from urllib.parse import quote_plus
import smtplib
from email.message import EmailMessage

import pandas as pd
from sqlalchemy import create_engine, text


# --------------------------------------------------
# CONFIGURAÇÕES DE BANCO (NEXUS)
# --------------------------------------------------
DB_USER = "dev"
DB_PASSWORD = os.getenv("NOC_PASSWORD")
if not DB_PASSWORD:
    raise RuntimeError("Variável de ambiente NOC_PASSWORD não definida.")

DB_PASSWORD = quote_plus(DB_PASSWORD)
DB_HOST = "10.126.112.251"
DB_PORT = 3306
DB_NAME = "NEXUS"

ENGINE = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# --------------------------------------------------
# URL DO PORTAL NEXUS (AMBIENTE ATUAL - TESTES)
# --------------------------------------------------
URL_NEXUS_SOLICITACAO = (
    "https://10.126.112.251:5173/Administrador/Debora%20Teste"
)

# --------------------------------------------------
# STATUS DAS SOLICITAÇÕES
# --------------------------------------------------
STATUS_NOMES = {
    0: "Aberta",
    1: "Em análise",
    2: "Em andamento",
    3: "Concluída",
    4: "Cancelada",
    5: "Em desenvolvimento",
    6: "Em homologação",
}

# --------------------------------------------------
# PRIORIDADES DA ÁREA
# (ajuste conforme a tabela real)
# --------------------------------------------------
PRIORIDADE_NOMES = {
    0: "Baixa",
    1: "Média",
    2: "Alta",
    3: "Crítica",
}

# --------------------------------------------------
# TIPOS DE EVENTOS
# --------------------------------------------------
EVENTO_NOMES = {
    "CRIACAO": "Criação",
    "STATUS_ATUALIZADO": "Status atualizado",
    "COMENTARIO_ADMIN": "Comentário do administrador",
    "PRIORIDADE_AREA": "Prioridade da área",
    "PREVISAO_ENTREGA": "Previsão de entrega atualizada",
    "DESCRICAO_ATUALIZADA": "Descrição atualizada",
    "ARQUIVO_ENVIADO": "Arquivo enviado",
}

# --------------------------------------------------
# CONFIGURAÇÕES DE E-MAIL
# --------------------------------------------------
EMAIL_REMETENTE = "nexusanalytics.br@telefonica.com"
SMTP_SERVIDOR = "10.128.11.229"
SMTP_PORTA = 25


# --------------------------------------------------
# FUNÇÃO PRINCIPAL
# --------------------------------------------------
def main():
    query_notificacoes = """
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
        JOIN NOC.TBL_USUARIOS U 
            ON U.MATRICULA = N.MATRICULA_DESTINO
        WHERE N.ENVIADO = 0;
    """

    df = pd.read_sql(query_notificacoes, ENGINE)

    if df.empty:
        print(f"[{datetime.now()}] Nenhuma notificação pendente.")
        return

    print(f"[{datetime.now()}] Encontradas {len(df)} notificações pendentes.")

    update_query = text("""
        UPDATE TBL_NOTIFICACOES_NEXUS
        SET ENVIADO = 1
        WHERE ID_NOTIFICACAO = :id_notif
    """)

    for _, row in df.iterrows():
        id_notif = row["ID_NOTIFICACAO"]
        id_solic = row["ID_SOLICITACAO"]
        tipo = row["TIPO_EVENTO"]
        descricao = row["DESCRICAO_EVENTO"] or ""
        data_evento = row["DATA_EVENTO"]
        email_destino = row["EMAIL_DESTINO"]
        nome_destino = row["NOME_DESTINO"]

        # ----------------------------------------------
        # Formatar data/hora
        # ----------------------------------------------
        data_evento_fmt = (
            data_evento.strftime("%d/%m/%Y %H:%M")
            if isinstance(data_evento, datetime)
            else str(data_evento)
        )

        # ----------------------------------------------
        # Tratar eventos específicos
        # ----------------------------------------------
        if tipo == "STATUS_ATUALIZADO":
            try:
                numero = int(str(descricao).split()[-1].replace(".", ""))
                descricao = f"Status alterado para {STATUS_NOMES.get(numero, 'Desconhecido')}."
            except Exception:
                pass

        if tipo == "PRIORIDADE_AREA":
            try:
                numero = int(str(descricao).split()[-1].replace(".", ""))
                descricao = f"Prioridade da área alterada para {PRIORIDADE_NOMES.get(numero, 'Desconhecida')}."
            except Exception:
                pass

        assunto = f"[NEXUS] Atualização da Solicitação #{id_solic}"

        # ----------------------------------------------
        # CORPO DO E-MAIL (HTML VÁLIDO)
        # ----------------------------------------------
        corpo_html = f"""
        <html>
        <body>
            <p>Olá, {nome_destino}!</p>

            <p>
              Houve uma atualização na sua solicitação
              <strong>#{id_solic}</strong>.
            </p>

            <p><strong>Evento:</strong> {EVENTO_NOMES.get(tipo, tipo)}</p>

            <p><strong>Descrição:</strong> {descricao}</p>

            <p><strong>Data e hora do evento:</strong> {data_evento_fmt}</p>

            <p>
              🔗 <a href="{URL_NEXUS_SOLICITACAO}" target="_blank">
                Acessar minha solicitação no Portal Nexus
              </a>
            </p>

            <br>
            <p>
              Atenciosamente,<br>
              Equipe NEXUS
            </p>
        </body>
        </html>
        """

        msg = EmailMessage()
        msg["Subject"] = assunto
        msg["From"] = EMAIL_REMETENTE
        msg["To"] = email_destino
        msg.set_content("Seu cliente de e-mail não suporta HTML.")
        msg.add_alternative(corpo_html, subtype="html")

        try:
            with smtplib.SMTP(SMTP_SERVIDOR, SMTP_PORTA) as smtp:
                smtp.send_message(msg)

            print(f"[{datetime.now()}] E-mail enviado para {email_destino} (notif {id_notif}).")

            with ENGINE.begin() as conn:
                conn.execute(update_query, {"id_notif": int(id_notif)})

        except Exception as e:
            print(
                f"[{datetime.now()}] ERRO ao enviar e-mail "
                f"para {email_destino} (notif {id_notif}): {e}"
            )


if __name__ == "__main__":
    main()
