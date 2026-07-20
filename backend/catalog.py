import datetime
import json
from pathlib import Path

_INDEX_PATH = Path(__file__).parent.parent / "catalog" / "catalog_index.json"

_catalog: list[dict] = []

# Códigos de snack que rotan mensual x4 aunque vivan en un grid bimestral (YC).
_SNACK_CODES = {"SNK5", "SAM2", "SPM2", "SNK4", "SNA0"}

# Todos los sources que corresponden al grid YC (Economy LH y REG).
_YC_SOURCES = {"SCL-YC GRID INTER", "15.07.2026-SCL-YC GRID INTER"}

# Prioridad de componente para elegir la imagen más representativa por código.
# Mayor score = más útil para que Gemini identifique visualmente el plato.
_COMP_PRIORITY: list[tuple[int, list[str]]] = [
    (10, ["signature dish", "signature"]),
    (10, ["red meat dish"]),
    (9,  ["main dish"]),
    (9,  ["non veggie choice", "non veggie sandwich"]),
    (9,  ["cold choice"]),
    (9,  ["sandwich option"]),
    (9,  ["plato sándwich", "plato sandwich"]),
    (9,  ["flat bread"]),
    (8,  ["plato huevo o dulce", "plato huevo"]),
    # "sweet product" va ANTES de "product" (regla más específica primero: evita que
    # "Sweet Product" herede score 8 por contener la palabra "product").
    (3,  ["sweet product", "mini chocolate", "healty snack"]),
    (8,  ["product"]),
    (7,  ["bakery"]),
    (7,  ["bread"]),
    (6,  ["#ref"]),
    (4,  ["appetizer"]),
    (4,  ["individual greens salad"]),
    (3,  ["magdalena", "dessert"]),
    (2,  ["fruit", "fruta", "garnishes", "rice cracker"]),
    (1,  ["extras", "bulk", "butter", "salt", "grissinis"]),
]

# Componentes que representan la opción fría/sándwich (se mandan como imagen secundaria).
# También cualquier componente con "sandwich" en el nombre (cubre "Plato Sándwich", etc.)
_COLD_COMP_KEYWORDS = {"cold choice", "sandwich option", "flat bread", "plato sándwich", "plato sandwich"}

# Score mínimo para incluir la imagen «principal» (evita mandar chocolate/garnish como referencia).
_MIN_MAIN_SCORE = 6


def _comp_score(component: str) -> int:
    c = (component or "").lower()
    for score, keywords in _COMP_PRIORITY:
        if any(kw in c for kw in keywords):
            return score
    return 5


def _is_cold(component: str) -> bool:
    c = (component or "").lower()
    return any(kw in c for kw in _COLD_COMP_KEYWORDS)


def _load():
    global _catalog
    data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
    _catalog = [item for item in data if item.get("image_path")]


_load()


# ── Patrones de ciclo por fecha ─────────────────────────────────────────────
# Cada patrón mapea mes (1-12) -> número de ciclo activo, según las fechas
# confirmadas por Pedro para cada categoría del catálogo.

def _ciclo_mensual_x4(mes: int) -> int:
    # Ene/May/Sep=1, Feb/Jun/Oct=2, Mar/Jul/Nov=3, Abr/Ago/Dic=4 (BC, CREW, PYC)
    return ((mes - 1) % 4) + 1


def _ciclo_bimestral_par(mes: int) -> int:
    # Ene-Feb/May-Jun/Sep-Oct=1, Mar-Abr/Jul-Ago/Nov-Dic=2 (Economy LH y REG)
    return 1 if ((mes - 1) // 2) % 2 == 0 else 2


def _ciclo_spml_alternado(mes: int) -> int:
    # Meses impares=1, pares=2 (SPML Business / Premium Economy)
    return 1 if mes % 2 == 1 else 2


def _ciclo_spml_trimestral(mes: int) -> int:
    # Ene-Feb-Mar/Jul-Ago-Sep=1, Abr-May-Jun/Oct-Nov-Dic=2 (SPML Economy)
    return 1 if (mes - 1) % 6 < 3 else 2


def _patron_para(source: str, code: str):
    code_u = (code or "").upper()
    es_spml = "SPML" in code_u
    # Cualquier source del grid YC (incluyendo el nuevo 15.07.2026) usa ciclo bimestral.
    es_yc = source in _YC_SOURCES

    prefijo = code_u.split()[0].split("-")[0] if code_u else ""
    if prefijo in _SNACK_CODES and not es_spml:
        return _ciclo_mensual_x4

    if es_spml:
        return _ciclo_spml_trimestral if es_yc else _ciclo_spml_alternado

    return _ciclo_bimestral_par if es_yc else _ciclo_mensual_x4


def get_catalog_text(fecha: datetime.date | None = None) -> str:
    fecha = fecha or datetime.date.today()
    mes = fecha.month

    lines = []
    seen = set()
    for item in _catalog:
        patron = _patron_para(item.get("source", ""), item.get("code", ""))
        if item.get("cycle") != patron(mes):
            continue

        key = f"{item['code']}|{item['component']}"
        if key in seen:
            continue
        seen.add(key)
        desc = item.get("description") or ""
        lines.append(f"- Código: {item['code']} | Componente: {item['component']} | {desc[:80]}")
    return "\n".join(lines)


def find_best_match(code: str, component: str) -> dict | None:
    code = code.upper().strip()
    comp = component.lower().strip()
    for item in _catalog:
        if item["code"].upper() == code and item["component"].lower() == comp:
            return item
    for item in _catalog:
        if item["code"].upper() == code:
            return item
    return None


_GRID_MAP: dict[str, set[str]] = {
    "BC":       {"SCL-BC GRID", "SQT BC JUN-SEPT 2026"},
    "CREW":     {"SCL-CREW INTER GRID"},
    "PYC":      {"SCL-PYC INTER GRID"},
    "YC":       {"SCL-YC GRID INTER", "15.07.2026-SCL-YC GRID INTER"},
    "CREW_DOM": {"01.03.2026-SCL-CREW DOM GRID"},
    "PE_DOM":   {"11.12.2024-SCL-PYC DOM", "01.07.2026-SCL-PYC DOM GRID"},
}

# SPML se filtra por patrón de código, no por source
_SPML_KEY = "SPML"


def get_catalog_images(fecha: datetime.date | None = None, grid: str | None = None) -> list[dict]:
    """Imágenes de referencia por código activo en el ciclo vigente.

    Por cada código devuelve hasta 2 imágenes:
    - La imagen «principal» con mayor prioridad de componente (plato caliente, main dish, etc.)
    - La imagen «fría» si existe (cold choice, sandwich option, flat bread) y es distinta.
    Esto permite identificar tanto el plato caliente como el sándwich del mismo servicio.

    grid: 'BC', 'CREW', 'PYC' o 'YC' — si se omite, devuelve todos los grids.
    """
    fecha = fecha or datetime.date.today()
    mes = fecha.month
    grid_key = (grid or "").upper()
    is_spml = grid_key == _SPML_KEY
    source_filter: set[str] | None = None if is_spml else _GRID_MAP.get(grid_key)

    # Para cada código: mejor imagen «principal» y mejor imagen «fría».
    # Cuando dos ítems tienen el mismo score, el último procesado gana (>= prefiere
    # los ítems del nuevo grid que aparecen al final de catalog_index.json).
    best_main: dict[str, tuple[int, dict]] = {}
    best_cold: dict[str, tuple[int, dict]] = {}

    for item in _catalog:
        if is_spml and "SPML" not in str(item.get("code", "")).upper():
            continue
        if not is_spml and source_filter and item.get("source") not in source_filter:
            continue
        patron = _patron_para(item.get("source", ""), item.get("code", ""))
        if item.get("cycle") != patron(mes):
            continue

        code = item["code"]
        comp = item.get("component", "")
        score = _comp_score(comp)

        if _is_cold(comp):
            if code not in best_cold or score >= best_cold[code][0]:
                best_cold[code] = (score, item)
        else:
            if code not in best_main or score >= best_main[code][0]:
                best_main[code] = (score, item)

    result: list[dict] = []
    seen_paths: set[str] = set()
    for code in set(best_main) | set(best_cold):
        # Imagen principal solo si tiene suficiente score (evita chocolate/garnish como referencia).
        if code in best_main and best_main[code][0] >= _MIN_MAIN_SCORE:
            path = best_main[code][1].get("image_path", "")
            if path and path not in seen_paths:
                result.append(best_main[code][1])
                seen_paths.add(path)
        # Imagen fría/sándwich siempre que exista (es muy útil para identificación).
        if code in best_cold:
            path = best_cold[code][1].get("image_path", "")
            if path and path not in seen_paths:
                result.append(best_cold[code][1])
                seen_paths.add(path)
        # Si no hubo imagen principal con score suficiente, incluir la fría como única referencia.
        # (ya incluida arriba; este bloque solo sirve si no hay cold tampoco → incluir main sin umbral)
        if code not in best_cold and code in best_main and best_main[code][0] < _MIN_MAIN_SCORE:
            path = best_main[code][1].get("image_path", "")
            if path and path not in seen_paths:
                result.append(best_main[code][1])
                seen_paths.add(path)
    return result


def get_all_codes() -> list[str]:
    return sorted({item["code"] for item in _catalog})
