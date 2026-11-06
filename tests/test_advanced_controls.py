"""Model-agnostic high-level controls following official ComfyUI GPT Image nodes."""
from __future__ import annotations

from unittest.mock import patch

import pytest

import nodes
from conftest import image_tensor
from gpt_image_bridge.config import ProviderConfig


def test_custom_size_validates_official_dimension_range():
    assert nodes._effective_image_size("Custom", 1024, 1536) == "1024x1536"
    assert nodes._effective_image_size("Custom", 2048, 1152) == "2048x1152"
    assert nodes._effective_image_size("auto", 1337, -100) == "auto"
    assert nodes._effective_image_size("3840x2160", 1024, 1024) == "3840x2160"
    invalid = (
        (479, 1024),       # below supported edge
        (3841, 2160),      # above supported edge
        (1025, 1024),      # not divisible by 16
        (480, 480),        # too few pixels
        (3840, 3840),      # too many pixels
        (3840, 480),       # excessive aspect ratio
    )
    for width, height in invalid:
        with pytest.raises(ValueError):
            nodes._effective_image_size("Custom", width, height)


def _provider():
    return ProviderConfig(
        auth_mode="api_key",
        base_url="http://127.0.0.1:8317/v1",
        model="gpt-image-2.6-sunburst",
        api_protocol="auto",
        api_key="unit-test-key",
        reference_generate_mode="images_edit",
    )


def test_generate_custom_dimensions_are_resolved_before_http_execution():
    with patch.object(nodes, "_run_and_convert", return_value=("img", "", "{}")) as run:
        actual = nodes.GPTImageBridgeGenerate().generate(
            provider=_provider(),
            prompt="a mountain landscape",
            size="Custom",
            quality="xhigh",
            background="auto",
            output_format="png",
            moderation="auto",
            n=1,
            timeout_sec=300,
            custom_width=2048,
            custom_height=1152,
        )
    assert actual == ("img", "", "{}")
    assert run.call_args.kwargs["size"] == "2048x1152"
    assert run.call_args.kwargs["quality"] == "xhigh"


def test_edit_custom_dimensions_are_resolved_before_http_execution():
    with patch.object(nodes, "_run_and_convert", return_value=("img", "", "{}")) as run:
        actual = nodes.GPTImageBridgeEdit().edit(
            provider=_provider(),
            prompt="change the lighting",
            size="Custom",
            quality="max",
            background="auto",
            output_format="png",
            moderation="auto",
            n=1,
            timeout_sec=300,
            custom_width=1024,
            custom_height=1024,
            **{nodes.BASE_IMAGE_INPUT_NAME: image_tensor(17, 19)},
        )
    assert actual == ("img", "", "{}")
    assert run.call_args.kwargs["size"] == "1024x1024"
    assert run.call_args.kwargs["quality"] == "max"


def test_more_references_have_stable_sequential_names():
    assert nodes.GENERATE_REFERENCE_INPUT_NAMES == tuple(
        f"reference_{i}" for i in range(1, 17)
    )
    assert nodes.REFERENCE_IMAGE_INPUT_NAMES == tuple(
        f"image_{i}" for i in range(2, 17)
    )
