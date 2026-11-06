"""Incremental deterministic JSON and CSV output."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TextIO

from .models import Schema


def write_json(records: Iterable[dict[str, Any]], handle: TextIO) -> None:
    handle.write("[")
    first = True
    for record in records:
        handle.write("\n  " if first else ",\n  ")
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ": ")))
        first = False
    handle.write("\n]\n" if not first else "]\n")


def write_csv(records: Iterable[dict[str, Any]], schema: Schema, handle: TextIO) -> None:
    names = [field.name for field in schema.fields]
    writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow({key: (str(value).lower() if isinstance(value, bool) else value) for key, value in record.items()})


def write_records(records: Iterable[dict[str, Any]], schema: Schema, output_format: str, handle: TextIO) -> None:
    if output_format == "json": write_json(records, handle)
    elif output_format == "csv": write_csv(records, schema, handle)
    else: raise ValueError(f"unsupported output format: {output_format}")


def write_new_file(path: Path, records: Iterable[dict[str, Any]], schema: Schema, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with path.open("x", encoding="utf-8", newline="") as handle:
            created = True
            write_records(records, schema, output_format, handle)
    except BaseException:
        if created:
            try: path.unlink(missing_ok=True)
            except OSError: pass
        raise
