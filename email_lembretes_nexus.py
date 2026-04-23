import os
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import smtplib
from email.message import EmailMessage

import pandas as pd
from sqlalchemy import create_engine

from dispatcher_notificacoes import enviar_teams_power_automate


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
# URL DO PORTAL NEXUS (AMBIENTE ATUAL)
# --------------------------------------------------
URL_NEXUS_SOLICITACOES = (
    "https://10.8.141.212:8080/Administrador/Debora%20Teste"
)


# --------------------------------------------------
# CONFIGURAÇÕES DE E-MAIL
# --------------------------------------------------
EMAIL_REMETENTE = "nexusanalytics.br@telefonica.com"
SMTP_SERVIDOR = "10.128.11.229"
SMTP_PORTA = 25

EMAIL_ADMINS = [
    "rute.rnascimento@telefonica.com",
    "debora.carneiro@telefonica.com",
]


# --------------------------------------------------
# PARÂMETROS DE REGRA DE LEMBRETE
# --------------------------------------------------
HORAS_ATRASO = 48


# --------------------------------------------------
# FUNÇÕES AUXILIARES
# --------------------------------------------------
def destacar_status(valor: str) -> str:
    if valor == "Aberta":
        return f'<span class="status-critico">{valor}</span>'
    if valor in ["Em análise", "Em andamento", "Em desenvolvimento", "Homologação"]:
        return f'<span class="status-atencao">{valor}</span>'
    return valor


# --------------------------------------------------
# FUNÇÃO PRINCIPAL
# --------------------------------------------------
def main():
    limite_tempo = datetime.now() - timedelta(hours=HORAS_ATRASO)

    query_pendentes = f"""
        SELECT
            S.ID_SOLICITACAO,
            U.NOME AS NOME_USUARIO,
            U.EMAIL AS EMAIL_USUARIO,
            CASE
                WHEN S.ID_STATUS = 0 THEN 'Aberta'
                WHEN S.ID_STATUS = 1 THEN 'Em análise'
                WHEN S.ID_STATUS = 2 THEN 'Em desenvolvimento'
                WHEN S.ID_STATUS = 3 THEN 'Homologação'
                WHEN S.ID_STATUS = 4 THEN 'Concluída'
                WHEN S.ID_STATUS = 5 THEN 'Cancelada'
                WHEN S.ID_STATUS = 6 THEN 'Paralisado'
                ELSE 'Desconhecido'
            END AS STATUS_NOME,
            S.DATA_HORA_ABERTURA,
            S.PREVISAO_ENTREGA,
            S.TITULO_SOLICITACAO,
            S.COMENTARIO_ADMIN
        FROM TBL_SOLICITACOES_NEXUS S
        LEFT JOIN NOC.TBL_USUARIOS U
            ON U.MATRICULA = S.MATRICULA
        WHERE S.ID_STATUS NOT IN (4, 5)
          AND S.DATA_HORA_ABERTURA < '{limite_tempo.strftime("%Y-%m-%d %H:%M:%S")}'
        ORDER BY S.DATA_HORA_ABERTURA ASC;
    """

    df = pd.read_sql(query_pendentes, ENGINE)

    if df.empty:
        print(f"[{datetime.now()}] Nenhuma solicitação pendente para lembrete.")
        return

    # --------------------------------------------------
    # TRATAMENTO VISUAL DOS DADOS
    # --------------------------------------------------
    df = df.fillna("-")

    df["DATA_HORA_ABERTURA"] = pd.to_datetime(
        df["DATA_HORA_ABERTURA"]
    ).dt.strftime("%d/%m/%Y %H:%M")

    if "PREVISAO_ENTREGA" in df.columns:
        df["PREVISAO_ENTREGA"] = pd.to_datetime(
            df["PREVISAO_ENTREGA"], errors="coerce"
        ).dt.strftime("%d/%m/%Y %H:%M").fillna("-")

    df["STATUS_NOME"] = df["STATUS_NOME"].apply(destacar_status)

    df = df.rename(columns={
        "ID_SOLICITACAO": "Solicitação",
        "NOME_USUARIO": "Usuário",
        "EMAIL_USUARIO": "E-mail",
        "STATUS_NOME": "Status",
        "DATA_HORA_ABERTURA": "Abertura",
        "PREVISAO_ENTREGA": "Previsão Entrega",
        "TITULO_SOLICITACAO": "Título Solicitação",
        "COMENTARIO_ADMIN": "Comentário Admin",
    })

    colunas_exibir = [
        "Solicitação",
        "Usuário",
        "E-mail",
        "Status",
        "Abertura",
        "Previsão Entrega",
        "Título Solicitação",
        "Comentário Admin",
    ]

    df = df[colunas_exibir]

    tabela_html = df.to_html(
        index=False,
        escape=False,
        classes="tabela",
        border=0
    )

    # --------------------------------------------------
    # HTML FINAL DO E-MAIL
    # --------------------------------------------------
    corpo_html = f"""
    <html>
    <head>
      <style>
        body {{
          font-family: Arial, sans-serif;
          font-size: 14px;
          color: #333333;
        }}

        table.tabela {{
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }}

        table.tabela th {{
          background-color: #660099;
          color: white;
          padding: 8px;
          text-align: left;
          border: 1px solid #4a0066; /* linha entre colunas no header */
        }}

        table.tabela td {{
          padding: 6px;
          border: 1px solid #dddddd; /* linhas verticais e horizontais */
        }}

        table.tabela tr:nth-child(even) {{
          background-color: #f7f3fb;
        }}

        .status-critico {{
          color: #b30000;
          font-weight: bold;
        }}

        .status-atencao {{
          color: #c28500;
          font-weight: bold;
        }}
      </style>
    </head>

    <body>
      <p>Bom dia,</p>

      <p><strong>Solicitações abertas há mais de {HORAS_ATRASO} horas</strong></p>

      
      <p>
        🔗 <a href="{URL_NEXUS_SOLICITACOES}" target="_blank">
          Acessar solicitações no Portal
        </a>
      </p>

      {tabela_html}

      <br>
      <p>Por favor, avaliem e atualizem o tratamento das solicitações quando possível.</p>

      <p>Este é um e-mail automático enviado apenas ao time responsável.</p>

      <p>Atenciosamente,<br>Equipe NEXUS</p>
    </body>
    </html>
    """

    msg = EmailMessage()
    msg["Subject"] = f"[NEXUS] Lembrete - Solicitações pendentes (+{HORAS_ATRASO}h)"
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = ", ".join(EMAIL_ADMINS)
    msg.set_content("Seu cliente de e-mail não suporta HTML.")
    msg.add_alternative(corpo_html, subtype="html")

    with smtplib.SMTP(SMTP_SERVIDOR, SMTP_PORTA) as smtp:
        smtp.send_message(msg)

    # --------------------------------------------------
    # TEAMS (RESUMO)
    # --------------------------------------------------
    mensagem = (
        f"⏰ Lembrete Nexus\n"
        f"{len(df)} solicitações pendentes há mais de {HORAS_ATRASO}h.\n"
        f"Verifique o e-mail para detalhes."
    )

    enviar_teams_power_automate(
        id_solicitacao=0,
        mensagem=mensagem,
        tipo_evento="LEMBRETE",
    )


if __name__ == "__main__":
    main()
