import os
import json
import datetime

import gspread
from google.oauth2.service_account import Credentials

_SPREADSHEET_ID = "1G2xd9D5a4_8JJkf7I3ZkAQMd-zqc30EFBOKuXeQm4bY"
_SHEET_NAME     = "Evaluaciones"
_SCOPES         = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_COLUMNS = [
    "fecha", "evaluador", "proveedor", "codigo", "nombre", "grid",
    "color", "aspecto", "olor", "sabor", "textura",
    "promedio", "comentarios", "foto_url", "imagen_referencia",
]
_SCORES = ["color", "aspecto", "olor", "sabor", "textura"]

_client: gspread.Client | None = None


def _get_client() -> gspread.Client:
    global _client
    if _client is None:
        creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not creds_json:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON no configurada")
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
        _client = gspread.authorize(creds)
    return _client


def _get_sheet() -> gspread.Worksheet:
    client = _get_client()
    ss     = client.open_by_key(_SPREADSHEET_ID)
    try:
        sheet = ss.worksheet(_SHEET_NAME)
    except gspread.WorksheetNotFound:
        sheet = ss.add_worksheet(_SHEET_NAME, rows=1000, cols=len(_COLUMNS))
        sheet.append_row([c.upper() for c in _COLUMNS])
        sheet.format("1", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0, "green": 0.09, "blue": 0.35},
        })
    return sheet


def guardar_evaluacion(payload: dict) -> bool:
    try:
        sheet = _get_sheet()

        promedio = sum(payload.get(k, 0) or 0 for k in _SCORES) / len(_SCORES)

        row = []
        for col in _COLUMNS:
            if col == "promedio":
                row.append(round(promedio, 2))
            elif col in ("foto_url", "imagen_referencia"):
                row.append("")  # Drive upload pendiente
            else:
                row.append(payload.get(col, "") or "")

        sheet.append_row(row, value_input_option="USER_ENTERED")
        print(f"[sheets] Fila guardada OK: {payload.get('codigo')} / {payload.get('evaluador')}")
        return True

    except Exception as e:
        print(f"[sheets] Error: {e}")
        return False
