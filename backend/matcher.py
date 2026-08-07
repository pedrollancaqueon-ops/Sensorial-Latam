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

IMPORTANTE: Algunas referencias tienen el componente como "#REF!" (dato roto del Excel). En ese caso usa SOLO la descripción de ingredientes y la imagen visual para hacer el match — el componente "#REF!" no es información relevante.

## PASO 1 — Clasifica el tipo de servicio por el contenedor y la presentación

Antes de buscar el código exacto, determina visualmente el tipo de servicio y asigna el campo `grid`:

- **Plato REDONDO blanco, presentación elegante, garnish fino**: Business Class → `grid: "BC"` — HLD0, HLD0 - Mechada, HLD0 - Merluza, HLD0 - Congrio, SPML HLD0, etc.
- **Bandeja NEGRA rectangular con plato separado, vaso, pan en bolsa/papel**: Economy Long Haul → `grid: "YC"` — FHS1 LH, FHB1 LH, FHLD LH, FHB LH, etc.
- **Bandeja NEGRA rectangular con 2–3 compartimentos integrados, sin plato separado**: Economy Regional → `grid: "YC"` — HLDR RG, HBE0 RG, HLD0 RG, HLD2 RG, HLDE RG, HB00 RG, etc.
- **Pan o sándwich sostenido en mano o en papel (sin bandeja visible)**: Es un componente suelto de Economy Regional → `grid: "YC"`. Clasifica por tipo: pan integral alargado = flat bread RG; pan de miga tostado = cold choice RG.
- **Bandeja PYC con plato o bowl separado, presentación semi-formal**: Premium Economy → `grid: "PYC"` — HBPY, SSPY, etc.
- **Bandeja de tripulación / servicio doméstico**: Crew → `grid: "CREW"` — HLDL, HB, SW00, SSPY, etc.

## PASO 2 — Identifica el código exacto

Compara la foto contra CADA imagen de referencia y elige la más similar. Considera:

1. **Ingrediente principal y tipo de preparación**: tipo de proteína (carne, pollo, pescado, tofu), tipo de pan (focaccia, integral, pan de hoja, hojaldre/empanada, ciabatta), tipo de fruta, tipo de salsa.
2. **Economy Regional (RG) — cómo distinguir entre códigos similares**:
   - Plato caliente con proteína (carne/pollo/pescado) + guarnición → HLD0 RG, HLD2 RG, HLDE RG, HLDR RG, HS01 RG
   - Hojaldre rectangular (tipo empanada dorada) + compota de fruta → HBE0 RG o HBER RG
   - Breakfast con fruta + pan rectangular (pan de hoja o miga integral) → HB00 RG o HB01 RG
   - La descripción de ingredientes de la referencia es clave para distinguirlos
3. **Un inspector puede fotografiar UN SOLO COMPONENTE** del servicio (solo el plato caliente, solo el sándwich, solo el queque, solo la fruta). La referencia puede mostrar ese mismo componente, no necesariamente toda la bandeja.
4. Para cada código puede haber **2 imágenes de referencia**: una del plato caliente y otra de la opción fría. Elige el código cuya referencia —cualquiera de las dos— más se parezca a la foto.
5. **Variantes SPML** (GFML / VGML / VLML / CHML): todas usan el mismo código base. No necesitas distinguir la variante dietética, solo confirma el código.
6. En caso de duda entre códigos similares (ej. FHB1 LH vs FHS1 LH): FHB1 LH es desayuno (sandwich integral con jamón, muffin o streusel); FHS1 LH es cena (plato caliente tipo pasta, cold choice focaccia, chocolate).
7. Si la confianza es inferior a 0.42, devuelve identificado: false. Entre 0.42 y 0.65 devuelve tu mejor opción igualmente.

Responde SOLO con JSON válido, sin texto adicional. Devuelve SIEMPRE tus mejores 1 a 3 candidatos, incluso si la confianza es baja — el evaluador humano decidirá cuál es correcto.
- `identificado: true` si el mejor candidato tiene confianza ≥ 0.42
- `identificado: false` si la confianza es baja, pero aun así incluye los candidatos en el array
- Solo devuelve `candidatos: []` si la imagen no muestra comida reconocible de ningún tipo

{"identificado": true, "grid": "BC", "candidatos": [{"codigo": "HLD0", "componente": "Main dish", "confianza": 0.85}, {"codigo": "HLD1", "componente": "Main dish", "confianza": 0.55}]}
Ejemplo baja confianza (muestra igual los candidatos):
{"identificado": false, "grid": "BC", "candidatos": [{"codigo": "HLD2", "componente": "Red Meat Dish", "confianza": 0.35}, {"codigo": "HLDE", "componente": "Red Meat Dish", "confianza": 0.28}]}"""


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
        comp = item["component"] if item["component"] != "#REF!" else "Plato de servicio"
        label = f"[Código: {item['code']} | {comp}{' | ' + desc if desc else ''}]"
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

        grid_detectado = result.get("grid", "").upper().strip()
        candidatos_raw = result.get("candidatos", [])

        # Si no hay candidatos de ningún tipo, la imagen no era reconocible
        if not candidatos_raw:
            return _no_match()

        candidatos = []
        for c in candidatos_raw[:3]:
            codigo     = c.get("codigo", "").upper().strip()
            componente = c.get("componente", "").strip()
            confianza  = float(c.get("confianza", 0))
            if not codigo:
                continue
            cat = find_best_match(codigo, componente)
            nombre_raw = cat["component"] if cat else componente
            nombre     = nombre_raw if nombre_raw != "#REF!" else componente
            candidatos.append({"codigo": codigo, "nombre": nombre, "confianza": confianza})

        if not candidatos:
            return _no_match()

        mejor = candidatos[0]
        cat   = find_best_match(mejor["codigo"], mejor["nombre"])
        imagen_referencia = cat["image_path"] if cat else ""

        identificado = result.get("identificado", False)

        return {
            "identificado":      identificado,
            "codigo":            mejor["codigo"],
            "nombre":            mejor["nombre"],
            "grid":              grid_detectado,
            "confianza":         mejor["confianza"],
            "imagen_referencia": imagen_referencia,
            "candidatos":        candidatos,
        }

    except Exception as e:
        print(f"[matcher] Error Gemini: {e}")
        return _no_match()


def _no_match() -> dict:
    return {"identificado": False, "codigo": "", "nombre": "", "grid": "", "confianza": 0.0, "imagen_referencia": "", "candidatos": []}
