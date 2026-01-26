"""Code index for structured code metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oya.db.connection import Database
    from oya.parsing.models import ParsedFile

from oya.parsing.models import SymbolType


@dataclass
class CodeIndexEntry:
    """A single entry in the code index."""

    id: int | None
    file_path: str
    symbol_name: str
    symbol_type: str
    line_start: int
    line_end: int
    signature: str | None
    docstring: str | None
    calls: list[str]
    called_by: list[str]
    raises: list[str]
    mutates: list[str]
    error_strings: list[str]
    source_hash: str

    @classmethod
    def from_row(cls, row) -> CodeIndexEntry:
        """Create entry from database row."""
        return cls(
            id=row[0],
            file_path=row[1],
            symbol_name=row[2],
            symbol_type=row[3],
            line_start=row[4],
            line_end=row[5],
            signature=row[6],
            docstring=row[7],
            calls=json.loads(row[8]) if row[8] else [],
            called_by=json.loads(row[9]) if row[9] else [],
            raises=json.loads(row[10]) if row[10] else [],
            mutates=json.loads(row[11]) if row[11] else [],
            error_strings=json.loads(row[12]) if row[12] else [],
            source_hash=row[13],
        )


class CodeIndexBuilder:
    """Builds and maintains the code index."""

    INDEXABLE_TYPES = {SymbolType.FUNCTION, SymbolType.METHOD, SymbolType.CLASS}

    def __init__(self, db: Database):
        self.db = db

    def build(self, parsed_files: list[ParsedFile], source_hash: str) -> int:
        """Build code index from parsed files. Returns count of entries created."""
        count = 0

        for pf in parsed_files:
            # Clear existing entries for this file
            self.db.execute("DELETE FROM code_index WHERE file_path = ?", (pf.path,))

            for symbol in pf.symbols:
                if symbol.symbol_type not in self.INDEXABLE_TYPES:
                    continue

                # Extract metadata
                raises = symbol.metadata.get("raises", [])
                mutates = symbol.metadata.get("mutates", [])
                error_strings = symbol.metadata.get("error_strings", [])
                calls = symbol.metadata.get("calls", [])

                self.db.execute(
                    """
                    INSERT INTO code_index
                    (file_path, symbol_name, symbol_type, line_start, line_end,
                     signature, docstring, calls, called_by, raises, mutates,
                     error_strings, source_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        pf.path,
                        symbol.name,
                        symbol.symbol_type.value,
                        symbol.start_line,
                        symbol.end_line,
                        symbol.signature,
                        (symbol.docstring or "")[:200],
                        json.dumps(calls),
                        json.dumps([]),  # called_by computed later
                        json.dumps(raises),
                        json.dumps(mutates),
                        json.dumps(error_strings),
                        source_hash,
                    ),
                )
                count += 1

        self.db.commit()
        return count

    def compute_called_by(self) -> None:
        """Compute called_by by inverting calls relationships."""
        # Build reverse mapping
        called_by_map: dict[str, list[str]] = {}

        cursor = self.db.execute("SELECT symbol_name, calls FROM code_index")
        for row in cursor.fetchall():
            caller = row[0]
            calls = json.loads(row[1]) if row[1] else []
            for callee in calls:
                if callee not in called_by_map:
                    called_by_map[callee] = []
                called_by_map[callee].append(caller)

        # Update each row
        for symbol, callers in called_by_map.items():
            self.db.execute(
                "UPDATE code_index SET called_by = ? WHERE symbol_name = ?",
                (json.dumps(callers), symbol),
            )

        self.db.commit()

    def delete_file(self, file_path: str) -> None:
        """Remove all entries for a file."""
        self.db.execute("DELETE FROM code_index WHERE file_path = ?", (file_path,))
        self.db.commit()
