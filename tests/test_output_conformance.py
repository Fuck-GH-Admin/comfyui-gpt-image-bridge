from __future__ import annotations

import io
import json

from PIL import Image

from conftest import FakeResponse, QueueOpener, png_b64
from gpt_image_bridge.config import with_protocol
from gpt_image_bridge.images import validate_image_bytes
from gpt_image_bridge.protocols import execute_operation, image_output_conformance
from gpt_image_bridge.transport import HttpClient


def image_bytes(mode: str) -> bytes:
    output = io.BytesIO()
    if mode == "RGBA":
        image = Image.new("RGBA", (8, 6), (20, 40, 60, 255))
        image.putpixel((0, 0), (20, 40, 60, 0))
    else:
        image = Image.new("RGB", (8, 6), (20, 40, 60))
    image.save(output, format="PNG")
    return output.getvalue()


def metadata(width=1024, height=1024, image_format="PNG", *, has_alpha=False, alpha_extrema=None):
    return {
        "width": width,
        "height": height,
        "format": image_format,
        "has_alpha": has_alpha,
        "alpha_extrema": alpha_extrema,
    }


def test_validate_image_bytes_reports_alpha_presence_and_extrema():
    _, rgba = validate_image_bytes(image_bytes("RGBA"))
    _, rgb = validate_image_bytes(image_bytes("RGB"))

    assert rgba["mode"] == "RGBA"
    assert rgba["has_alpha"] is True
    assert rgba["alpha_extrema"] == [0, 255]
    assert rgb["mode"] == "RGB"
    assert rgb["has_alpha"] is False
    assert rgb["alpha_extrema"] is None


def test_output_conformance_passes_when_actual_image_matches_request():
    result = image_output_conformance(
        size="1024x1024",
        background="transparent",
        output_format="png",
        images=[
            metadata(
                1024,
                1024,
                "PNG",
                has_alpha=True,
                alpha_extrema=[0, 255],
            )
        ],
    )

    assert result["status"] == "pass"
    assert result["checked_fields"] == ["size", "output_format", "background"]
    assert result["warnings"] == []
    assert result["checked_images"] == 1


def test_output_conformance_flags_size_format_and_transparency_mismatches():
    result = image_output_conformance(
        size="2048x1152",
        background="transparent",
        output_format="webp",
        images=[metadata(1536, 1024, "PNG")],
    )

    assert result["status"] == "warning"
    assert {item["field"] for item in result["warnings"]} == {
        "size",
        "output_format",
        "background",
    }
    size_warning = next(item for item in result["warnings"] if item["field"] == "size")
    assert size_warning["images"][0]["actual"] == "1536x1024"
    format_warning = next(
        item for item in result["warnings"] if item["field"] == "output_format"
    )
    assert format_warning["images"][0]["actual"] == "PNG"
    transparency_warning = next(
        item for item in result["warnings"] if item["field"] == "background"
    )
    assert transparency_warning["images"][0]["has_alpha"] is False


def test_output_conformance_respects_protocol_options_that_are_ignored():
    result = image_output_conformance(
        size="2048x1152",
        background="transparent",
        output_format="webp",
        images=[metadata(1536, 1024, "PNG")],
        ignored_options=("size", "background", "output_format"),
    )

    assert result["status"] == "not_checked"
    assert result["checked_fields"] == []
    assert result["warnings"] == []


def test_output_conformance_does_not_pass_when_no_image_was_returned():
    result = image_output_conformance(
        size="1024x1024",
        background="transparent",
        output_format="png",
        images=[],
    )
    assert result["status"] == "not_checked"
    assert result["checked_images"] == 0


def test_images_api_report_marks_real_response_mismatches(api_provider):
    provider = with_protocol(api_provider, "images")
    payload = {"data": [{"b64_json": png_b64(7, 9)}]}
    opener = QueueOpener(FakeResponse(json.dumps(payload).encode()))
    result = execute_operation(
        provider=provider,
        operation="generate",
        prompt="return a test image",
        size="1024x1024",
        background="transparent",
        output_format="webp",
        client=HttpClient(opener=opener, sleeper=lambda _: None),
    )

    conformance = result.report["output"]["conformance"]
    assert conformance["status"] == "warning"
    assert {item["field"] for item in conformance["warnings"]} == {
        "size",
        "output_format",
        "background",
    }

def test_responses_protocol_checks_fields_carried_by_image_generation_tool(api_provider):
    provider = with_protocol(api_provider, "responses")
    completed = {
        "type": "response.completed",
        "response": {
            "output": [
                {
                    "type": "image_generation_call",
                    "result": png_b64(7, 9),
                }
            ]
        },
    }
    opener = QueueOpener(
        FakeResponse(
            f"data: {json.dumps(completed)}\n\n".encode(),
            headers={"content-type": "text/event-stream"},
        )
    )

    result = execute_operation(
        provider=provider,
        operation="generate",
        prompt="check Responses output fields",
        size="1024x1024",
        background="transparent",
        output_format="webp",
        client=HttpClient(opener=opener, sleeper=lambda _: None),
    )

    tool = json.loads(opener.requests[0][0].data)["tools"][0]
    assert tool["size"] == "1024x1024"
    assert tool["background"] == "transparent"
    assert tool["output_format"] == "webp"
    conformance = result.report["output"]["conformance"]
    assert conformance["status"] == "warning"
    assert conformance["checked_fields"] == ["size", "output_format", "background"]
    assert {item["field"] for item in conformance["warnings"]} == {
        "size",
        "output_format",
        "background",
    }


def test_chat_completions_prompt_instruction_size_is_not_asserted(api_provider):
    provider = with_protocol(api_provider, "chat_completions")
    payload = {
        "choices": [
            {
                "message": {
                    "images": [{"b64_json": png_b64(7, 9)}],
                }
            }
        ]
    }
    opener = QueueOpener(FakeResponse(json.dumps(payload).encode()))

    result = execute_operation(
        provider=provider,
        operation="generate",
        prompt="check Chat Completions output fields",
        size="1024x1024",
        background="transparent",
        output_format="webp",
        client=HttpClient(opener=opener, sleeper=lambda _: None),
    )

    assert result.report["protocol_notes"]["size_transport"] == "prompt_instruction"
    conformance = result.report["output"]["conformance"]
    assert conformance["status"] == "not_checked"
    assert conformance["checked_fields"] == []
    assert conformance["warnings"] == []


def test_native_oauth_ignored_background_and_format_leave_size_checkable():
    result = image_output_conformance(
        size="1024x1024",
        background="transparent",
        output_format="webp",
        images=[metadata(1536, 1024, "PNG")],
        ignored_options=("background", "output_format"),
    )

    assert result["status"] == "warning"
    assert result["checked_fields"] == ["size"]
    assert [item["field"] for item in result["warnings"]] == ["size"]


def test_unrecognized_or_uncomparable_options_are_not_checked():
    result = image_output_conformance(
        size="Custom",
        background="opaque",
        output_format="svg",
        images=[metadata(1536, 1024, "PNG")],
    )

    assert result["status"] == "not_checked"
    assert result["checked_fields"] == []
    assert result["warnings"] == []

