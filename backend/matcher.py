import os
import base64
import json
import re
import google.generativeai as genai
from catalog import get_catalog_text, find_best_match

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
_model = genai.GenerativeModel("gemini-2.5-flash-lite")

_PROMPT_TEMPLATE = """Eres un asistente de control de calidad de catering aéreo de LATAM Airlines.
Se te muestra la foto de un plato o componente de servicio a bordo.

Tu tarea es identificar a cuál de los siguientes ítems del catálogo corresponde la imagen.
Responde SOLO con un JSON válido, sin texto adicional, con este formato exacto:
{{
  "identificado": true,
  "codigo": "XXXX",
  "componente": "Nombre del componente",
  "confianza": 0.0
}}

Si no puedes identificarlo con certeza, responde:
{{
  "identificado": false,
  "codigo": "",
  "componente": "",
  "confianza": 0.0
}}

Catálogo disponible:
{catalog}
"""


def identificar(foto_base64: str) -> dict:
    prompt = _PROMPT_TEMPLATE.format(catalog=get_catalog_text())

    img_data = base64.b64decode(foto_base64)
    image_part = {"mime_type": "image/jpeg", "data": img_data}

    try:
        response = _model.generate_content([prompt, image_part])
        text = response.text.strip()

        # Extraer JSON de la respuesta aunque venga con markdown
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            return _no_match()

        result = json.loads(json_match.group())

        if not result.get("identificado"):
            return _no_match()

        codigo    = result.get("codigo", "").upper().strip()
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
