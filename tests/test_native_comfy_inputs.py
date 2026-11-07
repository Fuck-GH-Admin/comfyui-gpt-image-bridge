"""Native ComfyUI Batch Images compatibility without a bridge-only collector."""
import sys
import pytest

from conftest import image_tensor
from test_registration_and_guard import import_comfy_package


def harness(monkeypatch):
    package = import_comfy_package()
    module = sys.modules[f"{package.__name__}.nodes"]
    captured = []

    def fake_run(**kwargs):
        captured.append(kwargs)
        return ("image", "revised", "report")

    monkeypatch.setattr(module, "_run_and_convert", fake_run)
    provider = module.ProviderConfig(
        auth_mode="api_key",
        base_url="https://relay.example/v1",
        model="image-example",
        api_protocol="images",
        api_key="test-key-not-for-sharing",
    )
    common = dict(
        provider=provider,
        prompt="Compose a new scene",
        size="auto",
        quality="auto",
        background="auto",
        output_format="png",
        moderation="auto",
        n=1,
        timeout_sec=300,
    )
    return package, captured, common


def test_generate_native_image_batch_uploads_each_frame_in_order(monkeypatch):
    package, calls, common = harness(monkeypatch)
    first = image_tensor(13, 11, 0.15)
    second = image_tensor(13, 11, 0.55)
    batch = __import__("torch").cat((first, second), dim=0)
    result = package.NODE_CLASS_MAPPINGS["GPTImageBridgeGenerate"]().generate(
        **common, reference_batch=batch,
    )
    assert result == ("image", "revised", "report")
    refs = calls[0]["references"]
    assert [(r.source_slot, r.batch_index, r.width, r.height) for r in refs] == [
        (1, 0, 13, 11), (1, 1, 13, 11),
    ]
    assert refs[0].png_bytes != refs[1].png_bytes
    assert calls[0]["operation"] == "generate"


def test_edit_native_batch_starts_with_image_two_and_preserves_base(monkeypatch):
    package, calls, common = harness(monkeypatch)
    base = image_tensor(19, 13, 0.25)
    reference_batch = image_tensor(15, 9, 0.45).repeat(3, 1, 1, 1)
    result = package.NODE_CLASS_MAPPINGS["GPTImageBridgeEdit"]().edit(
        **common, **{"base_image（Image 1）": base},
        reference_batch=reference_batch,
    )
    assert result == ("image", "revised", "report")
    request = calls[0]
    assert request["operation"] == "edit"
    assert (request["base_image"].source_slot, request["base_image"].width) == (1, 19)
    assert [(r.source_slot, r.batch_index) for r in request["references"]] == [
        (2, 0), (2, 1), (2, 2),
    ]


def test_generate_rejects_native_batch_plus_numbered_inputs_before_request(monkeypatch):
    package, calls, common = harness(monkeypatch)
    generate = package.NODE_CLASS_MAPPINGS["GPTImageBridgeGenerate"]().generate
    with pytest.raises(ValueError, match="either reference_batch"):
        generate(**common, reference_batch=image_tensor(8, 8), reference_1=image_tensor(8, 8))
    assert not calls


def test_edit_rejects_native_batch_plus_legacy_list_before_request(monkeypatch):
    package, calls, common = harness(monkeypatch)
    legacy = package.NODE_CLASS_MAPPINGS["GPTImageBridgeReferenceList"]().collect(
        image_2=image_tensor(11, 7)
    )[0]
    with pytest.raises(ValueError, match="either reference_batch"):
        package.NODE_CLASS_MAPPINGS["GPTImageBridgeEdit"]().edit(
            **common,
            **{"base_image（Image 1）": image_tensor(11, 7)},
            reference_batch=image_tensor(11, 7),
            references=legacy,
        )
    assert not calls


def test_generate_native_batch_limit_is_sixteen_before_request(monkeypatch):
    package, calls, common = harness(monkeypatch)
    generate = package.NODE_CLASS_MAPPINGS["GPTImageBridgeGenerate"]().generate
    good = image_tensor(8, 8).repeat(16, 1, 1, 1)
    assert generate(**common, reference_batch=good)[0] == "image"
    assert len(calls[-1]["references"]) == 16
    with pytest.raises(ValueError, match="At most 16"):
        generate(**common, reference_batch=image_tensor(8, 8).repeat(17, 1, 1, 1))
    assert len(calls) == 1


def test_edit_native_batch_limit_is_fifteen_before_request(monkeypatch):
    package, calls, common = harness(monkeypatch)
    edit = package.NODE_CLASS_MAPPINGS["GPTImageBridgeEdit"]().edit
    base = {"base_image（Image 1）": image_tensor(8, 8)}
    assert edit(**common, **base, reference_batch=image_tensor(8, 8).repeat(15, 1, 1, 1))[0] == "image"
    assert len(calls[-1]["references"]) == 15
    with pytest.raises(ValueError, match="at most 15"):
        edit(**common, **base, reference_batch=image_tensor(8, 8).repeat(16, 1, 1, 1))
    assert len(calls) == 1


def test_empty_batch_fails_before_network(monkeypatch):
    package, calls, common = harness(monkeypatch)
    batch = image_tensor(8, 8)[:0]
    with pytest.raises(ValueError, match="at least one"):
        package.NODE_CLASS_MAPPINGS["GPTImageBridgeGenerate"]().generate(
            **common, reference_batch=batch
        )
    assert not calls
