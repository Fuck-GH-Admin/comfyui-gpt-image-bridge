"""Documentation consistency and no-secret ComfyUI starter workflow contract.

The starter is for dragging into a real ComfyUI UI; this test verifies the
serialized graph and node contract without requiring a browser or paid API.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import nodes


ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)")
STARTER = ROOT / "example_workflows/CLIProxyAPI-Text-to-Image.json"


def test_all_local_markdown_links_exist_and_fences_are_balanced():
    docs = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    assert len(docs) >= 8, "Documentation index or guides are missing"
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        fences = [line for line in text.splitlines() if line.lstrip().startswith("```")]
        assert len(fences) % 2 == 0, f"Unbalanced code fences in {doc}"
        for match in LINK_RE.finditer(text):
            href = match.group(1)
            if href.startswith(("#", "https://", "http://", "mailto:", "data:")):
                continue
            path = unquote(urlsplit(href).path)
            target = (doc.parent / path).resolve()
            assert target.is_relative_to(ROOT.resolve()), f"Link escapes repository: {doc} {href}"
            assert target.exists(), f"Broken relative link: {doc} -> {href}"


def test_readme_is_a_short_usage_guide():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert len(readme.splitlines()) <= 130
    assert "feat/image26-images-first-reference-mode" in readme
    assert "docs/README.md" in readme
    assert "CLIProxyAPI-Text-to-Image.json" in readme


def test_cliproxyapi_starter_workflow_is_connected_and_has_no_secrets():
    workflow = json.loads(STARTER.read_text(encoding="utf-8"))
    assert workflow["version"] == 0.4
    assert workflow["last_node_id"] == 3
    assert workflow["last_link_id"] == 2
    assert workflow["links"] == [
        [1, 1, 0, 2, 0, "GPT_IMAGE_PROVIDER"],
        [2, 2, 0, 3, 0, "IMAGE"],
    ]
    by_id = {node["id"]: node for node in workflow["nodes"]}
    assert len(by_id) == 3
    assert by_id[1]["type"] == "GPTImageBridgeCLIProxyAPIProvider"
    assert by_id[2]["type"] == "GPTImageBridgeGenerate"
    assert by_id[3]["type"] == "SaveImage"
    assert by_id[1]["widgets_values"] == [
        "",
        "http://127.0.0.1:8317/v1",
        "gpt-image-2.6-flare",
        "",
        "images_edit",
        "auto",
    ]
    provider_schema = nodes.GPTImageBridgeCLIProxyAPIProvider.INPUT_TYPES()
    assert [item["name"] for item in by_id[1]["inputs"][:4]] == list(
        provider_schema["required"]
    )
    assert [item["name"] for item in by_id[1]["inputs"][4:]] == list(
        provider_schema["optional"]
    )
    assert [item["name"] for item in by_id[2]["inputs"][:9]] == list(
        nodes.GPTImageBridgeGenerate.INPUT_TYPES()["required"]
    )
    assert [item["name"] for item in by_id[2]["inputs"][9:]] == [
        "reference_1",
        "reference_2",
        "reference_3",
    ]
    assert by_id[1]["outputs"][0]["links"] == [1]
    assert by_id[2]["outputs"][0]["links"] == [2]
    assert by_id[2]["inputs"][0]["link"] == 1
    assert by_id[3]["inputs"][0]["link"] == 2
    assert by_id[1]["widgets_values"][0] == ""
    assert "Bearer " not in STARTER.read_text(encoding="utf-8")
    assert "access_token" not in STARTER.read_text(encoding="utf-8")
    assert "refresh_token" not in STARTER.read_text(encoding="utf-8")
