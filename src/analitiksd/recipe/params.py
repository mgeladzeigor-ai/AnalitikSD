from __future__ import annotations

import re
from typing import Any

_PLACEHOLDER = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def resolve_params(params: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, str]:
    """Развернуть спецификацию параметров в плоскую карту значений.

    Для каждого параметра берётся override (если задан), иначе default.
    Поддерживаемый тип в MVP: date_range -> ключи "<name>.from" и "<name>.to".
    """
    overrides = overrides or {}
    flat: dict[str, str] = {}
    for name, spec in params.items():
        ptype = spec["type"]
        value = overrides.get(name, spec["default"])
        if ptype == "date_range":
            flat[f"{name}.from"] = value["from"]
            flat[f"{name}.to"] = value["to"]
        else:
            raise ValueError(f"Unsupported param type: {ptype}")
    return flat


def substitute(obj: Any, values: dict[str, str]) -> Any:
    """Рекурсивно подставить плейсхолдеры {{key}} из values в структуру obj.

    Если строка целиком равна одному плейсхолдеру, подставляется значение как есть.
    Неизвестный ключ -> KeyError (тихо ничего не глотаем).
    """
    if isinstance(obj, dict):
        return {k: substitute(v, values) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(v, values) for v in obj]
    if isinstance(obj, str):
        return _sub_str(obj, values)
    return obj


def _sub_str(s: str, values: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"Unknown placeholder: {key}")
        return str(values[key])

    return _PLACEHOLDER.sub(repl, s)
