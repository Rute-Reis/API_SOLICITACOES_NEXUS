from .app.database import SessionLocal
from .app import models
from datetime import datetime

def registrar_evento(id_solicitacao: int, tipo_evento: str, matricula_destino: str, 
descricao: str = "") -> int:
    db = SessionLocal()
    try:        
        evento = models.Notificacao(
        id_solicitacao=id_solicitacao,
        tipo_evento=tipo_evento,
        matricula_destino=matricula_destino,
        descricao_evento=descricao,
        data_evento=datetime.now(),
        enviado=0
        )
        db.add(evento)
        db.commit()
        db.refresh(evento) # garante que o ID gerado seja atualizado no objeto
        return evento.id_notificacao
    finally:
        db.close()
