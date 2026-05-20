from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .artifacts import ValidationError

SCHEMA_DIR = Path(__file__).parent / "schemas"


def load_schema(name: str) -> dict[str, Any]:
    path = SCHEMA_DIR / f"{name}.schema.json"
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}: invalid JSON schema: {exc}") from exc
    if not isinstance(schema, dict):
        raise ValidationError(f"{path}: schema must be an object")
    return schema


def _type_matches(value: object, expected: object) -> bool:
    types = expected if isinstance(expected, list) else [expected]
    for typ in types:
        if typ == "string" and isinstance(value, str):
            return True
        if typ == "array" and isinstance(value, list):
            return True
        if typ == "object" and isinstance(value, dict):
            return True
        if typ == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if typ == "boolean" and isinstance(value, bool):
            return True
        if typ == "null" and value is None:
            return True
    return False


def validate_data_against_schema(data: dict[str, object], schema_name: str, source: Path) -> None:
    schema = load_schema(schema_name)
    required = schema.get("required", [])
    if isinstance(required, list):
        missing = [str(field) for field in required if field not in data or data[field] in ("", [])]
        if missing:
            raise ValidationError(f"{source}: schema {schema_name} missing required field(s): {', '.join(missing)}")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return
    for field, rules in properties.items():
        if field not in data or not isinstance(rules, dict):
            continue
        value = data[field]
        if "type" in rules and not _type_matches(value, rules["type"]):
            raise ValidationError(f"{source}: schema {schema_name} field {field} has invalid type")
        if "enum" in rules and value not in rules["enum"]:
            raise ValidationError(f"{source}: schema {schema_name} field {field} has invalid value {value!r}")
        if "const" in rules and value != rules["const"]:
            raise ValidationError(f"{source}: schema {schema_name} field {field} must equal {rules['const']!r}")
        if "pattern" in rules and isinstance(value, str) and not re.search(str(rules["pattern"]), value):
            raise ValidationError(f"{source}: schema {schema_name} field {field} does not match required pattern")
