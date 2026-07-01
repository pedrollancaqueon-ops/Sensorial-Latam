import os
import requests
import urllib3

_WEBHOOK_URL = os.getenv("SHEETS_WEBHOOK_URL", "")

# En redes corporativas con SSL inspection el certificado de Google
# viene reemplazado por uno interno. SSL_VERIFY=false lo desactiva solo en dev.
_SSL_VERIFY = os.getenv("SSL_VERIFY", "true").lower() != "false"

if not _SSL_VERIFY:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def guardar_evaluacion(payload: dict) -> bool:
    if not _WEBHOOK_URL:
        print("[sheets] SHEETS_WEBHOOK_URL no configurada — omitiendo escritura en Sheets")
        return False

    try:
        resp = requests.post(
            _WEBHOOK_URL,
            json=payload,
            timeout=15,
            allow_redirects=True,
            verify=_SSL_VERIFY,
        )
        resp.raise_for_status()
        result = resp.json()
        print(f"[sheets] Guardado OK: {result}")
        return result.get("ok", True)

    except Exception as e:
        print(f"[sheets] Error al guardar en Sheets: {e}")
        return False
