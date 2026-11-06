"""Schema data structures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Field:
    name: str
    type: str
    options: tuple[tuple[str, Any], ...] = ()

    def option(self, name: str) -> Any:
        return dict(self.options)[name]


@dataclass(frozen=True, slots=True)
class Schema:
    source_path: Path
    fields: tuple[Field, ...]
    schema_version: int = 1
