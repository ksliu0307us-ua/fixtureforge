"""Strict loading and validation for FixtureForge schemas."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from .models import Field, Schema

FIELD_NAME_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*"
_NAME_RE = re.compile(rf"\A{FIELD_NAME_PATTERN}\Z")
_TOP_FIELDS = frozenset({"schema_version", "fields"})
_OPTIONS = {
    "sequence": frozenset({"name", "type", "start", "step"}),
    "integer": frozenset({"name", "type", "min", "max"}),
    "choice": frozenset({"name", "type", "values"}),
    "boolean": frozenset({"name", "type"}),
    "date": frozenset({"name", "type", "start", "end"}),
}


class SchemaError(Exception):
    def __init__(self, messages: str | list[str]):
        self.messages = (messages,) if isinstance(messages, str) else tuple(messages)
        super().__init__("; ".join(self.messages))


class _DuplicateKeyError(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _date(value: Any, context: str, problems: list[str]) -> date | None:
    if not isinstance(value, str):
        problems.append(f"{context}: must be an ISO date string (YYYY-MM-DD)")
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        problems.append(f"{context}: invalid calendar date {value!r}")
        return None
    if parsed.isoformat() != value:
        problems.append(f"{context}: date must use canonical YYYY-MM-DD form")
        return None
    return parsed


def schema_from_data(data: Any, source_path: Path = Path("<memory>")) -> Schema:
    if not isinstance(data, dict):
        raise SchemaError("schema root must be an object")
    problems: list[str] = []
    missing = sorted(_TOP_FIELDS - set(data)); unknown = sorted(set(data) - _TOP_FIELDS)
    if missing: problems.append(f"schema: missing field(s): {', '.join(missing)}")
    if unknown: problems.append(f"schema: unknown field(s): {', '.join(unknown)}")
    version = data.get("schema_version")
    if not _integer(version) or version != 1:
        problems.append("schema: unsupported schema_version; expected integer 1")
    raw_fields = data.get("fields")
    if not isinstance(raw_fields, list):
        problems.append("schema: 'fields' must be a nonempty array")
        raw_fields = []
    elif not raw_fields:
        problems.append("schema: 'fields' must not be empty")

    fields: list[Field] = []
    names: set[str] = set()
    for index, raw in enumerate(raw_fields):
        context = f"fields[{index}]"
        if not isinstance(raw, dict):
            problems.append(f"{context}: must be an object")
            continue
        name = raw.get("name"); kind = raw.get("type")
        if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
            problems.append(f"{context}.name: must match {FIELD_NAME_PATTERN}")
        elif name in names:
            problems.append(f"{context}.name: duplicate field name {name!r}")
        else:
            names.add(name)
        if not isinstance(kind, str) or kind not in _OPTIONS:
            problems.append(f"{context}.type: unsupported field type {kind!r}")
            continue
        expected = _OPTIONS[kind]
        missing_options = sorted(expected - set(raw)); unknown_options = sorted(set(raw) - expected)
        if missing_options: problems.append(f"{context}: missing option(s): {', '.join(missing_options)}")
        if unknown_options: problems.append(f"{context}: unknown option(s): {', '.join(unknown_options)}")
        options: dict[str, Any] = {}
        if kind == "sequence":
            start, step = raw.get("start"), raw.get("step")
            if not _integer(start): problems.append(f"{context}.start: must be an integer (not boolean)")
            else: options["start"] = start
            if not _integer(step) or step <= 0: problems.append(f"{context}.step: must be a positive integer (not boolean)")
            else: options["step"] = step
        elif kind == "integer":
            low, high = raw.get("min"), raw.get("max")
            if not _integer(low): problems.append(f"{context}.min: must be an integer (not boolean)")
            else: options["min"] = low
            if not _integer(high): problems.append(f"{context}.max: must be an integer (not boolean)")
            else: options["max"] = high
            if _integer(low) and _integer(high) and low > high: problems.append(f"{context}: min must not exceed max")
        elif kind == "choice":
            values = raw.get("values")
            if not isinstance(values, list) or not values or not all(isinstance(item, str) for item in values):
                problems.append(f"{context}.values: must be a nonempty array of strings")
            else: options["values"] = tuple(values)
        elif kind == "date":
            start = _date(raw.get("start"), f"{context}.start", problems)
            end = _date(raw.get("end"), f"{context}.end", problems)
            if start is not None: options["start"] = start
            if end is not None: options["end"] = end
            if start is not None and end is not None and start > end: problems.append(f"{context}: start date must not exceed end date")
        if isinstance(name, str) and _NAME_RE.fullmatch(name) and not missing_options and not unknown_options:
            fields.append(Field(name, kind, tuple(options.items())))
    if problems:
        raise SchemaError(problems)
    return Schema(source_path, tuple(fields))


def load_schema(path: Path) -> Schema:
    try: text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc: raise SchemaError(f"cannot read schema {path}: {exc}") from exc
    try: data = json.loads(text, object_pairs_hook=_strict_object)
    except _DuplicateKeyError as exc: raise SchemaError(f"invalid schema {path}: {exc}") from exc
    except json.JSONDecodeError as exc: raise SchemaError(f"malformed JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    return schema_from_data(data, path)
