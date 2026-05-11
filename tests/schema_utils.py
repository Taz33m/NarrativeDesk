from __future__ import annotations

from datetime import datetime
from typing import Any


def validate_schema(instance: Any, schema: dict[str, Any], root: dict[str, Any], path: str = "$") -> None:
    if "$ref" in schema:
        validate_schema(instance, resolve_ref(root, schema["$ref"]), root, path)

    if "not" in schema:
        try:
            validate_schema(instance, schema["not"], root, path)
        except AssertionError:
            pass
        else:
            raise AssertionError(f"{path} must not match forbidden schema")

    if "anyOf" in schema:
        errors = []
        for option in schema["anyOf"]:
            try:
                validate_schema(instance, option, root, path)
            except AssertionError as exc:
                errors.append(str(exc))
            else:
                break
        else:
            raise AssertionError(f"{path} did not match anyOf: {'; '.join(errors)}")

    if "type" in schema:
        allowed_types = schema["type"]
        if isinstance(allowed_types, str):
            allowed_types = [allowed_types]
        if not any(matches_type(instance, item) for item in allowed_types):
            raise AssertionError(f"{path} expected type {allowed_types}, got {type(instance).__name__}")

    if "enum" in schema and instance not in schema["enum"]:
        raise AssertionError(f"{path} expected one of {schema['enum']}, got {instance!r}")

    if "pattern" in schema and isinstance(instance, str):
        import re

        if not re.match(schema["pattern"], instance):
            raise AssertionError(f"{path} expected pattern {schema['pattern']}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                raise AssertionError(f"{path}.{key} is required")

        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in instance:
                validate_schema(instance[key], subschema, root, f"{path}.{key}")

        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            for key, value in instance.items():
                if key not in properties:
                    validate_schema(value, additional, root, f"{path}.{key}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise AssertionError(f"{path} expected at least {schema['minItems']} items")
        if "items" in schema:
            for index, item in enumerate(instance):
                validate_schema(item, schema["items"], root, f"{path}[{index}]")

    if isinstance(instance, int | float) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise AssertionError(f"{path} expected >= {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise AssertionError(f"{path} expected <= {schema['maximum']}")

    if isinstance(instance, str) and schema.get("format") == "date-time":
        try:
            parsed = datetime.fromisoformat(instance.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AssertionError(f"{path} expected date-time") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise AssertionError(f"{path} expected date-time with timezone offset")


def resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise AssertionError(f"unsupported ref: {ref}")
    target: Any = root
    for part in ref[2:].split("/"):
        target = target[part]
    return target


def matches_type(instance: Any, schema_type: str) -> bool:
    if schema_type == "object":
        return isinstance(instance, dict)
    if schema_type == "array":
        return isinstance(instance, list)
    if schema_type == "string":
        return isinstance(instance, str)
    if schema_type == "number":
        return isinstance(instance, int | float) and not isinstance(instance, bool)
    if schema_type == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if schema_type == "boolean":
        return isinstance(instance, bool)
    if schema_type == "null":
        return instance is None
    raise AssertionError(f"unsupported schema type: {schema_type}")
