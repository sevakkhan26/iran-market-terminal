"""Thread-safe runtime settings store, persisted in Postgres (app_settings)."""
from __future__ import annotations

import logging
import threading
from dataclasses import asdict, fields
from typing import Any, Dict

from . import db
from .models import AppSettings

log = logging.getLogger("terminal.settings")


class SettingsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._settings = AppSettings()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        try:
            data = db.get_app_settings()
            if data:
                self._apply(data)
                log.info("Loaded %d settings from Postgres", len(data))
        except Exception as exc:
            log.warning("Could not load settings from DB yet (%s) — using defaults",
                        exc)
        self._loaded = True

    def _persist(self) -> None:
        try:
            payload = {f.name: float(getattr(self._settings, f.name))
                       for f in fields(AppSettings)}
            db.set_app_settings(payload)
        except Exception as exc:
            log.warning("Could not persist settings to DB: %s", exc)

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
            self._ensure_loaded()
            return AppSettings(**{f.name: getattr(self._settings, f.name)
                                  for f in fields(AppSettings)})

    def update(self, data: Dict[str, Any]) -> AppSettings:
        with self._lock:
            self._ensure_loaded()
            self._apply(data)
            self._persist()
            return self.get_unlocked()

    def get_unlocked(self) -> AppSettings:
        return AppSettings(**{f.name: getattr(self._settings, f.name)
                              for f in fields(AppSettings)})


settings_store = SettingsStore()
