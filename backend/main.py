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
    foto: str  # base64 JPEG


class EvaluacionPayload(BaseModel):
    evaluador:          str
    codigo:             str
    nombre:             str
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
    result = matcher.identificar(req.foto)
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
    import requests as req
    import urllib3
    urllib3.disable_warnings()

    url = os.getenv("SHEETS_WEBHOOK_URL", "")
    if not url:
        return {"ok": False, "error": "SHEETS_WEBHOOK_URL no configurada"}

    payload = {
        "fecha":      datetime.datetime.utcnow().isoformat() + "Z",
        "evaluador":  "test-render",
        "proveedor":  "Gategourmet SCL",
        "codigo":     "TEST",
        "nombre":     "Prueba conectividad",
        "color": 3, "aspecto": 3, "olor": 3, "sabor": 3, "textura": 3,
        "comentarios": "Fila de prueba automatica — borrar",
    }

    pasos = []
    try:
        # Paso 1: POST inicial
        r1 = req.post(url, json=payload, timeout=15, allow_redirects=False, verify=True)
        ok = r1.status_code in (200, 301, 302, 303, 307, 308)
        pasos.append({"paso": 1, "status": r1.status_code, "body": r1.text[:300]})
        return {"ok": ok, "pasos": pasos}

    except Exception as e:
        pasos.append({"paso": "excepcion", "error": str(e)})
        return {"ok": False, "pasos": pasos}


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
