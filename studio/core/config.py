"""Load config.yaml (+ preview overrides) and .env secrets."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

from .errors import MissingKeyError, StudioError

ROOT = Path(__file__).resolve().parents[2]

KEY_SOURCES = {
    "GEMINI_API_KEY": "https://aistudio.google.com/apikey",
    "YOUTUBE_API_KEY": "Google Cloud Console → APIs & Services → Credentials",
}


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


class Config(dict):
    """A dict with dotted-path lookup: cfg.get_path("video.fps")."""

    def get_path(self, dotted: str, default: Any = None) -> Any:
        node: Any = self
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def require(self, dotted: str) -> Any:
        value = self.get_path(dotted)
        if value is None:
            raise StudioError(
                f"Setting '{dotted}' is missing from config.yaml.",
                fix="Restore it from the copy on GitHub or add it back.",
            )
        return value

    def root_path(self, dotted: str) -> Path:
        """A path setting resolved relative to the project root."""
        p = Path(self.require(dotted))
        return p if p.is_absolute() else ROOT / p


def load_config(path: str | Path | None = None, mode: str = "final") -> Config:
    cfg_path = Path(path) if path else ROOT / "config.yaml"
    if not cfg_path.exists():
        raise StudioError(
            f"Config file not found: {cfg_path}",
            fix="Run the command from the project folder, or pass --config path\\to\\config.yaml",
        )
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise StudioError(
            f"config.yaml has a formatting mistake: {exc}",
            fix="YAML is sensitive to indentation — use spaces, not tabs.",
        ) from exc
    if mode == "preview":
        data = deep_merge(data, data.get("preview_overrides", {}))
    data["mode"] = mode
    return Config(data)


def load_env() -> None:
    """Load .env from the project root (never overrides real env vars)."""
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:  # pragma: no cover - dependency missing
        return
    load_dotenv(ROOT / ".env", override=False)


def get_secret(name: str, required: bool = True) -> str | None:
    value = (os.environ.get(name) or "").strip()
    if not value and required:
        raise MissingKeyError(name, KEY_SOURCES.get(name, "the service's website"))
    return value or None
