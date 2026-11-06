"""GPT Image 2.6 compatibility and explicit reference-image transport modes.

Mock HTTP requests confirm what ComfyUI sends; these tests do not claim that
a particular subscription account grants access to the model.
"""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from gpt_image_bridge.config import ProviderConfig
from gpt_image_bridge.images import encode_reference_slots, tensor_to_png
from gpt_image_bridge.protocols import execute_operation, select_protocol
from gpt_image_bridge.transport import HttpClient

from conftest import FakeResponse, QueueOpener, image_tensor


def _images_first(provider, *, model="gpt-image-2.6-flare", complexity="auto"):
    return replace(
        provider,
        model=model,
        responses_model="",
        reference_generate_mode="images_edit",
        image_complexity=complexity,
    )


def test_images_first_selection_is_explicit_and_backward_compatible(
    cliproxy_provider, api_provider
):
    images = _images_first(cliproxy_provider)
    assert select_protocol(images, operation="generate", has_references=False)[0] == "images"
    protocol, reason = select_protocol(
        images, operation="generate", has_references=True
    )
    assert protocol == "images"
    assert "/images/edits" in reason
    assert select_protocol(images, operation="edit", has_references=True)[0] == "images"
    assert select_protocol(
        cliproxy_provider, operation="generate", has_references=True
    )[0] == "responses"
    # Existing generic API Providers retain their original semantic route.
    assert select_protocol(
        api_provider, operation="generate", has_references=True
    )[0] == "responses"


def test_reference_guided_generation_uses_images_edit_with_single_reference(
    cliproxy_provider, image_json
):
    provider = _images_first(cliproxy_provider)
    reference = encode_reference_slots(image_tensor(11, 9, 0.3))[0]
    opener = QueueOpener(FakeResponse(image_json))
    result = execute_operation(
        provider=provider,
        operation="generate",
        prompt="new futuristic architectural illustration",
        references=(reference,),
        client=HttpClient(opener=opener, sleeper=lambda _: None),
    )
    request = opener.requests[0][0]
    assert request.full_url == "http://127.0.0.1:8317/v1/images/edits"
    assert b'name="model"' in request.data
    assert b"gpt-image-2.6-flare" in request.data
    assert b'name="image"; filename="image-1-base.png"' in request.data
    assert b"Create a NEW image guided by the supplied reference images." in request.data
    assert b"not a canvas to preserve or minimally edit" in request.data
    assert b"new futuristic architectural illustration" in request.data
    assert b"gpt-5.4-mini" not in request.data
    assert b"complexity" not in request.data
    assert len(result.images) == 1
    assert result.report["operation"] == "generate"
    assert result.report["selected_protocol"] == "images"
    assert result.report["reference_generation"]["mode"] == "images_edit"
    assert result.report["reference_generation"]["transport_operation"] == "edit"
    assert [role["source_slot"] for role in result.report["input"]["roles"]] == [1]


def test_reference_guided_generation_keeps_reference_order_and_batch_count(
    cliproxy_provider, image_json
):
    provider = _images_first(cliproxy_provider, model="gpt-image-2.6-sunburst")
    references = encode_reference_slots(
        image_tensor(11, 9, 0.2),
        image_tensor(14, 10, 0.6),
        image_tensor(8, 9, 0.9),
    )
    opener = QueueOpener(FakeResponse(image_json), FakeResponse(image_json))
    result = execute_operation(
        provider=provider,
        operation="generate",
        prompt="create a completely new illustrated landscape",
        references=references,
        n=2,
        client=HttpClient(opener=opener, sleeper=lambda _: None),
    )
    assert len(opener.requests) == 2
    assert len(result.images) == 2
    assert len(result.report["requests"]) == 2
    for request, _timeout in opener.requests:
        body = request.data
        assert b'gpt-image-2.6-sunburst' in body
        assert b'name="image[]"; filename="image-1-base.png"' in body
        assert b'name="image[]"; filename="image-2-reference.png"' in body
        assert b'name="image[]"; filename="image-3-reference.png"' in body
        assert body.index(b"image-1-base.png") < body.index(b"image-2-reference.png")
        assert body.index(b"image-2-reference.png") < body.index(b"image-3-reference.png")
        assert b"Images 2 through 3 are additional ordered visual references" in body
    assert [role["source_slot"] for role in result.report["input"]["roles"]] == [1, 2, 3]
    assert result.report["protocol_notes"]["reference_mode"] == "images_edit"
    assert [req["index"] for req in result.report["requests"]] == [1, 2]


@pytest.mark.parametrize("model", ["gpt-image-2.6-flare", "gpt-image-2.6-sunburst"])
def test_gpt_image_26_text_generation_accepts_official_models_and_complexity(
    cliproxy_provider, image_json, model
):
    provider = _images_first(cliproxy_provider, model=model, complexity="high")
    opener = QueueOpener(FakeResponse(image_json))
    execute_operation(
        provider=provider,
        operation="generate",
        prompt="official GPT Image 2.6 request",
        client=HttpClient(opener=opener, sleeper=lambda _: None),
    )
    request = opener.requests[0][0]
    payload = json.loads(request.data)
    assert request.full_url.endswith("/v1/images/generations")
    assert payload["model"] == model
    assert payload["complexity"] == "high"


def test_complexity_on_images_edit_is_a_multipart_field(cliproxy_provider, image_json):
    provider = _images_first(
        cliproxy_provider, model="gpt-image-2.6-sunburst", complexity="medium"
    )
    base = tensor_to_png(image_tensor(13, 15), source_slot=1, role="base")
    opener = QueueOpener(FakeResponse(image_json))
    execute_operation(
        provider=provider,
        operation="edit",
        prompt="change the painting style",
        base_image=base,
        client=HttpClient(opener=opener, sleeper=lambda _: None),
    )
    request = opener.requests[0][0]
    assert request.full_url.endswith("/v1/images/edits")
    assert b'name="complexity"' in request.data
    assert b"\r\nmedium\r\n" in request.data


def test_optional_responses_mode_separates_text_and_image_models(cliproxy_provider):
    from conftest import png_b64
    provider = replace(
        cliproxy_provider,
        model="gpt-image-2.6-flare",
        responses_model="gpt-6.1-sol",
        reference_generate_mode="responses",
        image_complexity="low",
    )
    completed = {
        "type": "response.completed",
        "response": {
            "output": [{"type": "image_generation_call", "result": png_b64(10, 12)}]
        },
    }
    opener = QueueOpener(
        FakeResponse(
            ("data: " + json.dumps(completed) + "\n\n").encode(),
            headers={"content-type": "text/event-stream"},
        )
    )
    refs = encode_reference_slots(image_tensor(9, 9))
    result = execute_operation(
        provider=provider,
        operation="generate",
        prompt="reference style",
        references=refs,
        client=HttpClient(opener=opener, sleeper=lambda _: None),
    )
    request = opener.requests[0][0]
    body = json.loads(request.data)
    assert request.full_url.endswith("/v1/responses")
    assert body["model"] == "gpt-6.1-sol"
    assert body["tools"][0]["type"] == "image_generation"
    assert body["tools"][0]["model"] == "gpt-image-2.6-flare"
    assert body["tools"][0]["complexity"] == "low"
    assert result.report["selected_protocol"] == "responses"
    assert len(result.images) == 1


def test_images_first_does_not_require_an_unavailable_responses_model(
    cliproxy_provider
):
    provider = _images_first(cliproxy_provider)
    assert provider.responses_model == ""
    assert provider.reference_generate_mode == "images_edit"
    with pytest.raises(ValueError, match="requires responses_model"):
        replace(provider, reference_generate_mode="responses")
    with pytest.raises(ValueError, match="reference_generate_mode"):
        replace(provider, reference_generate_mode="unknown")
    with pytest.raises(ValueError, match="image_complexity"):
        replace(provider, image_complexity="ultra")


def test_new_fields_are_not_sensitive_or_added_to_legacy_providers(api_provider):
    assert api_provider.reference_generate_mode == "legacy"
    assert api_provider.image_complexity == "auto"
    assert "reference_generate_mode" not in api_provider.public_dict()
    assert "image_complexity" not in api_provider.public_dict()
    new = replace(
        api_provider,
        reference_generate_mode="images_edit",
        image_complexity="medium",
    )
    assert new.public_dict()["reference_generate_mode"] == "images_edit"
    assert new.public_dict()["image_complexity"] == "medium"
