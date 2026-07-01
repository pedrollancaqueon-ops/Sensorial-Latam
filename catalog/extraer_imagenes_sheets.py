"""
Extrae imágenes embebidas de un Google Sheet usando la API de Google.
Requiere: pip install google-auth google-auth-oauthlib google-api-python-client requests
Credencial: service account JSON con acceso a Drive y Sheets.
"""

import os
import re
import requests
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = "service_account.json"  # ruta al JSON de la service account
SPREADSHEET_ID = "TU_SPREADSHEET_ID_AQUI"
CARPETA_SALIDA = "imagenes_catalogo"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

def obtener_credenciales():
    return service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

def extraer_imagenes_sheets(spreadsheet_id: str, carpeta_salida: str):
    creds = obtener_credenciales()
    service = build("sheets", "v4", credentials=creds)
    salida = Path(carpeta_salida)
    salida.mkdir(exist_ok=True)

    # Obtener metadata completa del spreadsheet incluyendo imágenes embebidas
    resultado = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        includeGridData=True,
    ).execute()

    imagenes_encontradas = 0

    for sheet in resultado.get("sheets", []):
        nombre_hoja = sheet["properties"]["title"]
        print(f"\nHoja: {nombre_hoja}")

        for grid_data in sheet.get("data", []):
            for fila_idx, fila in enumerate(grid_data.get("rowData", [])):
                for col_idx, celda in enumerate(fila.get("values", [])):

                    # Imágenes insertadas con =IMAGE()
                    formula = celda.get("userEnteredValue", {}).get("formulaValue", "")
                    if formula.upper().startswith("=IMAGE("):
                        url = re.findall(r'"(https?://[^"]+)"', formula)
                        if url:
                            nombre_archivo = f"{nombre_hoja}_F{fila_idx+1}_C{col_idx+1}.jpg"
                            _descargar_imagen(url[0], salida / nombre_archivo, creds)
                            imagenes_encontradas += 1

    # Imágenes flotantes (over-the-grid) — requieren exportar la hoja
    if imagenes_encontradas == 0:
        print("\nNo se encontraron imágenes con =IMAGE(). Intentando exportar hoja como XLSX...")
        _exportar_como_xlsx(spreadsheet_id, creds, carpeta_salida)
    else:
        print(f"\nTotal: {imagenes_encontradas} imágenes descargadas en '{carpeta_salida}/'")

def _descargar_imagen(url: str, destino: Path, creds):
    try:
        headers = {"Authorization": f"Bearer {creds.token}"}
        creds.refresh(requests.Request())  # type: ignore
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        destino.write_bytes(r.content)
        print(f"  Descargada: {destino.name}")
    except Exception as e:
        print(f"  Error descargando {url}: {e}")

def _exportar_como_xlsx(spreadsheet_id: str, creds, carpeta_salida: str):
    """
    Exporta el Sheet como .xlsx — las imágenes flotantes quedan dentro.
    Luego usa el script extraer_imagenes_excel.py sobre ese archivo.
    """
    drive = build("drive", "v3", credentials=creds)
    request = drive.files().export_media(
        fileId=spreadsheet_id,
        mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    xlsx_path = Path(carpeta_salida) / "catalogo_exportado.xlsx"
    with open(xlsx_path, "wb") as f:
        f.write(request.execute())
    print(f"  Exportado como: {xlsx_path}")
    print("  Ahora corre: python extraer_imagenes_excel.py catalogo_exportado.xlsx")

if __name__ == "__main__":
    extraer_imagenes_sheets(SPREADSHEET_ID, CARPETA_SALIDA)
