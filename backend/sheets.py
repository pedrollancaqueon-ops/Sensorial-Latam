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

        if r1.status_code == 200:
            result = r1.json()
            print(f"[sheets] Resultado directo: {result}")
            return result.get("ok", True)

        if r1.status_code in (301, 302, 303, 307, 308):
            location = r1.headers.get("Location", "")
            print(f"[sheets] Redirect a: {location[:80]}")

            # Paso 2: GET al redirect — recupera la respuesta de doPost
            r2 = requests.get(
                location,
                timeout=15,
                verify=_SSL_VERIFY,
            )
            print(f"[sheets] Paso 2 GET: {r2.status_code} — {r2.text[:200]}")

            if r2.status_code == 200:
                try:
                    result = r2.json()
                    print(f"[sheets] Resultado: {result}")
                    return result.get("ok", True)
                except Exception:
                    # La respuesta no es JSON pero el script corrió igual
                    print("[sheets] Respuesta no JSON — asumiendo ok")
                    return True

        print(f"[sheets] Error inesperado: {r1.status_code} — {r1.text[:200]}")
        return False

    except Exception as e:
        print(f"[sheets] Excepcion: {e}")
        return False
