import io
import os
import base64
import json
import re
from pathlib import Path

from PIL import Image

import google.generativeai as genai
from catalog import get_catalog_images, find_best_match, get_visual_twins, _GRID_MAP

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
_model = genai.GenerativeModel("gemini-2.5-flash-lite")

_BASE_PATH = Path(__file__).parent.parent
_REFS_PATH = Path(__file__).parent / "referencias"


def _parse_frontend_ref(stem: str) -> tuple[list[str], str]:
    """Parse IMG filename stem → (codes, label).

    IMG_HLD0_y_HLD2  → (["HLD0", "HLD2"], "HLD0 / HLD2")
    IMG_FHLD_Frio    → (["FHLD"], "FHLD (Frío)")
    IMG_HLD2_Churrasco → (["HLD2"], "HLD2 (Churrasco)")
    IMG_FHB0         → (["FHB0"], "FHB0")
    """
    if "_y_" in stem:
        parts = stem.split("_y_")
        return parts, " / ".join(parts)
    idx = stem.find("_")
    if idx != -1:
        code = stem[:idx]
        descriptor = stem[idx + 1:].replace("_", " ")
        return [code], f"{code} ({descriptor})"
    return [stem], stem


def _compress_to_jpeg(path: Path, max_px: int = 1024, quality: int = 80) -> bytes:
    with Image.open(path) as img:
        img = img.convert("RGB")
        ratio = min(max_px / img.width, max_px / img.height, 1.0)
        if ratio < 1.0:
            img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()


def _get_frontend_refs() -> list[dict]:
    """Return list of {data, codes, label} for IMG_*.png/jpg in backend/referencias/, pre-compressed."""
    result = []
    for path in sorted(_REFS_PATH.glob("IMG_*.*")):
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        stem = path.stem[4:]  # strip leading "IMG_"
        codes, label = _parse_frontend_ref(stem)
        data = _compress_to_jpeg(path)
        kb_orig = path.stat().st_size // 1024
        kb_comp = len(data) // 1024
        print(f"[matcher] Ref manual: {path.name} {kb_orig}KB -> {kb_comp}KB")
        result.append({"data": data, "codes": codes, "label": label})
    return result


_FRONTEND_REFS = _get_frontend_refs()

_PROMPT_RESCUE = """Eres un experto en catering aéreo LATAM. La imagen muestra comida de a bordo.
Identifica el tipo de servicio y el código más probable. Devuelve JSON con al menos 1 candidato.
Reglas rápidas:
- Plato blanco redondo elegante → BC (HLD0, HLD2, HLDE, LHLD, HLD0 - Mechada, HLD0 - Merluza, HLD1)
- Bandeja negra con compartimentos → YC Economy (HLD0 RG, HLD2 RG, HBE0 RG, HB00 RG, FHLD LH, FHB1 LH)
- Bowl blanco con fideos negros → PYC (HLDL)
- Base naranja/calabaza + medallón oscuro → HLD2, HLDE, LHLD
- Base blanca/crema + medallón mechada → HLD0 - Mechada
- Hojaldre/empanada dorada + fruta → HBE0 RG, HBER RG
Formato: {"identificado": false, "grid": "BC", "candidatos": [{"codigo": "HLD2", "componente": "Red Meat Dish", "confianza": 0.30}]}"""

# Map code → set of codes that share a frontend image (for twin expansion).
_FRONTEND_CODE_TWINS: dict[str, list[str]] = {}
for _ref in _FRONTEND_REFS:
    if len(_ref["codes"]) > 1:
        for _c in _ref["codes"]:
            _FRONTEND_CODE_TWINS[_c] = _ref["codes"]


_PROMPT = """Eres un experto en control de calidad de catering aéreo de LATAM Airlines SCL.

La PRIMERA imagen es la foto del inspector a bordo. Las imágenes siguientes son referencias del catálogo vigente, etiquetadas con [Código | Componente | Descripción de ingredientes].

REGLA ABSOLUTA (no negociable): Si la imagen muestra CUALQUIER preparación culinaria —aunque la foto sea oscura, en ángulo, parcial, borrosa o de baja calidad— DEBES devolver al menos 1 candidato. Una mala foto no justifica candidatos vacíos; usa tu mejor juicio visual aunque la confianza sea 0.10. `candidatos: []` solo es válido si la imagen literalmente no contiene comida (foto de una persona, texto, objeto no alimenticio).

IMPORTANTE: Algunas referencias tienen el componente como "#REF!" (dato roto del Excel). En ese caso usa SOLO la descripción de ingredientes y la imagen visual para hacer el match — el componente "#REF!" no es información relevante.

## PASO 1 — Clasifica el tipo de servicio por el contenedor y la presentación

Antes de buscar el código exacto, determina visualmente el tipo de servicio y asigna el campo `grid`:

- **Plato REDONDO blanco, presentación elegante, garnish fino**: Business Class → `grid: "BC"` — HLD0, HLD0 - Mechada, HLD0 - Merluza, HLD0 - Congrio, SPML HLD0, etc.
- **Bandeja NEGRA rectangular, con plato o bowl blanco/cerámico encima + vaso + pan en bolsa o papel SEPARADO**: Economy Long Haul → `grid: "YC"` — FHS LH, FHS LH - Normal, FHS1 LH, FHB1 LH, FHLD LH, FHB LH, etc.
- **Bandeja NEGRA rectangular con 2–3 compartimentos INTEGRADOS en la misma bandeja, sin plato separado encima**: Economy Regional → `grid: "YC"` — HLD0 RG, HLD2 RG, HLDE RG, HLDR RG, HBE0 RG, HB00 RG, etc.
  - DIFERENCIADOR CLAVE RG vs LH: En Regional el PAN PLANO (flat bread, focaccia) está DENTRO de un compartimento izquierdo de la bandeja negra. No hay plato blanco encima. Si ves la comida directamente en los compartimentos de la bandeja negra → es RG.
  - En Long Haul siempre hay un plato o bowl blanco/cerámico separado colocado SOBRE la bandeja. El pan viene en bolsita plástica o papel aparte.
- **Pan o sándwich sostenido en mano o en papel (sin bandeja visible)**: Es un componente suelto de Economy Regional → `grid: "YC"`. Clasifica por tipo: pan integral alargado = flat bread RG; pan de miga tostado = cold choice RG.
- **Bowl blanco redondo con tallarines NEGROS (tinta de calamar) + carne en tiras + champiñones**: Premium Economy/PYC → `grid: "PYC"` → **HLDL**
- **Bandeja PYC con plato o bowl separado, presentación semi-formal**: Premium Economy → `grid: "PYC"` — HBPY, SSPY, HLDL, etc.
- **Bandeja de tripulación / servicio doméstico**: Crew → `grid: "CREW"` — HLDL, HB, SW00, SSPY, etc.

## PASO 2 — Identifica el código exacto

Compara la foto contra CADA imagen de referencia y elige la más similar. Considera:

1. **Ingrediente principal y tipo de preparación**: tipo de proteína (carne, pollo, pescado, tofu), tipo de pan (focaccia, integral, pan de hoja, hojaldre/empanada, ciabatta), tipo de fruta, tipo de salsa.
2. **Business Class (BC) — cómo distinguir entre platos calientes**:
   - **BASE BLANCA** (crema de papa y trufa) + medallón de mechada pulled beef + cebollas asadas/quemadas negras + aceite verde → **HLD0 - Mechada**
   - **BASE NARANJA** (puré de calabaza) + medallón de res grillado + salsa oscura de vino + cebollas moradas caramelizadas → HLD2, HLDE, LHLD, LHD3
   - **Pastel amarillo rectangular** (pastel de choclo) sobre tomate concasse → HLD0, HLD1
   - **Proteína de mar** (merluza, congrio) + caldo o crema → HLD0 - Merluza, HLD0 - Congrio
   - El COLOR DE LA BASE es el diferenciador principal entre mechada (blanca) y res (naranja)
3. **Economy Regional (RG) — cómo distinguir entre códigos similares**:
   - REGLA PRINCIPAL: bandeja negra con compartimentos integrados (sin plato blanco encima) = siempre RG, NUNCA LH.
   - Pollo/carne/pescado en salsa + arroz + pan plano en compartimento izquierdo → HLD0 RG (pollo) o HLD2 RG (res)
   - Hojaldre rectangular (tipo empanada dorada) + compota de fruta → HBE0 RG o HBER RG
   - Breakfast con fruta + pan rectangular (pan de hoja o miga integral) → HB00 RG o HB01 RG
   - Omelette plegado + tomate cherry + papas rostizadas en plato blanco → puede ser HB00 (CREW, plato blanco elegante) o HB00 RG (Economy Regional, bandeja negra). Si está en plato blanco redondo, priorizar HB00 CREW
   - La descripción de ingredientes de la referencia es clave para distinguirlos
3. **Un inspector puede fotografiar UN SOLO COMPONENTE** del servicio (solo el plato caliente, solo el sándwich, solo el queque, solo la fruta). La referencia puede mostrar ese mismo componente, no necesariamente toda la bandeja.
4. Para cada código puede haber **2 imágenes de referencia**: una del plato caliente y otra de la opción fría. Elige el código cuya referencia —cualquiera de las dos— más se parezca a la foto.
5. **Variantes dietéticas SPML** (VGML, CHML, GFML, VLML): el código incluye el prefijo SPML + el tipo de servicio. Usa estos códigos exactos:
   - Economy Regional (bandeja negra con compartimentos integrados): **VGML HLD0 RG**, **VGML HS01 RG** / **CHML HLD0**, **CHML HS01**
   - Economy Long Haul (bandeja negra con plato blanco encima): **VGML FHS1** / **CHML FHS1**
   - Las imágenes de referencia etiquetadas como "VGML" y "CHML" muestran la presentación visual — determina el código exacto según el tipo de servicio (RG o LH).
6. En caso de duda entre códigos similares (ej. FHB1 LH vs FHS1 LH): FHB1 LH es desayuno (sandwich integral con jamón, muffin o streusel); FHS1 LH es cena (plato caliente tipo pasta, cold choice focaccia, chocolate).

## RESPUESTA

Devuelve SIEMPRE tus mejores 1 a 3 candidatos — aunque la confianza sea baja. El evaluador humano elegirá cuál es correcto.

NUNCA devuelvas `candidatos: []` si hay comida en la imagen. Si no puedes distinguir el código exacto, elige los candidatos más probables por tipo de servicio y proteína, aunque la confianza sea 0.10.

- `identificado: true` si el mejor candidato tiene confianza ≥ 0.38
- `identificado: false` si es tu mejor intento pero con baja confianza — igualmente incluye los candidatos

Responde SOLO con JSON válido, sin texto adicional:
{"identificado": true, "grid": "BC", "candidatos": [{"codigo": "HLD2", "componente": "Red Meat Dish", "confianza": 0.82}, {"codigo": "LHLD", "componente": "Red Meat Dish", "confianza": 0.65}]}
Ejemplo baja confianza:
{"identificado": false, "grid": "BC", "candidatos": [{"codigo": "HLD2", "componente": "Red Meat Dish", "confianza": 0.35}, {"codigo": "HLDE", "componente": "Red Meat Dish", "confianza": 0.28}]}"""


def _rescue_identificar(img_data: bytes) -> list[dict] | None:
    """Retry con prompt simplificado cuando Gemini devuelve candidatos vacíos."""
    try:
        resp = _model.generate_content([
            _PROMPT_RESCUE,
            {"mime_type": "image/jpeg", "data": img_data},
        ])
        text = resp.text.strip()
        print(f"[matcher] Rescate Gemini: {text[:300]}")
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        result = json.loads(m.group())
        raw = result.get("candidatos", [])
        return raw if raw else None
    except Exception as e:
        print(f"[matcher] Error rescate Gemini: {e}")
        return None


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

    # Imágenes de referencia manuales (IMG_*.png en frontend/, pre-comprimidas)
    for ref in _FRONTEND_REFS:
        contents.append(f"[Referencia manual: {ref['label']}]")
        contents.append({"mime_type": "image/jpeg", "data": ref["data"]})
        ref_count += 1

    print(f"[matcher] Enviando foto + {ref_count} imágenes de referencia a Gemini")

    try:
        response = _model.generate_content(contents)
        text = response.text.strip()
        print(f"[matcher] Respuesta Gemini (primeros 400 chars): {text[:400]}")

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            grid_detectado = result.get("grid", "").upper().strip()
            candidatos_raw = result.get("candidatos", [])
        else:
            print("[matcher] No se encontró JSON en la respuesta — reintentando con rescate")
            result = {}
            grid_detectado = ""
            candidatos_raw = []

        # Si no hay candidatos, reintenta con prompt de rescate antes de rendirse
        if not candidatos_raw:
            print("[matcher] Candidatos vacíos — reintentando con prompt de rescate")
            rescue = _rescue_identificar(img_data)
            if rescue:
                candidatos_raw = rescue
            else:
                return _no_match()

        candidatos = []
        codigos_vistos: set[str] = set()
        for c in candidatos_raw[:6]:
            codigo     = c.get("codigo", "").upper().strip()
            componente = c.get("componente", "").strip()
            confianza  = float(c.get("confianza", 0))
            if not codigo or codigo in codigos_vistos:
                continue
            codigos_vistos.add(codigo)
            cat = find_best_match(codigo, componente)
            nombre_raw = cat["component"] if cat else componente
            nombre     = nombre_raw if nombre_raw != "#REF!" else componente
            candidatos.append({"codigo": codigo, "nombre": nombre, "confianza": confianza})

        if not candidatos:
            return _no_match()

        # Expandir con gemelos de imagen manual (ej: HLD0_y_HLD2 → agregar HLD2 si Gemini dijo HLD0).
        for c in list(candidatos):
            for twin_code in _FRONTEND_CODE_TWINS.get(c["codigo"], []):
                if twin_code == c["codigo"] or twin_code in codigos_vistos:
                    continue
                codigos_vistos.add(twin_code)
                cat = find_best_match(twin_code, c["nombre"])
                nombre_raw = cat["component"] if cat else c["nombre"]
                nombre = nombre_raw if nombre_raw != "#REF!" else c["nombre"]
                candidatos.append({"codigo": twin_code, "nombre": nombre, "confianza": 0.0})

        # Expandir con gemelos visuales: códigos activos que comparten el mismo
        # componente del mejor candidato (ej: todos los "Red Meat Dish" BC).
        # Se excluyen sub-variantes (ej: "HLD0 - Mechada") porque son para platos
        # distintos aunque compartan componente en el catálogo.
        mejor_nombre = candidatos[0]["nombre"]
        grid_sources = _GRID_MAP.get(grid_detectado, set())
        if mejor_nombre and grid_sources:
            twins = get_visual_twins(mejor_nombre, grid_sources)
            for twin_code in twins:
                if twin_code in codigos_vistos:
                    continue
                if " - " in twin_code:  # sub-variante (HLD0 - Mechada, etc.)
                    continue
                codigos_vistos.add(twin_code)
                cat = find_best_match(twin_code, mejor_nombre)
                nombre_raw = cat["component"] if cat else mejor_nombre
                nombre     = nombre_raw if nombre_raw != "#REF!" else mejor_nombre
                candidatos.append({"codigo": twin_code, "nombre": nombre, "confianza": 0.0})

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
