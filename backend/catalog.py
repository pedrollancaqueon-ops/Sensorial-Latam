import json
from pathlib import Path

_INDEX_PATH = Path(__file__).parent.parent / "catalog" / "catalog_index.json"

_catalog: list[dict] = []
_catalog_text: str = ""


def _load():
    global _catalog, _catalog_text
    data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
    _catalog = [item for item in data if item.get("image_path")]

    lines = []
    seen = set()
    for item in _catalog:
        key = f"{item['code']}|{item['component']}"
        if key in seen:
            continue
        seen.add(key)
        desc = item.get("description") or ""
        lines.append(f"- Código: {item['code']} | Componente: {item['component']} | {desc[:80]}")
    _catalog_text = "\n".join(lines)


_load()


def get_catalog_text() -> str:
    return _catalog_text


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


def get_all_codes() -> list[str]:
    return sorted({item["code"] for item in _catalog})
