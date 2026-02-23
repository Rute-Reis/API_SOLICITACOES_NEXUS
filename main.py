from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import ssl

#from .backlogRansharing import backlogRansharing
#from .tabelaAutomacao import tabelaAutomacao
#from .Science import Science
#from .PlanoVerao import PlanoVerao
#from .FalhasClearDOL import FalhasClearDOL
#from .AnaliseAlarmesDOL import AnaliseAlarmesDOL
from .PAGINA_SOLICITACAO_NEXUS import PAGINA_SOLICITACAO_NEXUS


app = FastAPI()

import os

app = FastAPI()

# === Pasta de uploads_solicitacao_Nexus, compartilhada com PAGINA_SOLICITACAO_NEXUS ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))      # diretório onde está o main.py
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads_solicitacao_Nexus")             # /.../pasta_do_projeto/uploads
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Servir arquivos estáticos da pasta uploads_solicitacao_Nexus na rota /uploads_solicitacao_Nexus
app.mount("/uploads_solicitacao_Nexus", StaticFiles(directory=UPLOAD_DIR), name="uploads_solicitacao_Nexus")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://10.215.39.31:7771",
        "http://10.215.39.31:7771",
        "https://10.215.39.31",
        "http://10.215.39.31",
        "https://10.8.141.212:8000",
        "http://10.8.141.212:8000",
        "https://10.8.141.212:8080",
        "http://10.8.141.212:8080",
        "https://10.8.141.212:3000",
        "http://10.8.141.212:3000",
        "https://10.126.112.251:5173",
        "http://10.126.112.251:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


#app.include_router(backlogRansharing.router)
#app.include_router(tabelaAutomacao.router)
#app.include_router(Science.router)
#app.include_router(PlanoVerao.router)
#app.include_router(FalhasClearDOL.router)
#app.include_router(AnaliseAlarmesDOL.router)
app.include_router(PAGINA_SOLICITACAO_NEXUS.router)


@app.get("/")
async def root():

    return {"message": "main app da API"}


uvicorn.run(app,
            host="10.126.112.251",
            port=9000,
            ssl_certfile="3019804.cer",
            ssl_keyfile="10.126.112.251.pem")
