"""Seeded, incremental fixture record generation."""

from __future__ import annotations

import random
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

from .models import Field, Schema


def _value(field: Field, row_index: int, rng: random.Random) -> Any:
    if field.type == "sequence": return field.option("start") + row_index * field.option("step")
    if field.type == "integer": return rng.randint(field.option("min"), field.option("max"))
    if field.type == "choice": return rng.choice(field.option("values"))
    if field.type == "boolean": return bool(rng.getrandbits(1))
    if field.type == "date":
        start = field.option("start"); days = (field.option("end") - start).days
        return (start + timedelta(days=rng.randint(0, days))).isoformat()
    raise ValueError(f"unsupported field type: {field.type}")


def generate_records(schema: Schema, rows: int, seed: int) -> Iterator[dict[str, Any]]:
    if not isinstance(rows, int) or isinstance(rows, bool) or rows < 0: raise ValueError("rows must be a nonnegative integer")
    if not isinstance(seed, int) or isinstance(seed, bool): raise ValueError("seed must be an integer")
    rng = random.Random(seed)
    for index in range(rows):
        yield {field.name: _value(field, index, rng) for field in schema.fields}
