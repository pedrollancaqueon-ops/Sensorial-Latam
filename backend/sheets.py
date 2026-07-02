import os
import requests
import urllib3

_WEBHOOK_URL = os.getenv("SHEETS_WEBHOOK_URL", "")
_SSL_VERIFY  = os.getenv("SSL_VERIFY", "true").lower() != "false"

if not _SSL_VERIFY:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def guardar_evaluacion(payload: dict) -> bool:
    if not _WEBHOOK_URL:
        print("[sheets] SHEETS_WEBHOOK_URL no configurada")
        return False

    try:
        # Paso 1: POST al /exec — dispara doPost en Google (retorna 302)
        r1 = requests.post(
            _WEBHOOK_URL,
            json=payload,
            timeout=15,
            allow_redirects=False,
            verify=_SSL_VERIFY,
        )
        print(f"[sheets] Paso 1 POST: {r1.status_code}")

        # 200: respuesta directa, 302: Apps Script procesó y redirige (ambos = éxito)
        if r1.status_code in (200, 301, 302, 303, 307, 308):
            print(f"[sheets] Guardado OK (status {r1.status_code})")
            return True

        print(f"[sheets] Error: {r1.status_code} — {r1.text[:200]}")
        return False

    except Exception as e:
        print(f"[sheets] Excepcion: {e}")
        return False
