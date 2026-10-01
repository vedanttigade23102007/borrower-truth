"""Read and write a book's tables without changing their layout. Uses pyarrow only.

    rows = bookio.load(book_dir, "tape")          # a list of dicts, one per row
    bookio.save(book_dir, "tape", rows)           # same columns and types as before, or an error
"""
import os

import pyarrow as pa
import pyarrow.parquet as pq


def path(book_dir: str, table: str) -> str:
    return os.path.join(book_dir, f"{table}.parquet")


def schema(book_dir: str, table: str) -> pa.Schema:
    return pq.read_schema(path(book_dir, table))


def load(book_dir: str, table: str) -> list[dict]:
    return pq.read_table(path(book_dir, table)).to_pylist()


def save(book_dir: str, table: str, rows: list[dict]) -> None:
    """Write rows back with exactly the original columns and types. A missing or extra column is an error."""
    sch = schema(book_dir, table)
    want = set(sch.names)
    for i, r in enumerate(rows):
        if set(r) != want:
            raise ValueError(f"{table} row {i}: columns {sorted(set(r) ^ want)} differ from the table's layout")
    pq.write_table(pa.Table.from_pylist(rows, schema=sch), path(book_dir, table))
