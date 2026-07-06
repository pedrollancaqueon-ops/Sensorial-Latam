import os
import base64
import json
import re
from pathlib import Path

import google.generativeai as genai
from catalog import get_catalog_images, find_best_match

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
_model = genai.GenerativeModel("gemini-2.5-flash-lite")

_BASE_PATH = Path(__file__).parent.parent

_PROMPT = """Eres un asistente de control de calidad de catering aéreo de LATAM Airlines.

La PRIMERA imagen es la foto tomada a bordo del plato a identificar.
Las imágenes siguientes son las referencias del catálogo vigente para este período, cada una etiquetada con su código y componente.

Compara visualmente la foto del plato con las referencias e identifica el mejor match.
Responde SOLO con JSON válido, sin texto adicional:
{
  "identificado": true,
  "codigo": "XXXX",
  "componente": "nombre del componente",
  "confianza": 0.85
}
Si ninguna referencia calza claramente:
{
  "identificado": false,
  "codigo": "",
  "componente": "",
  "confianza": 0.0
}"""


def identificar(foto_base64: str) -> dict:
    img_data = base64.b64decode(foto_base64)
    user_photo = {"mime_type": "image/jpeg", "data": img_data}

    contents = [_PROMPT, user_photo]

    ref_count = 0
    for item in get_catalog_images():
        img_path = _BASE_PATH / item["image_path"]
        if not img_path.exists():
            continue
        label = f"[Código: {item['code']} | {item['component']}]"
        contents.append(label)
        contents.append({"mime_type": "image/jpeg", "data": img_path.read_bytes()})
        ref_count += 1

    print(f"[matcher] Enviando foto + {ref_count} imágenes de referencia a Gemini")

    try:
        response = _model.generate_content(contents)
        text = response.text.strip()

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            return _no_match()

        result = json.loads(json_match.group())

        if not result.get("identificado"):
            return _no_match()

        codigo     = result.get("codigo", "").upper().strip()
        componente = result.get("componente", "").strip()
        confianza  = float(result.get("confianza", 0))

        catalog_item = find_best_match(codigo, componente)
        nombre = catalog_item["component"] if catalog_item else componente

        return {
            "identificado": True,
            "codigo":       codigo,
            "nombre":       nombre,
            "confianza":    confianza,
        }

    except Exception as e:
        print(f"[matcher] Error Gemini: {e}")
        return _no_match()


def _no_match() -> dict:
    return {"identificado": False, "codigo": "", "nombre": "", "confianza": 0.0}
