"""Unit tests for key-free, local image service configuration."""
from __future__ import annotations

import json
import os

import pytest

from gpt_image_bridge import provider_profiles as profiles


def write_profile_file(monkeypatch, tmp_path, data, *, mode=0o600):
    path = tmp_path / "provider-settings.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    os.chmod(path, mode)
    monkeypatch.setenv(profiles.ENV_PATH, str(path))
    return path


def sample(key="private-client-key-should-never-be-shared"):
    return {"profiles": {
        "local_codex": {
            "api_key": key, "base_url": "http://127.0.0.1:8317/v1",
            "model": "gpt-image-2.6-flare", "api_protocol": "auto",
            "reference_mode": "images_edit", "use_async": False,
        },
        "third_party": {
            "api_key": "private-other-gateway-key",
            "base_url": "https://relay.example/v1",
            "model": "vendor-image-model", "api_protocol": "images",
            "reference_mode": "images_edit",
        },
    }}


def test_profile_node_lists_only_names_and_never_reveals_credentials(monkeypatch, tmp_path):
    private = "private-client-key-should-never-be-shared"
    write_profile_file(monkeypatch, tmp_path, sample(private))
    assert profiles.profile_names() == ["local_codex", "third_party"]
    public = str(profiles.profile_names())
    assert private not in public
    provider = profiles.build_profile_provider("local_codex")
    assert provider.api_key == private
    assert provider.base_url == "http://127.0.0.1:8317/v1"
    assert provider.model == "gpt-image-2.6-flare"
    assert provider.reference_generate_mode == "images_edit"
    assert private not in repr(provider)
    assert private not in json.dumps(provider.public_dict())


def test_third_party_uses_its_own_host_model_key_and_image_protocol(monkeypatch, tmp_path):
    write_profile_file(monkeypatch, tmp_path, sample())
    provider = profiles.build_profile_provider("third_party", image_model="custom-image-id")
    assert provider.base_url == "https://relay.example/v1"
    assert provider.api_key == "private-other-gateway-key"
    assert provider.model == "custom-image-id"
    assert provider.api_protocol == "images"
    assert provider.use_async is False


def test_profile_file_rotation_is_used_on_next_execution(monkeypatch, tmp_path):
    path = write_profile_file(monkeypatch, tmp_path, sample("key-before-rotation"))
    old = profiles.profile_fingerprint()
    assert profiles.build_profile_provider("local_codex").api_key == "key-before-rotation"
    path.write_text(json.dumps(sample("a-new-rotated-key-longer")), encoding="utf-8")
    os.chmod(path, 0o600)
    assert profiles.profile_fingerprint() != old
    assert profiles.build_profile_provider("local_codex").api_key == "a-new-rotated-key-longer"


def test_missing_configuration_has_non_secret_placeholder(monkeypatch, tmp_path):
    monkeypatch.setenv(profiles.ENV_PATH, str(tmp_path / "missing.json"))
    assert profiles.profile_names() == [profiles.NO_PROFILE]
    with pytest.raises(ValueError, match="Select a configured"):
        profiles.build_profile_provider(profiles.NO_PROFILE)


def test_unknown_profile_name_is_rejected_even_when_file_exists(monkeypatch, tmp_path):
    write_profile_file(monkeypatch, tmp_path, sample())
    with pytest.raises(ValueError, match="not present"):
        profiles.build_profile_provider("something_else")


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions only")
def test_world_readable_secret_config_is_rejected(monkeypatch, tmp_path):
    write_profile_file(monkeypatch, tmp_path, sample(), mode=0o644)
    assert profiles.profile_names() == [profiles.NO_PROFILE]
    with pytest.raises(ValueError, match="chmod 600"):
        profiles.build_profile_provider("local_codex")


@pytest.mark.parametrize("value", [
    "not-json", "[]", '{"profiles": []}', '{"profiles": {"bad/name": {}}}',
    '{"profiles": {"x": {"unsupported": true}}}',
])
def test_invalid_profile_documents_fail_closed_without_echo(monkeypatch, tmp_path, value):
    path = tmp_path / "bad-profile.json"
    path.write_text(value, encoding="utf-8")
    os.chmod(path, 0o600)
    monkeypatch.setenv(profiles.ENV_PATH, str(path))
    assert profiles.profile_names() == [profiles.NO_PROFILE]
    with pytest.raises(ValueError):
        profiles.build_profile_provider("x")


def test_missing_key_is_rejected_without_echo(monkeypatch, tmp_path):
    doc = sample()
    doc["profiles"]["local_codex"]["api_key"] = ""
    write_profile_file(monkeypatch, tmp_path, doc)
    with pytest.raises(ValueError, match="api_key must be non-empty"):
        profiles.build_profile_provider("local_codex")


def test_responses_override_requires_compatible_transport(monkeypatch, tmp_path):
    write_profile_file(monkeypatch, tmp_path, sample())
    with pytest.raises(ValueError, match="Responses reference mode"):
        profiles.build_profile_provider("third_party", reference_mode="responses")
    provider = profiles.build_profile_provider("local_codex", reference_mode="responses", responses_model="available-host-model")
    assert provider.reference_generate_mode == "responses"
    assert provider.responses_model == "available-host-model"


def test_profile_does_not_allow_configuration_path_from_workflow(monkeypatch, tmp_path):
    write_profile_file(monkeypatch, tmp_path, sample())
    with pytest.raises(ValueError, match="Select a configured"):
        profiles.build_profile_provider("../some-other-file")
