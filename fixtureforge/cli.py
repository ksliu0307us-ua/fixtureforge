"""Command-line interface for FixtureForge."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from . import __version__
from .generators import generate_records
from .models import Field, Schema
from .schema import SchemaError, load_schema
from .writers import write_new_file, write_records


def _nonnegative(value: str) -> int:
    try: parsed = int(value)
    except ValueError as exc: raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0: raise argparse.ArgumentTypeError("must be nonnegative")
    return parsed


def _integer(value: str) -> int:
    try: return int(value)
    except ValueError as exc: raise argparse.ArgumentTypeError("must be an integer") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fixtureforge", description="Generate deterministic synthetic JSON and CSV fixtures.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("validate", "validate a schema"), ("describe", "describe a schema")):
        command = commands.add_parser(name, help=help_text); command.add_argument("schema", type=Path); command.add_argument("--format", choices=("text", "json"), default="text")
    for name, help_text in (("preview", "print generated records"), ("generate", "write generated records to a new file")):
        command = commands.add_parser(name, help=help_text); command.add_argument("schema", type=Path)
        command.add_argument("--rows", type=_nonnegative, required=True); command.add_argument("--seed", type=_integer, required=True)
        command.add_argument("--format", choices=("json", "csv"), required=True)
        if name == "generate": command.add_argument("--output", type=Path, required=True)
    return parser


def _plain(value: Any) -> Any:
    if isinstance(value, date): return value.isoformat()
    if isinstance(value, tuple): return [_plain(item) for item in value]
    return value


def _field_data(field: Field) -> dict[str, Any]:
    return {"name": field.name, "type": field.type, **{key: _plain(value) for key, value in field.options}}


def _describe(schema: Schema, output_format: str) -> str:
    if output_format == "json":
        return json.dumps({"schema_version": schema.schema_version, "field_count": len(schema.fields), "fields": [_field_data(field) for field in schema.fields]}, ensure_ascii=False, indent=2) + "\n"
    lines = [f"Schema version: {schema.schema_version}", f"Fields: {len(schema.fields)}"]
    for index, field in enumerate(schema.fields, 1):
        options = ", ".join(f"{key}={_plain(value)!r}" for key, value in field.options)
        lines.append(f"  {index}. {field.name}: {field.type}" + (f" ({options})" if options else ""))
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate":
        try: schema = load_schema(args.schema)
        except SchemaError as exc:
            if args.format == "json": print(json.dumps({"valid": False, "errors": list(exc.messages)}, ensure_ascii=False, indent=2))
            else:
                for message in exc.messages: print(f"error: {message}", file=sys.stderr)
            return 1
        if args.format == "json": print(json.dumps({"valid": True, "schema_version": schema.schema_version, "field_count": len(schema.fields)}, indent=2))
        else: print(f"OK: schema is valid ({len(schema.fields)} fields).")
        return 0
    try:
        schema = load_schema(args.schema)
        if args.command == "describe": sys.stdout.write(_describe(schema, args.format)); return 0
        records = generate_records(schema, args.rows, args.seed)
        if args.command == "preview":
            if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", newline="")
            write_records(records, schema, args.format, sys.stdout); return 0
        if args.output.exists(): raise FileExistsError(f"output file already exists: {args.output}")
        write_new_file(args.output, records, schema, args.format)
        print(f"Wrote {args.rows} rows: {args.output.resolve()}"); return 0
    except SchemaError as exc:
        for message in exc.messages: print(f"error: {message}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 2
    return 2
