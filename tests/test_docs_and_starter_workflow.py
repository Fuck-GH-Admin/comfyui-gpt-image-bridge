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
    assert "git clone --branch main" in readme
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
    assert by_id[1]["type"] == "GPTImageBridgeProviderProfile"
    assert by_id[2]["type"] == "GPTImageBridgeGenerate"
    assert by_id[3]["type"] == "SaveImage"
    assert by_id[1]["widgets_values"] == ["local_codex", "", "profile", ""]
    provider_schema = nodes.GPTImageBridgeProviderProfile.INPUT_TYPES()
    assert [item["name"] for item in by_id[1]["inputs"][:1]] == list(provider_schema["required"])
    assert [item["name"] for item in by_id[1]["inputs"][1:]] == list(provider_schema["optional"])
    assert "api_key" not in json.dumps(by_id[1])
    assert "base_url" not in json.dumps(by_id[1])
    assert [item["name"] for item in by_id[2]["inputs"][:9]] == list(
        nodes.GPTImageBridgeGenerate.INPUT_TYPES()["required"]
    )
    assert [item["name"] for item in by_id[2]["inputs"][9:]] == [
        "reference_1",
        "reference_batch",
    ]
    assert by_id[1]["outputs"][0]["links"] == [1]
    assert by_id[2]["outputs"][0]["links"] == [2]
    assert by_id[2]["inputs"][0]["link"] == 1
    assert by_id[3]["inputs"][0]["link"] == 2
    assert by_id[1]["widgets_values"][0] == "local_codex"
    assert "Bearer " not in STARTER.read_text(encoding="utf-8")
    assert "access_token" not in STARTER.read_text(encoding="utf-8")
    assert "refresh_token" not in STARTER.read_text(encoding="utf-8")


def test_native_comfy_text_and_size_workflow_uses_only_standard_primitive_nodes():
    workflow_file = ROOT / "example_workflows/Native-ComfyUI-Text-and-Size.json"
    data = json.loads(workflow_file.read_text(encoding="utf-8"))
    assert data["version"] == 0.4
    nodes_by_id = {node["id"]: node for node in data["nodes"]}
    assert {node["type"] for node in data["nodes"]} == {
        "GPTImageBridgeProviderProfile",
        "GPTImageBridgeGenerate",
        "PrimitiveStringMultiline",
        "PrimitiveInt",
        "SaveImage",
    }
    assert sum(n["type"] == "PrimitiveInt" for n in data["nodes"]) == 2
    generate = nodes_by_id[2]
    assert generate["widgets_values"][1] == "Custom"
    by_name = {input_["name"]: input_ for input_ in generate["inputs"]}
    assert by_name["prompt"]["link"] == 3
    assert by_name["custom_width"]["link"] == 4
    assert by_name["custom_height"]["link"] == 5
    assert by_name["reference_batch"]["link"] is None
    assert nodes_by_id[4]["type"] == "PrimitiveStringMultiline"
    assert nodes_by_id[5]["type"] == "PrimitiveInt"
    assert nodes_by_id[6]["type"] == "PrimitiveInt"
    assert [nodes_by_id[x]["widgets_values"][0] for x in [5, 6]] == [1536, 1024]
    assert len(data["links"]) == 5
    assert "api_key" not in workflow_file.read_text(encoding="utf-8")
    assert "base_url" not in workflow_file.read_text(encoding="utf-8")
