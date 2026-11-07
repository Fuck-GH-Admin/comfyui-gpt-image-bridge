#!/usr/bin/env python3
"""Real ComfyUI HTTP/queue smoke test against an in-process fake CLIProxyAPI.

This deliberately starts the actual ComfyUI server and executes its workflow
graph. Only the remote image service is simulated; no OAuth credentials or
paid image-generation calls are involved.
"""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageDraw

CLIENT_KEY = "ci-cliproxy-client-key-not-an-oauth-token"
EXPECTED_NODES = {
    "GPTImageBridgeAPIProvider",
    "GPTImageBridgeProviderProfile",
    "GPTImageBridgeCLIProxyAPIProvider",
    "GPTImageBridgeOAuthProvider",
    "GPTImageBridgeReferenceList",
    "GPTImageBridgeGenerate",
    "GPTImageBridgeEdit",
    "GPTImageBridgeSaveImage",
}
REQUESTS = []
REQUESTS_LOCK = threading.Lock()


def png_data(width: int = 32, height: int = 24, *, alpha: bool = False) -> bytes:
    output = io.BytesIO()
    if alpha:
        image = Image.new("RGBA", (width, height), (70, 125, 210, 255))
        ImageDraw.Draw(image).rectangle(
            (0, 0, max(0, width // 2 - 1), height - 1),
            fill=(70, 125, 210, 0),
        )
    else:
        image = Image.new("RGB", (width, height), (70, 125, 210))
    image.save(output, "PNG")
    return output.getvalue()


# The fake upstream deliberately returns RGBA so this smoke test exercises
# decoding, ComfyUI IMAGE transport, and the built-in SaveImage node end to end.
PNG_B64 = base64.b64encode(png_data(alpha=True)).decode("ascii")


class FakeCLIProxyAPI(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        # Never echo received credentials into CI logs.
        return

    def _write(self, payload: bytes, *, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        auth = self.headers.get("Authorization")
        if auth != "Bearer " + CLIENT_KEY:
            self._write(b'{"error":"invalid_client_key"}', status=401)
            return

        if self.path == "/v1/images/generations":
            try:
                request = json.loads(body)
                valid = (
                    request.get("model") == "gpt-image-2.6-flare"
                    and bool(request.get("prompt"))
                    and request.get("n") == 1
                )
            except (ValueError, TypeError):
                valid = False
            kind = "generate"

        elif self.path == "/v1/images/edits":
            guided_generation = b"Create a NEW image guided by" in body
            if guided_generation:
                # Single reference uses the Images 'image' field; multiple
                # references use the API's 'image[]' field consistently.
                first_single = b'name="image"; filename="image-1-base.png"' in body
                first_multi = b'name="image[]"; filename="image-1-base.png"' in body
                second_multi = b'name="image[]"; filename="image-2-reference.png"' in body
                has_second = b"image-2-reference.png" in body
                valid = (
                    b'name="model"' in body
                    and b"gpt-image-2.6-flare" in body
                    and (first_single or first_multi)
                    and b"not a canvas to preserve or minimally edit" in body
                    and (
                        (not has_second and first_single)
                        or (has_second and first_multi and second_multi
                            and body.index(b"image-1-base.png") < body.index(b"image-2-reference.png"))
                    )
                )
                kind = "reference_image_edit"
            else:
                valid = (
                    b'name="model"' in body
                    and b"gpt-image-2.6-flare" in body
                    and b'name="image[]"; filename="image-1-base.png"' in body
                    and b'name="image[]"; filename="image-2-reference.png"' in body
                    and body.index(b"image-1-base.png") < body.index(b"image-2-reference.png")
                )
                kind = "edit"

        elif self.path == "/v1/responses":
            try:
                request = json.loads(body)
                tools = request.get("tools") or []
                content = request["input"][1]["content"]
                valid = (
                    request.get("model") == "gpt-6.1-sol"
                    and tools[0]["type"] == "image_generation"
                    and tools[0]["model"] == "gpt-image-2.6-flare"
                    and tools[0]["action"] == "generate"
                    and any(part.get("type") == "input_image" for part in content)
                )
            except (ValueError, TypeError, KeyError, IndexError):
                valid = False
            kind = "reference"

        else:
            self._write(b'{"error":"unexpected_endpoint"}', status=404)
            return

        with REQUESTS_LOCK:
            REQUESTS.append({"kind": kind, "valid": valid})
        if not valid:
            self._write(b'{"error":"invalid_request_shape"}', status=422)
            return

        if kind == "reference":
            event = {
                "type": "response.completed",
                "response": {
                    "output": [
                        {"type": "image_generation_call", "result": PNG_B64}
                    ]
                },
            }
            frame = ("data: " + json.dumps(event) + "\n\n").encode("utf-8")
            self._write(frame, content_type="text/event-stream")
        else:
            self._write(json.dumps({"data": [{"b64_json": PNG_B64}]}).encode())


def http_json(base: str, path: str, payload: dict | None = None):
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"} if body is not None else {}
    request = urllib.request.Request(
        base + path, data=body, headers=headers, method="POST" if body is not None else "GET"
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read()), response.headers


def unused_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def provider_inputs(api_key: str, proxy_url: str, mode: str = "images_edit"):
    return {
        "api_key": api_key,
        "base_url": proxy_url + "/v1",
        "image_model": "gpt-image-2.6-flare",
        "responses_model": "gpt-6.1-sol" if mode == "responses" else "",
        "reference_mode": mode,
        "image_complexity": "auto",
    }


def generate_inputs(provider_node: str, *, n: int = 1):
    return {
        "provider": [provider_node, 0],
        "prompt": "Return a 32x24 blue test image",
        "size": "auto",
        "quality": "auto",
        "background": "auto",
        "output_format": "png",
        "moderation": "auto",
        "n": n,
        "timeout_sec": 120,
    }


def wait_for_history(base: str, prompt_id: str, log_path: Path, timeout: int = 90):
    stop_at = time.monotonic() + timeout
    while time.monotonic() < stop_at:
        result, _ = http_json(base, "/history/" + prompt_id)
        if prompt_id in result:
            item = result[prompt_id]
            status = item.get("status", {})
            if status.get("status_str") == "error":
                raise AssertionError("ComfyUI execution errored; inspect server logs")
            return item
        time.sleep(0.4)
    tail = log_path.read_text(encoding="utf-8", errors="replace")[-6000:]
    raise AssertionError("ComfyUI workflow did not finish; server log tail:\n" + tail)


def queue_workflow(
    base: str,
    proxy_url: str,
    graph: dict,
    output_node: str,
    expected_count: int,
    log_path: Path,
    output_dir: Path,
    *,
    reference_mode: str = "images_edit",
    expected_format: str = "png",
):
    is_profile = graph["1"]["class_type"] == "GPTImageBridgeProviderProfile"
    if not is_profile:
        credential, headers = http_json(
            base, "/gpt-image-bridge/session-credential", {"api_key": CLIENT_KEY}
        )
    if is_profile:
        graph["1"]["inputs"] = {
            "profile": "ci_gateway", "image_model": "",
            "reference_mode": "profile", "responses_model": "",
        }
    else:
        assert "no-store" in headers.get("Cache-Control", "").lower()
        handle = credential["credential_handle"]
        assert handle.startswith("gpt-image-bridge-session:")
        assert CLIENT_KEY not in handle
        graph["1"]["inputs"] = provider_inputs(handle, proxy_url, reference_mode)

    workflow = {
        "nodes": [{
            "type": "GPTImageBridgeProviderProfile" if is_profile else "GPTImageBridgeCLIProxyAPIProvider",
            "widgets_values": (
                ["ci_gateway", "", "profile", ""]
                if is_profile else [
                    CLIENT_KEY, proxy_url + "/v1", "gpt-image-2.6-flare",
                    "gpt-6.1-sol" if reference_mode == "responses" else "",
                    reference_mode, "auto",
                ]
            ),
        }]
    }
    if is_profile:
        assert CLIENT_KEY not in json.dumps(workflow)
        assert "api_key" not in json.dumps(workflow)
    queued, _ = http_json(
        base,
        "/prompt",
        {
            "prompt": graph,
            "extra_data": {"extra_pnginfo": {"workflow": workflow}},
        },
    )
    assert "prompt_id" in queued, "ComfyUI rejected the graph: " + str(queued)
    history = wait_for_history(base, queued["prompt_id"], log_path)
    assert CLIENT_KEY not in json.dumps(history), "A raw proxy client key leaked to ComfyUI history"
    output = history.get("outputs", {}).get(output_node, {})
    images = output.get("images", [])
    assert len(images) == expected_count, (
        "Expected %s saved images, received %s; history=%s"
        % (expected_count, len(images), str(history)[:2500])
    )
    expected_extension = {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}[expected_format]
    expected_pillow_format = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}[expected_format]
    assert all(image.get("filename", "").endswith(expected_extension) for image in images)
    for saved in images:
        full_path = (output_dir / saved.get("subfolder", "") / saved["filename"]).resolve()
        assert full_path.is_relative_to(output_dir.resolve()), "Invalid saved-image path"
        assert full_path.is_file(), "Save node reported a missing output file"
        with Image.open(full_path) as loaded:
            loaded.verify()
        with Image.open(full_path) as loaded:
            assert loaded.format == expected_pillow_format
            assert loaded.size == (32, 24), "Saved dimensions differ from proxy output"
            if expected_format in ("png", "webp"):
                assert loaded.mode == "RGBA", "Lossless-alpha format dropped the upstream alpha channel"
                assert loaded.getchannel("A").getextrema() == (0, 255), "Saved alpha samples changed"
            else:
                assert loaded.mode == "RGB", "JPEG must be flattened to RGB"
            metadata = json.dumps(loaded.info, ensure_ascii=False)
            assert CLIENT_KEY not in metadata, "A raw client key leaked to image metadata"
    return images


def run(root: Path):
    if not (root / "main.py").is_file():
        raise RuntimeError("Actual ComfyUI repository is required, not a mock")
    assert (root / "custom_nodes" / "comfyui-gpt-image-bridge" / "__init__.py").is_file()

    input_dir = root / "input"
    input_dir.mkdir(exist_ok=True)
    (input_dir / "bridge_reference.png").write_bytes(png_data(47, 29))

    fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeCLIProxyAPI)
    fake_thread = threading.Thread(target=fake.serve_forever, daemon=True)
    fake_thread.start()
    proxy_url = "http://127.0.0.1:" + str(fake.server_address[1])
    comfy_url = "http://127.0.0.1:" + str(unused_port())
    log_path = Path(tempfile.gettempdir()) / "comfyui-cliproxy-smoke.log"
    profile_dir = Path(tempfile.mkdtemp(prefix="bridge-ci-profiles-"))
    profile_path = profile_dir / "providers.local.json"
    profile_path.write_text(json.dumps({"profiles": {"ci_gateway": {
        "base_url": proxy_url + "/v1", "api_key": CLIENT_KEY,
        "model": "gpt-image-2.6-flare", "api_protocol": "auto",
        "reference_mode": "images_edit", "use_async": False,
    }}}), encoding="utf-8")
    os.chmod(profile_path, 0o600)

    command = [
        sys.executable,
        str(root / "main.py"),
        "--cpu",
        "--listen", "127.0.0.1",
        "--port", comfy_url.rsplit(":", 1)[1],
        "--disable-auto-launch",
        "--offline",
        "--log-stdout",
    ]
    process = None
    try:
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                command,
                cwd=root,
                stdout=log,
                stderr=subprocess.STDOUT,
                env={**os.environ, "HF_HUB_OFFLINE": "1", "GPT_IMAGE_BRIDGE_PROVIDERS_FILE": str(profile_path)},
            )
        started = time.monotonic()
        while time.monotonic() - started < 240:
            if process.poll() is not None:
                raise RuntimeError("ComfyUI exited during startup")
            try:
                node_data, _ = http_json(comfy_url, "/object_info/GPTImageBridgeCLIProxyAPIProvider")
                if "GPTImageBridgeCLIProxyAPIProvider" in node_data:
                    break
            except (urllib.error.URLError, TimeoutError, ValueError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError("ComfyUI did not register the provider within 240 seconds")

        missing = []
        for node in sorted(EXPECTED_NODES):
            data, _ = http_json(comfy_url, "/object_info/" + node)
            if node not in data:
                missing.append(node)
        assert not missing, "Missing actual ComfyUI nodes: " + str(missing)
        info, _ = http_json(comfy_url, "/system_stats")
        version = info.get("system", {}).get("comfyui_version")
        print("[PASS] Real ComfyUI server started. Version:", version, flush=True)
        print("[PASS] All 8 GPT Image Bridge custom nodes registered", flush=True)
        for builtin in ("PrimitiveStringMultiline", "PrimitiveInt", "BatchImagesNode", "GetImageSize", "SaveImage"):
            built_info, _ = http_json(comfy_url, "/object_info/" + builtin)
            assert builtin in built_info, "Missing native ComfyUI node: " + builtin
        print("[PASS] Native ComfyUI Text/Int/BatchImagesNode/GetImageSize/SaveImage nodes registered", flush=True)
        for legacy_name in (
            "GPTImageBridgeAPIProvider",
            "GPTImageBridgeCLIProxyAPIProvider",
            "GPTImageBridgeOAuthProvider",
        ):
            legacy_info, _ = http_json(comfy_url, "/object_info/" + legacy_name)
            assert legacy_info[legacy_name].get("deprecated") is True
            assert legacy_info[legacy_name].get("dev_only") is True
        print("[PASS] Old Provider nodes flagged deprecated and hidden in ordinary search", flush=True)

        # Fail closed on raw API keys: the ComfyUI queue must never persist them.
        raw_graph = {
            "1": {"class_type": "GPTImageBridgeCLIProxyAPIProvider", "inputs": provider_inputs(CLIENT_KEY, proxy_url)},
            "2": {"class_type": "GPTImageBridgeGenerate", "inputs": generate_inputs("1")},
            "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0], "filename_prefix": "ShouldNotExist"}},
        }
        try:
            http_json(comfy_url, "/prompt", {"prompt": raw_graph})
        except urllib.error.HTTPError as error:
            assert error.code == 400, "Unexpected raw-key rejection status: " + str(error.code)
        else:
            raise AssertionError("ComfyUI accepted a raw API key into its queue")
        assert not REQUESTS, "A rejected raw-key graph reached the proxy"
        print("[PASS] Prompt guard rejects raw keys before enqueue", flush=True)
        # A forged Profile node must not make it possible to push a raw
        # credential into a shareable ComfyUI prompt/history.
        injected_profile = {
            "1": {
                "class_type": "GPTImageBridgeProviderProfile",
                "inputs": {"profile": "ci_gateway", "api_key": CLIENT_KEY},
            },
            "2": {"class_type": "GPTImageBridgeGenerate", "inputs": generate_inputs("1")},
            "3": {"class_type": "SaveImage", "inputs": {
                "images": ["2", 0], "filename_prefix": "InjectedProfileMustNotSave",
            }},
        }
        try:
            http_json(comfy_url, "/prompt", {"prompt": injected_profile})
        except urllib.error.HTTPError as error:
            assert error.code == 400, "Raw key in Profile graph should be rejected"
        else:
            raise AssertionError("ComfyUI accepted raw API Key injected into Profile node")
        assert not REQUESTS, "Rejected Profile prompt was forwarded to the gateway"
        print("[PASS] Provider Profile rejects injected raw Key before queue insertion", flush=True)

        # Text-to-image: n=2 means two real ComfyUI->proxy HTTP requests.
        graph = {
            "1": {"class_type": "GPTImageBridgeCLIProxyAPIProvider", "inputs": {}},
            "2": {"class_type": "GPTImageBridgeGenerate", "inputs": generate_inputs("1", n=2)},
            "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0], "filename_prefix": "CI-Text"}},
        }
        images = queue_workflow(comfy_url, proxy_url, graph, "3", 2, log_path, root / "output")
        assert all(x["filename"].startswith("CI-Text") for x in images)
        print("[PASS] Text generation n=2 -> 2 actual PNG files (32x24), metadata scrubbed", flush=True)

        # Local saver: preserve the upstream alpha in lossless WebP.
        graph = {
            "1": {"class_type": "GPTImageBridgeCLIProxyAPIProvider", "inputs": {}},
            "2": {"class_type": "GPTImageBridgeGenerate", "inputs": generate_inputs("1")},
            "12": {
                "class_type": "GPTImageBridgeSaveImage",
                "inputs": {
                    "images": ["2", 0],
                    "file_format": "webp",
                    "filename_prefix": "CI-Bridge-WebP",
                    "quality": 100,
                    "png_compress_level": 4,
                    "webp_lossless": True,
                    "jpeg_background": "#FFFFFF",
                },
            },
        }
        webp_images = queue_workflow(
            comfy_url, proxy_url, graph, "12", 1, log_path, root / "output",
            expected_format="webp",
        )
        assert webp_images[0]["filename"].startswith("CI-Bridge-WebP")
        print("[PASS] Custom saver writes lossless WebP and preserves RGBA alpha", flush=True)

        # JPEG cannot carry alpha; the saver composites transparent pixels over the configured matte.
        graph = {
            "1": {"class_type": "GPTImageBridgeCLIProxyAPIProvider", "inputs": {}},
            "2": {"class_type": "GPTImageBridgeGenerate", "inputs": generate_inputs("1")},
            "13": {
                "class_type": "GPTImageBridgeSaveImage",
                "inputs": {
                    "images": ["2", 0],
                    "file_format": "jpeg",
                    "filename_prefix": "CI-Bridge-JPEG",
                    "quality": 100,
                    "png_compress_level": 4,
                    "webp_lossless": False,
                    "jpeg_background": "#FFFFFF",
                },
            },
        }
        jpeg_images = queue_workflow(
            comfy_url, proxy_url, graph, "13", 1, log_path, root / "output",
            expected_format="jpeg",
        )
        assert jpeg_images[0]["filename"].startswith("CI-Bridge-JPEG")
        jpeg_path = root / "output" / jpeg_images[0]["filename"]
        with Image.open(jpeg_path) as jpeg:
            pixels = jpeg.convert("RGB")
            assert min(pixels.getpixel((4, 12))) > 235, "JPEG transparent area was not composited over white"
        print("[PASS] Custom saver writes JPEG and composites alpha over the chosen matte", flush=True)

        # Reference generation: actual LoadImage -> Generate -> SaveImage graph.
        graph = {
            "1": {"class_type": "GPTImageBridgeCLIProxyAPIProvider", "inputs": {}},
            "4": {"class_type": "LoadImage", "inputs": {"image": "bridge_reference.png"}},
            "5": {"class_type": "GPTImageBridgeGenerate", "inputs": {**generate_inputs("1"), "reference_1": ["4", 0]}},
            "6": {"class_type": "SaveImage", "inputs": {"images": ["5", 0], "filename_prefix": "CI-Reference"}},
        }
        queue_workflow(comfy_url, proxy_url, graph, "6", 1, log_path, root / "output")
        print("[PASS] Default reference generation -> Images Edit -> actual PNG", flush=True)

        # Opt-in Responses mode retains a separate mainline model and image tool.
        graph = {
            "1": {"class_type": "GPTImageBridgeCLIProxyAPIProvider", "inputs": {}},
            "4": {"class_type": "LoadImage", "inputs": {"image": "bridge_reference.png"}},
            "10": {"class_type": "GPTImageBridgeGenerate", "inputs": {**generate_inputs("1"), "reference_1": ["4", 0]}},
            "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "CI-Reference-Responses"}},
        }
        queue_workflow(
            comfy_url, proxy_url, graph, "11", 1, log_path, root / "output",
            reference_mode="responses",
        )
        print("[PASS] Opt-in Responses reference generation -> actual PNG", flush=True)

        # Edit: actual reference-list node, base IMAGE, multipart upload and save.
        graph = {
            "1": {"class_type": "GPTImageBridgeCLIProxyAPIProvider", "inputs": {}},
            "4": {"class_type": "LoadImage", "inputs": {"image": "bridge_reference.png"}},
            "7": {"class_type": "GPTImageBridgeReferenceList", "inputs": {"image_2": ["4", 0]}},
            "8": {
                "class_type": "GPTImageBridgeEdit",
                "inputs": {
                    **generate_inputs("1"),
                    "base_image（Image 1）": ["4", 0],
                    "references（Image 2 开始）": ["7", 0],
                },
            },
            "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "CI-Edit"}},
        }
        queue_workflow(comfy_url, proxy_url, graph, "9", 1, log_path, root / "output")
        print("[PASS] Editing -> actual PNG file via IMAGE/reference list/multipart/SaveImage", flush=True)

        # Native ComfyUI text editing and image batching, without our own
        # prompt editor or reference collector node. Modern BatchImagesNode is registered in the pinned ComfyUI 0.44.0;
        # V3 Autogrow inputs use namespaced prompt keys images.image0 etc.
        graph = {
            "1": {"class_type": "GPTImageBridgeProviderProfile", "inputs": {}},
            "4": {"class_type": "LoadImage", "inputs": {"image": "bridge_reference.png"}},
            "14": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": "Create a completely NEW reference-inspired image"}},
            "15": {"class_type": "BatchImagesNode", "inputs": {"images.image0": ["4", 0], "images.image1": ["4", 0]}},
            "16": {"class_type": "GPTImageBridgeGenerate", "inputs": {
                **generate_inputs("1"),
                "prompt": ["14", 0],
                "reference_batch": ["15", 0],
            }},
            "17": {"class_type": "SaveImage", "inputs": {
                "images": ["16", 0], "filename_prefix": "CI-Native-Reference-Batch",
            }},
        }
        queue_workflow(comfy_url, proxy_url, graph, "17", 1, log_path, root / "output")
        print("[PASS] Native multiline Text + native Batch Images -> bridge Generate -> native SaveImage", flush=True)

        # Native batch also feeds Edit without the deprecated Bridge Reference List.
        graph = {
            "1": {"class_type": "GPTImageBridgeProviderProfile", "inputs": {}},
            "4": {"class_type": "LoadImage", "inputs": {"image": "bridge_reference.png"}},
            "15": {"class_type": "BatchImagesNode", "inputs": {"images.image0": ["4", 0], "images.image1": ["4", 0]}},
            "18": {"class_type": "GPTImageBridgeEdit", "inputs": {
                **generate_inputs("1"),
                "base_image（Image 1）": ["4", 0],
                "reference_batch": ["15", 0],
            }},
            "19": {"class_type": "SaveImage", "inputs": {
                "images": ["18", 0], "filename_prefix": "CI-Native-Edit-Batch",
            }},
        }
        queue_workflow(comfy_url, proxy_url, graph, "19", 1, log_path, root / "output")
        print("[PASS] Native Batch Images -> bridge Edit -> native SaveImage", flush=True)

        # Profile provider: server-side Key only, never a workflow widget or queue field.
        graph = {
            "1": {"class_type": "GPTImageBridgeProviderProfile", "inputs": {}},
            "2": {"class_type": "GPTImageBridgeGenerate", "inputs": generate_inputs("1")},
            "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0], "filename_prefix": "CI-Profile"}},
        }
        queue_workflow(comfy_url, proxy_url, graph, "3", 1, log_path, root / "output")
        print("[PASS] Local third-party-style profile generated via actual ComfyUI without Key widget", flush=True)

        with REQUESTS_LOCK:
            observed = list(REQUESTS)
        assert [item["kind"] for item in observed] == [
            "generate",
            "generate",
            "generate",
            "generate",
            "reference_image_edit",
            "reference",
            "edit",
            "reference_image_edit",
            "edit",
            "generate",
        ], "Unexpected proxy requests: " + str(observed)
        assert all(item["valid"] for item in observed)
        print("[PASS] 10 proxy HTTP requests matched native image batches, two reference modes and local savers", flush=True)
        print("COMFYUI_SMOKE_PASS", flush=True)

    except Exception:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-10000:] if log_path.exists() else ""
        print("===== Actual ComfyUI server log (tail) =====", file=sys.stderr)
        print(tail, file=sys.stderr)
        raise
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        shutil.rmtree(profile_dir, ignore_errors=True)
        fake.shutdown()
        fake.server_close()
        fake_thread.join(timeout=5)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: comfyui_server_smoke.py /path/to/real/ComfyUI")
    run(Path(sys.argv[1]).resolve())
