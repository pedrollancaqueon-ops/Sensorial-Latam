from dotenv import load_dotenv
load_dotenv(dotenv_path="../.env")

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import matcher
import sheets

app = FastAPI(title="Evaluación Sensorial LATAM")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


# ── Modelos ────────────────────────────────────────────────────────────────────

class FotoRequest(BaseModel):
    foto: str  # base64 JPEG


class EvaluacionPayload(BaseModel):
    evaluador:    str
    codigo:       str
    nombre:       str
    proveedor:    str
    foto:         str        # base64 — no se guarda en Sheets, solo metadato
    comentarios:  str = ""
    fecha:        str
    apariencia:   int
    aroma:        int
    sabor:        int
    textura:      int
    temperatura:  int


# ── API ────────────────────────────────────────────────────────────────────────

@app.post("/api/identificar")
async def identificar(req: FotoRequest):
    if not req.foto:
        raise HTTPException(400, "foto requerida")
    result = matcher.identificar(req.foto)
    return result


@app.post("/api/guardar")
async def guardar(payload: EvaluacionPayload):
    data = payload.model_dump()
    data.pop("foto", None)  # no enviamos la imagen al Sheet
    ok = sheets.guardar_evaluacion(data)
    return {"ok": ok}


# ── Test de conectividad ───────────────────────────────────────────────────────

@app.get("/api/test-sheets")
async def test_sheets():
    import datetime
    payload = {
        "fecha":      datetime.datetime.utcnow().isoformat() + "Z",
        "evaluador":  "test-render",
        "proveedor":  "Gategourmet SCL",
        "codigo":     "TEST",
        "nombre":     "Prueba conectividad",
        "apariencia": 5, "aroma": 5, "sabor": 5, "textura": 5, "temperatura": 5,
        "comentarios": "Fila de prueba automatica — borrar",
    }
    ok = sheets.guardar_evaluacion(payload)
    return {"ok": ok, "webhook_url": os.getenv("SHEETS_WEBHOOK_URL", "")[:50] + "..."}


# ── Frontend estático ──────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(FRONTEND_DIR / "index.html")

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Arranque local ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
