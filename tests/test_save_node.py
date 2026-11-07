from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from PIL import Image

PROJECT = Path(__file__).resolve().parents[1]


def import_comfy_package():
    package_name = "comfyui_gpt_image_bridge_save_test_package"
    spec = importlib.util.spec_from_file_location(
        package_name,
        PROJECT / "__init__.py",
        submodule_search_locations=[str(PROJECT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def install_folder_paths_stub(monkeypatch, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    def get_save_image_path(prefix, root, width, height):
        normalized = os.path.normpath(prefix)
        subfolder = os.path.dirname(normalized)
        filename = os.path.basename(normalized)
        full_folder = Path(root) / subfolder
        full_folder.mkdir(parents=True, exist_ok=True)
        counters = []
        pattern = re.compile(re.escape(filename) + r"_(\d+)_\.")
        for item in full_folder.iterdir():
            match = pattern.match(item.name)
            if item.is_file() and match:
                counters.append(int(match.group(1)))
        return str(full_folder), filename, max(counters, default=0) + 1, subfolder, normalized

    monkeypatch.setitem(
        sys.modules,
        "folder_paths",
        SimpleNamespace(
            get_output_directory=lambda: str(output_dir),
            get_save_image_path=get_save_image_path,
        ),
    )


def saver_node():
    module = import_comfy_package()
    return module.NODE_CLASS_MAPPINGS["GPTImageBridgeSaveImage"]()


def test_saver_is_registered_as_a_comfyui_output_node():
    module = import_comfy_package()
    node = module.NODE_CLASS_MAPPINGS["GPTImageBridgeSaveImage"]
    assert module.NODE_DISPLAY_NAME_MAPPINGS["GPTImageBridgeSaveImage"] == (
        "GPT Image Bridge · Export JPEG/WebP (optional)"
    )
    assert node.OUTPUT_NODE is True
    assert node.RETURN_TYPES == ("IMAGE",)
    assert node.INPUT_TYPES()["required"]["file_format"][0] == (
        "png",
        "jpeg",
        "webp",
    )


def test_png_batch_preserves_rgba_and_uses_comfyui_output_folder(tmp_path, monkeypatch):
    install_folder_paths_stub(monkeypatch, tmp_path / "output")
    images = torch.tensor(
        [
            [[[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 1.0]]],
            [[[0.0, 0.0, 1.0, 0.5], [1.0, 1.0, 0.0, 1.0]]],
        ],
        dtype=torch.float32,
    )

    result = saver_node().save_images(
        images,
        file_format="png",
        filename_prefix="bridge/png",
        png_compress_level=9,
    )

    assert result["result"][0] is images
    saved = result["ui"]["images"]
    assert [item["filename"] for item in saved] == [
        "png_00001_.png",
        "png_00002_.png",
    ]
    assert all(item["subfolder"] == "bridge" and item["type"] == "output" for item in saved)
    with Image.open(tmp_path / "output/bridge/png_00001_.png") as image:
        assert image.mode == "RGBA"
        assert [image.getchannel("A").getpixel((0, 0)), image.getchannel("A").getpixel((1, 0))] == [0, 255]
    with Image.open(tmp_path / "output/bridge/png_00002_.png") as image:
        assert image.mode == "RGBA"
        assert [image.getchannel("A").getpixel((0, 0)), image.getchannel("A").getpixel((1, 0))] == [127, 255]


def test_webp_lossless_keeps_alpha_and_batch_outputs(tmp_path, monkeypatch):
    if Image.registered_extensions().get(".webp") != "WEBP":
        pytest.skip("Pillow was built without WebP support")
    install_folder_paths_stub(monkeypatch, tmp_path / "output")
    images = torch.tensor(
        [
            [[[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 1.0]]],
            [[[0.0, 0.0, 1.0, 0.5], [1.0, 1.0, 0.0, 1.0]]],
        ],
        dtype=torch.float32,
    )

    result = saver_node().save_images(
        images,
        file_format="webp",
        filename_prefix="bridge/webp",
        quality=100,
        webp_lossless=True,
    )

    assert [item["filename"] for item in result["ui"]["images"]] == [
        "webp_00001_.webp",
        "webp_00002_.webp",
    ]
    with Image.open(tmp_path / "output/bridge/webp_00001_.webp") as image:
        assert image.mode == "RGBA"
        assert [image.getchannel("A").getpixel((0, 0)), image.getchannel("A").getpixel((1, 0))] == [0, 255]
    with Image.open(tmp_path / "output/bridge/webp_00002_.webp") as image:
        assert image.mode == "RGBA"
        assert [image.getchannel("A").getpixel((0, 0)), image.getchannel("A").getpixel((1, 0))] == [127, 255]


def test_jpeg_composites_alpha_over_selected_background(tmp_path, monkeypatch):
    install_folder_paths_stub(monkeypatch, tmp_path / "output")
    images = torch.zeros((1, 16, 32, 4), dtype=torch.float32)
    images[:, :, :, 0] = 1.0
    images[:, :, 16:, 3] = 1.0

    result = saver_node().save_images(
        images,
        file_format="jpeg",
        filename_prefix="jpeg",
        quality=100,
        jpeg_background="#0000FF",
    )

    path = tmp_path / "output/jpeg_00001_.jpg"
    assert result["ui"]["images"][0]["filename"] == path.name
    with Image.open(path) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        pixels = np.asarray(image)
        assert np.allclose(pixels[8, 4], [0, 0, 255], atol=8)
        assert np.allclose(pixels[8, 27], [255, 0, 0], atol=8)


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"file_format": "tiff"}, "file_format"),
        ({"quality": 0}, "quality"),
        ({"png_compress_level": 10}, "png_compress_level"),
        ({"file_format": "jpeg", "jpeg_background": "white"}, "six-digit hex"),
    ],
)
def test_saver_rejects_invalid_options(tmp_path, monkeypatch, kwargs, match):
    install_folder_paths_stub(monkeypatch, tmp_path / "output")
    images = torch.zeros((1, 2, 2, 3), dtype=torch.float32)
    with pytest.raises(ValueError, match=match):
        saver_node().save_images(images, **kwargs)


def test_saver_rejects_non_finite_or_invalid_image_tensor(tmp_path, monkeypatch):
    install_folder_paths_stub(monkeypatch, tmp_path / "output")
    node = saver_node()
    with pytest.raises(ValueError, match="NaN or infinite"):
        node.save_images(torch.full((1, 2, 2, 3), float("nan")))
    with pytest.raises(ValueError, match="RGB or RGBA"):
        node.save_images(torch.zeros((1, 2, 2, 2)))
