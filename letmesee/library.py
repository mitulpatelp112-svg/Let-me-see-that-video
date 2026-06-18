"""The local video library: a folder of per-video data plus a JSON index.

Layout::

    library/
      index.json            # searchable index of every absorbed video
      <id>/
        meta.json           # full normalised metadata for one video
        transcript.txt      # plain-text transcript (if available)
        <id>.mp4 / .m4a     # media files (only if downloading is enabled)

The index is the source of truth for search. Each record is a plain dict so it
stays trivially serialisable and easy to inspect by hand.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

Record = dict[str, Any]

_INDEX_NAME = "index.json"
# Fields scanned by ``search``.
_SEARCHABLE_FIELDS = (
    "title",
    "description",
    "uploader",
    "channel",
    "platform",
    "transcript",
)


class Library:
    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # -- paths -------------------------------------------------------------
    @property
    def index_path(self) -> Path:
        return self.root / _INDEX_NAME

    def item_dir(self, record_id: str) -> Path:
        return self.root / _safe_id(record_id)

    # -- index io ----------------------------------------------------------
    def _load_index(self) -> dict[str, Record]:
        if not self.index_path.is_file():
            return {}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        records = data.get("records", {})
        return records if isinstance(records, dict) else {}

    def _save_index(self, records: dict[str, Record]) -> None:
        payload = {"version": 1, "records": records}
        _atomic_write_json(self.index_path, payload)

    # -- public api --------------------------------------------------------
    def add(self, record: Record) -> None:
        records = self._load_index()
        records[record["id"]] = record
        self._save_index(records)

    def get(self, record_id: str) -> Record | None:
        return self._load_index().get(record_id)

    def has(self, record_id: str) -> bool:
        return record_id in self._load_index()

    def all(self) -> list[Record]:
        records = list(self._load_index().values())
        records.sort(key=lambda r: r.get("absorbed_at", ""), reverse=True)
        return records

    def search(self, query: str) -> list[Record]:
        terms = [t for t in query.lower().split() if t]
        if not terms:
            return self.all()
        results = []
        for record in self.all():
            haystack = " ".join(
                _stringify(record.get(field)) for field in _SEARCHABLE_FIELDS
            ).lower()
            haystack += " " + " ".join(
                _stringify(t) for t in record.get("tags", []) or []
            ).lower()
            if all(term in haystack for term in terms):
                results.append(record)
        return results


def _safe_id(record_id: str) -> str:
    """Make an id safe to use as a directory name."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(record_id))


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(_stringify(v) for v in value)
    return str(value)


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
