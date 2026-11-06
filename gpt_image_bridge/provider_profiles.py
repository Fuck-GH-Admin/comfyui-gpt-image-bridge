"""Server-side OpenAI-compatible provider profiles.

Names are available to ComfyUI nodes; credentials remain in a private local
JSON file, never in a shareable workflow or /object_info response.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .config import ProviderConfig

ENV_PATH = "GPT_IMAGE_BRIDGE_PROVIDERS_FILE"
NO_PROFILE = "(configure providers.local.json)"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
MAX_FILE_BYTES = 256 * 1024
MAX_PROFILES = 48
_ALLOWED = frozenset({
    "api_key", "base_url", "model", "api_protocol", "reference_mode",
    "responses_model", "image_complexity", "use_async", "use_custom_endpoints",
    "generate_endpoint", "edit_endpoint", "async_generate_endpoint",
    "async_edit_endpoint", "async_poll_endpoint_template", "async_mapping_json",
})


def profile_file() -> Path:
    custom = os.environ.get(ENV_PATH, "").strip()
    return (Path(custom).expanduser() if custom else
            Path(__file__).resolve().parents[1] / "providers.local.json")


def _read_profiles() -> dict[str, dict[str, Any]]:
    path = profile_file()
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {}
    if not path.is_file() or stat.st_size > MAX_FILE_BYTES:
        raise ValueError("Provider profile file is not a regular JSON file or exceeds 256 KiB.")
    if os.name == "posix" and stat.st_mode & 0o077:
        raise ValueError("Provider profile file is readable by other users; use chmod 600.")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("Provider profile file must contain valid UTF-8 JSON.") from None
    if not isinstance(document, dict) or set(document) != {"profiles"}:
        raise ValueError("Provider profile file must contain exactly a 'profiles' object.")
    profiles = document["profiles"]
    if not isinstance(profiles, dict) or len(profiles) > MAX_PROFILES:
        raise ValueError("Provider 'profiles' must be an object with at most 48 entries.")
    for name, record in profiles.items():
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError("Provider profile names must contain 1–64 letters, digits, dots, dashes or underscores.")
        if not isinstance(record, dict) or set(record) - _ALLOWED:
            raise ValueError("Provider profile has invalid or unsupported configuration fields.")
    return profiles


def profile_names() -> list[str]:
    try:
        names = sorted(_read_profiles())
    except ValueError:
        return [NO_PROFILE]
    return names or [NO_PROFILE]


def profile_fingerprint() -> str:
    """Invalidate ComfyUI's cached Provider after local config/key changes."""
    try:
        stat = profile_file().stat()
    except FileNotFoundError:
        return "not-configured"
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def _boolean(record: dict[str, Any], field: str, default: bool) -> bool:
    value = record.get(field, default)
    if not isinstance(value, bool):
        raise ValueError(f"Provider profile field {field} must be a Boolean.")
    return value


def build_profile_provider(
    name: str,
    *,
    image_model: str = "",
    reference_mode: str = "profile",
    responses_model: str = "",
) -> ProviderConfig:
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError("Select a configured GPT Image Bridge provider profile.")
    profiles = _read_profiles()
    if name not in profiles:
        raise ValueError(
            "Provider profile is not present on this ComfyUI server. "
            "Add it to providers.local.json (or GPT_IMAGE_BRIDGE_PROVIDERS_FILE) and refresh node definitions."
        )
    settings = profiles[name]
    for key in ("api_key", "base_url", "model"):
        value = settings.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Provider profile field {key} must be non-empty text.")
    for key, value in settings.items():
        if key not in {"use_async", "use_custom_endpoints"} and not isinstance(value, str):
            raise ValueError("Provider profile text fields must be strings.")

    protocol = settings.get("api_protocol", "auto")
    mode = settings.get("reference_mode", "images_edit") if reference_mode == "profile" else reference_mode
    if mode == "responses" and protocol not in {"auto", "responses"}:
        raise ValueError("Responses reference mode requires auto or responses protocol.")
    if mode == "images_edit" and protocol not in {"auto", "images"}:
        raise ValueError("Images Edit reference mode requires auto or images protocol.")
    model = str(image_model or "").strip() or settings["model"].strip()
    host_model = str(responses_model or "").strip() or settings.get("responses_model", "")
    # This path is executed on the trusted backend. Never use a workflow
    # input to supply the raw key or a configuration filename.
    return ProviderConfig.from_api_inputs(
        api_key=settings["api_key"],
        base_url=settings["base_url"],
        model=model,
        api_protocol=protocol,
        reference_generate_mode=mode,
        responses_model=host_model,
        image_complexity=settings.get("image_complexity", "auto"),
        use_async=_boolean(settings, "use_async", False),
        use_custom_endpoints=_boolean(settings, "use_custom_endpoints", False),
        generate_endpoint=settings.get("generate_endpoint", ""),
        edit_endpoint=settings.get("edit_endpoint", ""),
        async_generate_endpoint=settings.get("async_generate_endpoint", ""),
        async_edit_endpoint=settings.get("async_edit_endpoint", ""),
        async_poll_endpoint_template=settings.get("async_poll_endpoint_template", ""),
        async_mapping_json=settings.get("async_mapping_json", ""),
    )
