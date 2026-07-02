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
        # Apps Script devuelve 302 y requests lo sigue como GET perdiendo el body.
        # Solución: primer request sin seguir redirect, luego POST manual al destino.
        resp = requests.post(
            _WEBHOOK_URL,
            json=payload,
            timeout=15,
            allow_redirects=False,
            verify=_SSL_VERIFY,
        )
        print(f"[sheets] Respuesta inicial: {resp.status_code}")

        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location", "")
            print(f"[sheets] Redirect a: {location}")
            resp = requests.post(
                location,
                json=payload,
                timeout=15,
                allow_redirects=False,
                verify=_SSL_VERIFY,
            )
            print(f"[sheets] Respuesta tras redirect: {resp.status_code} — {resp.text[:200]}")

        if resp.status_code == 200:
            result = resp.json()
            print(f"[sheets] Resultado: {result}")
            return result.get("ok", True)

        print(f"[sheets] Error HTTP {resp.status_code}: {resp.text[:300]}")
        return False

    except Exception as e:
        print(f"[sheets] Excepción: {e}")
        return False
