from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "save"
DATA_FILE = DATA_DIR / "game_state.json"

DEFAULT_DATA: Dict[str, Any] = {
    "config": {
        "display_mode": "window",
        "music_muted": False,
    },
    "stats": {
        "current": None,
        "last": None,
        "best": None,
    },
}


def _load_raw() -> Dict[str, Any]:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return deepcopy(DEFAULT_DATA)


def _save_raw(data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def update_config(display_mode: str) -> None:
    data = _load_raw()
    data.setdefault("config", {})
    data["config"]["display_mode"] = display_mode
    _save_raw(data)


def set_music_muted(muted: bool) -> None:
    data = _load_raw()
    data.setdefault("config", {})
    data["config"]["music_muted"] = bool(muted)
    _save_raw(data)


def get_music_muted() -> bool:
    data = _load_raw()
    return bool(data.get("config", {}).get("music_muted", False))


def set_current_run(info: Dict[str, Any]) -> None:
    data = _load_raw()
    data.setdefault("stats", {})
    data["stats"]["current"] = info
    _save_raw(data)


def update_current_run(info: Dict[str, Any]) -> None:
    data = _load_raw()
    data.setdefault("stats", {})
    current = data["stats"].get("current") or {}
    current.update(info)
    data["stats"]["current"] = current
    _save_raw(data)


def complete_run(summary: Dict[str, Any]) -> None:
    data = _load_raw()
    stats = data.setdefault("stats", {})
    stats["last"] = summary
    best = stats.get("best")
    if not best or _is_better(summary, best):
        stats["best"] = summary
    stats["current"] = None
    _save_raw(data)


def _is_better(new: Dict[str, Any], old: Dict[str, Any]) -> bool:
    new_deliveries = int(new.get("deliveries", 0))
    old_deliveries = int(old.get("deliveries", 0))
    if new_deliveries != old_deliveries:
        return new_deliveries > old_deliveries
    new_items = int(new.get("items", 0))
    old_items = int(old.get("items", 0))
    return new_items > old_items


def get_stats() -> Dict[str, Any]:
    data = _load_raw()
    stats = data.get("stats", {})
    return {
        "current": stats.get("current"),
        "last": stats.get("last"),
        "best": stats.get("best"),
    }
