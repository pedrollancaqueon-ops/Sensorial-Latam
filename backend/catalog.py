import datetime
import json
from pathlib import Path

_INDEX_PATH = Path(__file__).parent.parent / "catalog" / "catalog_index.json"

_catalog: list[dict] = []

# Códigos de snack que rotan mensual x4 aunque vivan en un grid bimestral (YC).
_SNACK_CODES = {"SNK5", "SAM2", "SPM2", "SNK4", "SNA0"}


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
    es_yc = source == "SCL-YC GRID INTER"

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


_GRID_MAP = {
    "BC":   "SCL-BC GRID",
    "CREW": "SCL-CREW INTER GRID",
    "PYC":  "SCL-PYC INTER GRID",
    "YC":   "SCL-YC GRID INTER",
}


def get_catalog_images(fecha: datetime.date | None = None, grid: str | None = None) -> list[dict]:
    """Una imagen representativa por código activo en el ciclo vigente.
    grid: 'BC', 'CREW', 'PYC' o 'YC' — si se omite, devuelve todos los grids.
    """
    fecha = fecha or datetime.date.today()
    mes = fecha.month
    source_filter = _GRID_MAP.get((grid or "").upper())

    seen_codes: set[str] = set()
    result = []
    for item in _catalog:
        if source_filter and item.get("source") != source_filter:
            continue
        patron = _patron_para(item.get("source", ""), item.get("code", ""))
        if item.get("cycle") != patron(mes):
            continue
        code = item["code"]
        if code in seen_codes:
            continue
        seen_codes.add(code)
        result.append(item)
    return result


def get_all_codes() -> list[str]:
    return sorted({item["code"] for item in _catalog})
