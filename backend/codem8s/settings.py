from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

CONFIG_DIR = Path.home() / ".codem8s"
CONFIG_FILE = CONFIG_DIR / "settings.json"


class SettingsIn(BaseModel):
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")


class SettingsOut(BaseModel):
    has_api_key: bool
    masked_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    config_path: str = str(CONFIG_FILE)


def _machine_secret() -> bytes:
    raw = f"{os.getenv('USER','user')}::{Path.home()}::codem8s-local-settings".encode("utf-8")
    return base64.urlsafe_b64encode(raw)[:32]


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(byte ^ key[index % len(key)] for index, byte in enumerate(data))


def encode_secret(value: str) -> str:
    if not value:
        return ""
    mixed = _xor(value.encode("utf-8"), _machine_secret())
    return base64.urlsafe_b64encode(mixed).decode("ascii")


def decode_secret(value: str) -> str:
    if not value:
        return ""
    try:
        mixed = base64.urlsafe_b64decode(value.encode("ascii"))
        return _xor(mixed, _machine_secret()).decode("utf-8")
    except Exception:
        return ""


def mask_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return "*" * len(value)
    return value[:7] + "..." + value[-4:]


def load_raw() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_settings() -> SettingsIn:
    raw = load_raw()
    key = os.getenv("OPENAI_API_KEY") or decode_secret(raw.get("openai_api_key_encoded", ""))
    model = os.getenv("OPENAI_MODEL") or raw.get("openai_model") or "gpt-4o-mini"
    return SettingsIn(openai_api_key=key, openai_model=model)


def save_settings(settings: SettingsIn) -> SettingsOut:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = load_settings()
    api_key = settings.openai_api_key.strip() or existing.openai_api_key
    model = settings.openai_model.strip() or existing.openai_model or "gpt-4o-mini"
    payload = {
        "openai_api_key_encoded": encode_secret(api_key),
        "openai_model": model,
        "note": "Local Codem8s settings. The API key is lightly obfuscated, not bank-grade encrypted.",
    }
    CONFIG_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        CONFIG_FILE.chmod(0o600)
    except Exception:
        pass
    return settings_status()


def settings_status() -> SettingsOut:
    settings = load_settings()
    return SettingsOut(
        has_api_key=bool(settings.openai_api_key.strip()),
        masked_api_key=mask_key(settings.openai_api_key.strip()),
        openai_model=settings.openai_model,
        config_path=str(CONFIG_FILE),
    )


def get_openai_key() -> Optional[str]:
    key = load_settings().openai_api_key.strip()
    return key or None


def get_openai_model() -> str:
    return load_settings().openai_model or "gpt-4o-mini"
