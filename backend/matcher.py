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

_PROMPT = """Eres un experto en control de calidad de catering aéreo de LATAM Airlines SCL.

La PRIMERA imagen es la foto del inspector a bordo. Las imágenes siguientes son referencias del catálogo vigente, etiquetadas con [Código | Componente | Descripción de ingredientes].

## PASO 1 — Clasifica el tipo de servicio por el contenedor y la presentación

Antes de buscar el código exacto, determina visualmente el tipo de servicio y asigna el campo `grid`:

- **Plato REDONDO blanco, presentación elegante, garnish fino**: Business Class → `grid: "BC"` — HLD0, HLD0 - Mechada, HLD0 - Merluza, HLD0 - Congrio, SPML HLD0, etc.
- **Bandeja NEGRA rectangular, plato separado, vaso, pan en bolsa/papel**: Economy Long Haul → `grid: "YC"` — FHS1 LH, FHB1 LH, FHLD LH, FHB LH, etc.
- **Bandeja NEGRA rectangular con 2–3 compartimentos, sin plato separado**: Economy Regional → `grid: "YC"` — HLDR SPML RG, HBE0 SPML RG, HBE0 RG, HLDR RG, etc.
- **Pan o sándwich envuelto en papel (focaccia, ciabatta, integral, pan de hoja)**: Cold choice / breakfast → deduce el grid por el contenedor o el código más cercano.
- **Bandeja PYC con plato o bowl separado, presentación semi-formal**: Premium Economy → `grid: "PYC"` — HBPY, SSPY, etc.
- **Bandeja de tripulación / servicio doméstico**: Crew → `grid: "CREW"` — HLDL, HB, SW00, SSPY, etc.

## PASO 2 — Identifica el código exacto

Compara la foto contra CADA imagen de referencia y elige la más similar. Considera:

1. **Ingrediente principal**: tipo de proteína (carne, pollo, pescado, tofu), tipo de pan (focaccia, integral, pan de hoja, ciabatta), tipo de fruta.
2. **Un inspector puede fotografiar UN SOLO COMPONENTE** del servicio (solo el plato caliente, solo el sándwich, solo el queque, solo la fruta). La referencia puede mostrar ese mismo componente, no necesariamente toda la bandeja.
3. Para cada código puede haber **2 imágenes de referencia**: una del plato caliente y otra de la opción fría. Elige el código cuya referencia —cualquiera de las dos— más se parezca a la foto.
4. **Variantes SPML** (GFML / VGML / VLML / CHML): todas usan el mismo código base. No necesitas distinguir la variante dietética, solo confirma el código.
5. En caso de duda entre códigos similares (ej. FHB1 LH vs FHS1 LH): FHB1 LH es desayuno (sandwich integral con jamón, muffin o streusel); FHS1 LH es cena (plato caliente tipo pasta, cold choice focaccia, chocolate).
6. Si la confianza es inferior a 0.55, devuelve identificado: false.

Responde SOLO con JSON válido, sin texto adicional:
{"identificado": true, "codigo": "CÓDIGO", "componente": "nombre del componente fotografiado", "grid": "BC", "confianza": 0.85}
Si ninguna referencia calza claramente:
{"identificado": false, "codigo": "", "componente": "", "grid": "", "confianza": 0.0}"""


def identificar(foto_base64: str, grid: str | None = None) -> dict:
    img_data = base64.b64decode(foto_base64)
    user_photo = {"mime_type": "image/jpeg", "data": img_data}

    contents = [_PROMPT, user_photo]

    ref_count = 0
    for item in get_catalog_images(grid=grid):
        img_path = _BASE_PATH / item["image_path"]
        if not img_path.exists():
            continue
        desc = item.get("description", "")
        label = f"[Código: {item['code']} | {item['component']}{' | ' + desc if desc else ''}]"
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

        codigo         = result.get("codigo", "").upper().strip()
        componente     = result.get("componente", "").strip()
        confianza      = float(result.get("confianza", 0))
        grid_detectado = result.get("grid", "").upper().strip()

        catalog_item = find_best_match(codigo, componente)
        nombre            = catalog_item["component"]   if catalog_item else componente
        imagen_referencia = catalog_item["image_path"]  if catalog_item else ""

        return {
            "identificado":      True,
            "codigo":            codigo,
            "nombre":            nombre,
            "grid":              grid_detectado,
            "confianza":         confianza,
            "imagen_referencia": imagen_referencia,
        }

    except Exception as e:
        print(f"[matcher] Error Gemini: {e}")
        return _no_match()


def _no_match() -> dict:
    return {"identificado": False, "codigo": "", "nombre": "", "grid": "", "confianza": 0.0, "imagen_referencia": ""}
