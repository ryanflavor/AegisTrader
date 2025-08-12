"""Persistence implementation for test-example."""

import json
from typing import Any


class InMemoryRepository:
    """In-memory repository implementation."""

    def __init__(self):
        self._storage: dict[str, Any] = {}

    async def find_by_id(self, id: str) -> Any | None:
        """Find entity by ID."""
        return self._storage.get(id)

    async def find_all(self) -> list[Any]:
        """Find all entities."""
        return list(self._storage.values())

    async def save(self, id: str, entity: Any) -> None:
        """Save entity."""
        self._storage[id] = entity

    async def delete(self, id: str) -> None:
        """Delete entity by ID."""
        if id in self._storage:
            del self._storage[id]


class FileRepository:
    """File-based repository implementation."""

    def __init__(self, file_path: str):
        self._file_path = file_path
        self._load_data()

    def _load_data(self):
        """Load data from file."""
        try:
            with open(self._file_path) as f:
                self._data = json.load(f)
        except FileNotFoundError:
            self._data = {}

    def _save_data(self):
        """Save data to file."""
        with open(self._file_path, "w") as f:
            json.dump(self._data, f, indent=2)
