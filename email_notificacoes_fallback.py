import os
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import smtplib
from email.message import EmailMessage

import pandas as pd
from sqlalchemy import create_engine, text


DB_USER = "dev"
DB_PASSWORD = os.getenv("NOC_PASSWORD")
DB_PASSWORD = quote_plus(DB_PASSWORD)
DB_HOST = "10.126.112.251"
DB_PORT = 3306
DB_NAME = "NEXUS"

ENGINE = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

EMAIL_REMETENTE = "nexusanalytics.br@telefonica.com"
SMTP_SERVIDOR = "10.128.11.229"
SMTP_PORTA = 25

URL_NEXUS_SOLICITACAO = (
    "https://10.126.112.251:5173/Administrador/Debora%20Teste"
)


def main():
    query = """
        SELECT *
        FROM TBL_NOTIFICACOES_NEXUS
        WHERE ENVIADO = 0
          AND DATA_EVENTO < NOW() - INTERVAL 10 MINUTE
    """

    df = pd.read_sql(query, ENGINE)

    if df.empty:
        return

    update = text("""
        UPDATE TBL_NOTIFICACOES_NEXUS
        SET ENVIADO = 1
        WHERE ID_NOTIFICACAO = :id
    """)

    for _, row in df.iterrows():
        msg = EmailMessage()
        msg["Subject"] = f"[NEXUS] Atualização da Solicitação #{row['ID_SOLICITACAO']}"
        msg["From"] = EMAIL_REMETENTE
        msg["To"] = f"{row['MATRICULA_DESTINO']}@telefonica.com"

        corpo = f"""
        <html>
        <body>
          <p>Sua solicitação <strong>#{row['ID_SOLICITACAO']}</strong> foi atualizada.</p>

          <p>
            🔗 <a href="{URL_NEXUS_SOLICITACAO}" target="_blank">
            Acessar minha solicitação no Portal Nexus
            </a>
          </p>

          <p>Equipe NEXUS</p>
        </body>
        </html>
        """

        msg.set_content("Seu cliente não suporta HTML.")
        msg.add_alternative(corpo, subtype="html")

        with smtplib.SMTP(SMTP_SERVIDOR, SMTP_PORTA) as smtp:
            smtp.send_message(msg)

        with ENGINE.begin() as conn:
            conn.execute(update, {"id": row["ID_NOTIFICACAO"]})


if __name__ == "__main__":
    main()
