"""Read-only access to the project's SQLite source database."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"
SQLITE_HEADER = b"SQLite format 3\x00"


def validate_database(path: str | Path) -> Path:
    """Reject absent, Git LFS pointer, and non-SQLite files with actionable errors."""
    db = Path(path).expanduser().resolve()
    if not db.exists():
        raise FileNotFoundError(f"Database not found: {db}")
    with db.open("rb") as stream:
        header = stream.read(128)
    if header.startswith(LFS_HEADER):
        raise RuntimeError(
            f"{db} is a Git LFS pointer, not the database. From the repository root run `git lfs pull` "
            "or set AGRIWATER_DB to the downloaded full agriwater_v2.sqlite file."
        )
    if not header.startswith(SQLITE_HEADER):
        raise RuntimeError(f"{db} is not a valid SQLite database file.")
    return db


def resolve_database(path: str | Path | None = None, start: str | Path | None = None) -> Path:
    """Resolve AGRIWATER_DB or a standard project location and validate it."""
    configured = path or os.environ.get("AGRIWATER_DB")
    if configured:
        return validate_database(configured)
    here = Path(start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        for candidate in (folder / "AgriWater" / "database" / "agriwater_v2.sqlite",
                          folder / "database" / "agriwater_v2.sqlite"):
            if candidate.exists():
                return validate_database(candidate)
    raise FileNotFoundError(
        "No agriwater_v2.sqlite found. Set AGRIWATER_DB or pass --db; GitHub ZIPs may contain only a Git LFS pointer."
    )


def connect_readonly(path: str | Path | None = None) -> sqlite3.Connection:
    db = resolve_database(path)
    return sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)


def read_table(path: str | Path, table: str):
    """Read one table as a DataFrame, without mutating the source database."""
    import pandas as pd

    with connect_readonly(path) as connection:
        return pd.read_sql_query(f'SELECT * FROM "{table}"', connection)
