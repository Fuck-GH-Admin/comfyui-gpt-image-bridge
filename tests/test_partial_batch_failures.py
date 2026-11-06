"""Paid multi-output requests: failed later calls must report partial progress.

No real API is contacted; each attempt is backed by QueueOpener fixtures.
"""
from __future__ import annotations

import json

import pytest

from conftest import FakeResponse, QueueOpener, png_b64
from gpt_image_bridge.config import with_protocol
from gpt_image_bridge.errors import BridgeError
from gpt_image_bridge.protocols import execute_operation
from gpt_image_bridge.transport import HttpClient


def _one_image_response(protocol):
    encoded = png_b64()
    if protocol == "images":
        return FakeResponse(json.dumps({"data": [{"b64_json": encoded}]}).encode())
    if protocol == "responses":
        event = {
            "type": "response.completed",
            "response": {"output": [{"type": "image_generation_call", "result": encoded}]},
        }
        return FakeResponse(
            ("data: " + json.dumps(event) + "\n\n").encode(),
            headers={"content-type": "text/event-stream"},
        )
    return FakeResponse(
        json.dumps({"choices": [{"message": {"images": [{"b64_json": encoded}]}}]}).encode()
    )


@pytest.mark.parametrize("protocol", ["images", "responses", "chat_completions"])
def test_second_output_network_failure_reports_partial_progress_without_retry(
    cliproxy_provider, protocol
):
    provider = with_protocol(cliproxy_provider, protocol)
    opener = QueueOpener(_one_image_response(protocol), OSError("connection lost"))
    with pytest.raises(BridgeError) as captured:
        execute_operation(
            provider=provider,
            operation="generate",
            prompt="two paid outputs",
            n=2,
            client=HttpClient(opener=opener, sleeper=lambda _: None),
        )

    error = captured.value
    assert len(opener.requests) == 2  # no auto-resubmit of the failed request
    assert error.error_code == "network_error"
    assert error.safe_to_resubmit is False
    assert error.remote_task_may_continue is True
    assert error.batch_progress == {
        "requested_outputs": 2,
        "confirmed_outputs": 1,
        "failed_request_index": 2,
        "batch_outputs_delivered": False,
        "whole_batch_retry_risk": "may_duplicate_outputs",
    }
    assert error.report()["batch_progress"] == error.batch_progress
    assert cliproxy_provider.api_key not in str(error)


def test_successful_http_response_with_missing_second_image_is_not_a_safe_batch_retry(
    cliproxy_provider,
):
    opener = QueueOpener(
        _one_image_response("images"),
        FakeResponse(json.dumps({"data": []}).encode()),
    )
    with pytest.raises(BridgeError) as captured:
        execute_operation(
            provider=cliproxy_provider,
            operation="generate",
            prompt="partial images",
            n=2,
            client=HttpClient(opener=opener, sleeper=lambda _: None),
        )
    assert len(opener.requests) == 2
    assert captured.value.safe_to_resubmit is False
    assert captured.value.batch_progress["confirmed_outputs"] == 1
    assert captured.value.batch_progress["failed_request_index"] == 2


def test_first_output_failure_marks_zero_confirmed_outputs(cliproxy_provider):
    opener = QueueOpener(OSError("connection lost"))
    with pytest.raises(BridgeError) as captured:
        execute_operation(
            provider=cliproxy_provider,
            operation="generate",
            prompt="first failure",
            n=3,
            client=HttpClient(opener=opener, sleeper=lambda _: None),
        )
    assert len(opener.requests) == 1
    assert captured.value.batch_progress["confirmed_outputs"] == 0
    assert captured.value.batch_progress["failed_request_index"] == 1


def test_single_output_error_has_no_batch_annotation(cliproxy_provider):
    opener = QueueOpener(OSError("connection lost"))
    with pytest.raises(BridgeError) as captured:
        execute_operation(
            provider=cliproxy_provider,
            operation="generate",
            prompt="one",
            n=1,
            client=HttpClient(opener=opener, sleeper=lambda _: None),
        )
    assert len(opener.requests) == 1
    assert captured.value.batch_progress is None
