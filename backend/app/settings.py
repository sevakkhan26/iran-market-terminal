"""Thread-safe runtime settings store, persisted to data/settings.json."""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any, Dict

from .db import DATA_DIR
from .models import AppSettings

log = logging.getLogger("terminal.settings")

SETTINGS_PATH = DATA_DIR / "settings.json"


class SettingsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._settings = AppSettings()
        self._load()

    def _load(self) -> None:
        try:
            if SETTINGS_PATH.exists():
                data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                self._apply(data)
        except Exception as exc:
            log.warning("Could not load persisted settings: %s", exc)

    def _persist(self) -> None:
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_PATH.write_text(json.dumps(asdict(self._settings), indent=2),
                                     encoding="utf-8")
        except Exception as exc:
            log.warning("Could not persist settings: %s", exc)

    def _apply(self, data: Dict[str, Any]) -> None:
        valid = {f.name for f in fields(AppSettings)}
        for key, value in data.items():
            if key not in valid or value is None:
                continue
            lo, hi = AppSettings.BOUNDS.get(key, (None, None))
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if lo is not None:
                value = max(lo, min(hi, value))
            setattr(self._settings, key, value)

    def get(self) -> AppSettings:
        with self._lock:
            return AppSettings(**{f.name: getattr(self._settings, f.name)
                                  for f in fields(AppSettings)})

    def update(self, data: Dict[str, Any]) -> AppSettings:
        with self._lock:
            self._apply(data)
            self._persist()
            return self.get_unlocked()

    def get_unlocked(self) -> AppSettings:
        return AppSettings(**{f.name: getattr(self._settings, f.name)
                              for f in fields(AppSettings)})


settings_store = SettingsStore()
