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
CATALOG_DIR  = Path(__file__).parent.parent / "catalog"


# ── Modelos ────────────────────────────────────────────────────────────────────

class FotoRequest(BaseModel):
    foto: str   # base64 JPEG
    grid: str = ""  # 'BC', 'CREW', 'PYC' o 'YC'


class EvaluacionPayload(BaseModel):
    model_config = {"extra": "ignore"}

    evaluador:          str
    codigo:             str
    nombre:             str
    grid:               str = ""
    proveedor:          str
    foto:               str   # base64 — Apps Script sube a Drive
    comentarios:        str = ""
    fecha:              str
    imagen_referencia:  str = ""
    color:    int
    aspecto:  int
    olor:     int
    sabor:    int
    textura:  int


# ── API ────────────────────────────────────────────────────────────────────────

@app.post("/api/identificar")
async def identificar(req: FotoRequest):
    if not req.foto:
        raise HTTPException(400, "foto requerida")
    result = matcher.identificar(req.foto, grid=req.grid or None)
    return result


@app.post("/api/guardar")
async def guardar(payload: EvaluacionPayload):
    data = payload.model_dump()
    # foto va al Apps Script para que la suba a Drive
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
        "grid":       "BC",
        "color": 3, "aspecto": 3, "olor": 3, "sabor": 3, "textura": 3,
        "comentarios": "Fila de prueba — borrar",
    }
    ok = sheets.guardar_evaluacion(payload)
    return {"ok": ok}


# ── Estáticos ─────────────────────────────────────────────────────────────────

app.mount("/catalog", StaticFiles(directory=str(CATALOG_DIR)), name="catalog_files")

@app.get("/")
async def root():
    return FileResponse(FRONTEND_DIR / "index.html")

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Arranque local ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
