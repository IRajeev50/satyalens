"""Dependency-free validator for the eval seed set against evals/schema.json.

Implements exactly the JSON Schema subset the schema uses (type, required,
properties, items, enum, const, pattern, minLength, minItems,
additionalProperties: false) so validation runs with the standard library
only - no new dependency, nothing simulated.
"""
import json
import re
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent


class ValidationError(ValueError):
    pass


def _fail(path: str, message: str) -> None:
    raise ValidationError(f"{path or '<root>'}: {message}")


def _check(schema: dict, value, path: str) -> None:
    if "const" in schema and value != schema["const"]:
        _fail(path, f"expected const {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        _fail(path, f"{value!r} not in enum {schema['enum']}")
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            _fail(path, "expected object")
        for key in schema.get("required", []):
            if key not in value:
                _fail(path, f"missing required key {key!r}")
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(schema.get("properties", {}))
            if extra:
                _fail(path, f"unexpected keys {sorted(extra)}")
        for key, subschema in schema.get("properties", {}).items():
            if key in value:
                _check(subschema, value[key], f"{path}.{key}")
    elif expected_type == "array":
        if not isinstance(value, list):
            _fail(path, "expected array")
        if "minItems" in schema and len(value) < schema["minItems"]:
            _fail(path, f"expected at least {schema['minItems']} item(s)")
        for index, item in enumerate(value):
            _check(schema.get("items", {}), item, f"{path}[{index}]")
    elif expected_type == "string":
        if not isinstance(value, str):
            _fail(path, "expected string")
        if "minLength" in schema and len(value) < schema["minLength"]:
            _fail(path, f"shorter than minLength {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            _fail(path, f"does not match pattern {schema['pattern']!r}")
    elif expected_type == "boolean":
        if not isinstance(value, bool):
            _fail(path, "expected boolean")
    elif expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            _fail(path, "expected integer")


def load_schema(path: Path | None = None) -> dict:
    return json.loads((path or EVALS_DIR / "schema.json").read_text(encoding="utf-8"))


def load_seed(path: Path | None = None) -> list[dict]:
    return json.loads((path or EVALS_DIR / "gold_seed.json").read_text(encoding="utf-8"))


def validate_example(example: dict, schema: dict | None = None) -> None:
    _check(schema or load_schema(), example, example.get("id", ""))


def validate_seed(seed: list[dict] | None = None, schema: dict | None = None) -> list[dict]:
    schema = schema or load_schema()
    seed = load_seed() if seed is None else seed
    ids = set()
    for example in seed:
        validate_example(example, schema)
        if example["id"] in ids:
            _fail(example["id"], "duplicate id")
        ids.add(example["id"])
    return seed
