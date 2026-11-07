from __future__ import annotations

import io
import os
import re

import numpy as np
from PIL import Image

if __package__:
    from .gpt_image_bridge.config import (
        API_PROTOCOLS,
        OAUTH_PROTOCOLS,
        ProviderConfig,
    )
    from .gpt_image_bridge.errors import report_json
    from .gpt_image_bridge.images import (
        EncodedImage,
        encode_reference_slots,
        image_bytes_to_tensor,
        mask_to_png,
        tensor_to_png,
    )
    from .gpt_image_bridge.protocols import execute_operation
    from .gpt_image_bridge.provider_profiles import build_profile_provider, profile_names, profile_fingerprint
else:
    from gpt_image_bridge.config import (
        API_PROTOCOLS,
        OAUTH_PROTOCOLS,
        ProviderConfig,
    )
    from gpt_image_bridge.errors import report_json
    from gpt_image_bridge.images import (
        EncodedImage,
        encode_reference_slots,
        image_bytes_to_tensor,
        mask_to_png,
        tensor_to_png,
    )
    from gpt_image_bridge.protocols import execute_operation
    from gpt_image_bridge.provider_profiles import build_profile_provider, profile_names, profile_fingerprint


CATEGORY = "GPT Image Bridge"
SIZE_VALUES = (
    "auto",
    "1024x1024",
    "1536x1024",
    "1024x1536",
    "2048x2048",
    "2048x1152",
    "1152x2048",
    "3840x2160",
    "2160x3840",
    "Custom",
)
QUALITY_VALUES = ("auto", "low", "medium", "high", "xhigh", "max")
BACKGROUND_VALUES = ("auto", "opaque", "transparent")
OUTPUT_FORMAT_VALUES = ("png", "jpeg", "webp")
MODERATION_VALUES = ("auto", "low")
COMPLEXITY_VALUES = ("auto", "low", "medium", "high")
REFERENCE_GENERATE_MODES = ("images_edit", "responses")
BASE_IMAGE_INPUT_NAME = "base_image（Image 1）"
EDIT_REFERENCES_INPUT_NAME = "references（Image 2 开始）"
REFERENCE_IMAGE_INPUT_NAMES = tuple(f"image_{index}" for index in range(2, 17))
GENERATE_REFERENCE_INPUT_NAMES = tuple(
    f"reference_{index}" for index in range(1, 17)
)


class GPTImageBridgeProviderProfile:
    """Recommended, key-free canvas provider backed by local service profiles."""

    RETURN_TYPES = ("GPT_IMAGE_PROVIDER",)
    RETURN_NAMES = ("provider",)
    FUNCTION = "build"
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "Choose a locally configured image service. Base URL and API Key "
        "are kept in providers.local.json, outside shareable ComfyUI workflows."
    )

    @classmethod
    def INPUT_TYPES(cls):
        names = profile_names()
        return {
            "required": {
                "profile": (names, {"default": names[0]}),
            },
            "optional": {
                "image_model": ("STRING", {
                    "default": "", "multiline": False,
                    "tooltip": "Optional override. Leave blank to use the profile's default image model.",
                }),
                "reference_mode": (
                    ("profile", "images_edit", "responses"),
                    {"default": "profile", "tooltip": "Use the profile default or override reference-guided generation."},
                ),
                "responses_model": ("STRING", {
                    "default": "", "multiline": False,
                    "tooltip": "Optional Responses host model override; no effect on standard Images calls.",
                }),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **_kwargs):
        return profile_fingerprint()

    def build(self, profile, image_model="", reference_mode="profile", responses_model=""):
        return (build_profile_provider(
            profile,
            image_model=image_model,
            reference_mode=reference_mode,
            responses_model=responses_model,
        ),)


class GPTImageBridgeAPIProvider:
    DEPRECATED = True
    DEV_ONLY = True
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": (
                    "STRING",
                    {"default": "", "multiline": False, "socketless": True},
                ),
                "base_url": ("STRING", {"default": "", "multiline": False}),
                "model": ("STRING", {"default": "", "multiline": False}),
                "api_protocol": (API_PROTOCOLS, {"default": "auto"}),
            },
            "optional": {
                "use_custom_endpoints": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "socketless": True,
                        "label": "使用自定义端点",
                        "tooltip": (
                            "关闭时忽略所有自定义同步/异步端点和响应映射，"
                            "使用所选协议的标准路径与标准响应格式。"
                        ),
                    },
                ),
                "generate_endpoint": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "label": "自定义生成端点",
                        "tooltip": (
                            "仅在“使用自定义端点”开启时生效。填写同步端点；"
                            "异步开关会按标准 Images 路径派生异步端点。"
                        ),
                    },
                ),
                "edit_endpoint": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "label": "自定义编辑端点",
                        "tooltip": (
                            "仅在“使用自定义端点”开启时生效。填写同步端点；"
                            "异步开关会按标准 Images 路径派生异步端点。"
                        ),
                    },
                ),
                "use_async": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "socketless": True,
                        "label": "使用异步",
                        "tooltip": (
                            "优先使用 Images 异步任务端点；仅在服务明确表示不支持时"
                            "安全回退同步。"
                        ),
                    },
                ),
                "async_generate_endpoint": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "label": "自定义异步生成提交端点",
                        "tooltip": (
                            "可选。开启自定义端点和异步后生效；填写供应商真实的"
                            "异步生成 POST 端点，留空时按标准 Images 路径派生。"
                        ),
                    },
                ),
                "async_edit_endpoint": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "label": "自定义异步编辑提交端点",
                        "tooltip": (
                            "可选。开启自定义端点和异步后生效；填写供应商真实的"
                            "异步编辑 POST 端点，留空时按标准 Images 路径派生。"
                        ),
                    },
                ),
                "async_poll_endpoint_template": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "label": "自定义异步查询端点模板",
                        "tooltip": (
                            "可选。必须恰好包含一个 {task_id}，例如 "
                            "jobs/{task_id} 或 jobs?id={task_id}；轮询固定使用 GET。"
                        ),
                    },
                ),
                "async_mapping_json": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "label": "自定义异步 JSON 映射",
                        "tooltip": (
                            "可选。使用受限 RFC 6901 JSON Pointer 映射任务 ID、"
                            "状态、结果和图片字段；不支持脚本或 JSONPath。"
                        ),
                    },
                ),
            }
        }

    RETURN_TYPES = ("GPT_IMAGE_PROVIDER",)
    RETURN_NAMES = ("provider",)
    FUNCTION = "build"
    CATEGORY = CATEGORY

    def build(
        self,
        api_key,
        base_url,
        model,
        api_protocol,
        generate_endpoint="",
        edit_endpoint="",
        use_custom_endpoints=None,
        use_async=True,
        async_generate_endpoint="",
        async_edit_endpoint="",
        async_poll_endpoint_template="",
        async_mapping_json="",
    ):
        provider = ProviderConfig.from_api_inputs(
            api_key=api_key,
            base_url=base_url,
            model=model,
            api_protocol=api_protocol,
            use_custom_endpoints=use_custom_endpoints,
            use_async=use_async,
            generate_endpoint=generate_endpoint,
            edit_endpoint=edit_endpoint,
            async_generate_endpoint=async_generate_endpoint,
            async_edit_endpoint=async_edit_endpoint,
            async_poll_endpoint_template=async_poll_endpoint_template,
            async_mapping_json=async_mapping_json,
            require_session_handle=True,
        )
        return (provider,)


class GPTImageBridgeCLIProxyAPIProvider:
    DEPRECATED = True
    DEV_ONLY = True
    """Provider preset for a local or remote CLIProxyAPI OpenAI-compatible server."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "socketless": True,
                        "tooltip": (
                            "CLIProxyAPI config.yaml 中 access.api-keys 的客户端密钥；"
                            "不是上游 Codex OAuth Token。"
                        ),
                    },
                ),
                "base_url": (
                    "STRING",
                    {
                        "default": "http://127.0.0.1:8317/v1",
                        "multiline": False,
                        "label": "CLIProxyAPI Base URL",
                    },
                ),
                "image_model": (
                    "STRING",
                    {
                        "default": "gpt-image-2.6-flare",
                        "multiline": False,
                        "label": "图像模型",
                        "tooltip": (
                            "OpenAI 正式型号: gpt-image-2.6-flare (快速) / "
                            "gpt-image-2.6-sunburst (精细)。"
                            "模型须在当前 CLIProxyAPI 账号上可用；旧 gpt-image-2 仍可填写。"
                        ),
                    },
                ),
                "responses_model": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "label": "Responses 主模型",
                        "tooltip": (
                            "仅在参考图模式选择 responses 时填写真实可用的文本主模型。"
                            "否则无需填写，不参与 Images 生图。"
                        ),
                    },
                ),
            },
            "optional": {
                "reference_mode": (
                    REFERENCE_GENERATE_MODES,
                    {
                        "default": "images_edit",
                        "label": "参考图生成模式",
                        "tooltip": (
                            "images_edit（默认）：用首张参考图作为 Images Edit 输入，"
                            "生成新图；不是从零无参生图。"
                            "responses：调用文本主模型的 image_generation 工具。"
                        ),
                    },
                ),
                "image_complexity": (
                    COMPLEXITY_VALUES,
                    {
                        "default": "auto",
                        "label": "图像规划复杂度",
                        "tooltip": (
                            "OpenAI Images API 的 2.6 支持 low / medium / high。"
                            "但 CLIProxyAPI 8.0.57 的 Codex Images 转换器不会转发 complexity；"
                            "默认 Images 路径下此控件暂不生效。"
                            "auto 不发送字段；与渲染质量 quality 不同。"
                        ),
                    },
                ),
            },
        }

    RETURN_TYPES = ("GPT_IMAGE_PROVIDER",)
    RETURN_NAMES = ("provider",)
    FUNCTION = "build"
    CATEGORY = CATEGORY

    def build(
        self,
        api_key,
        base_url,
        image_model,
        responses_model,
        reference_mode="images_edit",
        image_complexity="auto",
    ):
        provider = ProviderConfig.from_api_inputs(
            api_key=api_key,
            base_url=base_url,
            model=image_model,
            responses_model=responses_model,
            reference_generate_mode=reference_mode,
            image_complexity=image_complexity,
            api_protocol="auto",
            use_custom_endpoints=False,
            use_async=False,
            require_session_handle=True,
        )
        return (provider,)


class GPTImageBridgeOAuthProvider:
    DEPRECATED = True
    DEV_ONLY = True
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("STRING", {"default": "gpt-image-2"}),
                "api_protocol": (OAUTH_PROTOCOLS, {"default": "auto"}),
            }
        }

    RETURN_TYPES = ("GPT_IMAGE_PROVIDER",)
    RETURN_NAMES = ("provider",)
    FUNCTION = "build"
    CATEGORY = CATEGORY

    def build(self, model, api_protocol):
        provider = ProviderConfig.from_oauth_inputs(
            model=model,
            api_protocol=api_protocol,
        )
        return (provider,)


def _effective_image_size(size: str, custom_width: int, custom_height: int) -> str:
    """Resolve UI Custom dimensions without restricting free-form model aliases.

    ComfyUI's official GPT Image 2.6 node accepts dimensions in multiples of
    16, bounded by size, aspect ratio and total pixel count. Apply the same
    checks before requests so invalid dimensions do not consume remote quota.
    """
    if size != "Custom":
        return size
    width, height = int(custom_width), int(custom_height)
    if not 480 <= width <= 3840 or not 480 <= height <= 3840:
        raise ValueError("Custom width and height must be between 480 and 3840.")
    if width % 16 or height % 16:
        raise ValueError("Custom width and height must be multiples of 16.")
    if max(width, height) / min(width, height) > 3:
        raise ValueError("Custom aspect ratio must be no greater than 3:1.")
    if not 655_360 <= width * height <= 8_294_400:
        raise ValueError("Custom image must be between 655,360 and 8,294,400 pixels.")
    return f"{width}x{height}"


def _ordered_single_image_slots(
    kwargs,
    names: tuple[str, ...],
    *,
    queue_name: str,
):
    values = [kwargs.get(name) for name in names]
    connected = [index for index, value in enumerate(values) if value is not None]
    if not connected:
        return []
    last_connected = connected[-1]
    for index in range(last_connected + 1):
        if values[index] is None:
            raise ValueError(
                f"{queue_name} inputs must be connected without gaps: "
                f"connect {names[index]} before {names[last_connected]}."
            )
    for index, value in enumerate(values[: last_connected + 1]):
        ndim = int(value.ndim)
        frame_count = int(value.shape[0]) if ndim == 4 else 1
        if frame_count != 1:
            raise ValueError(
                f"{names[index]} accepts exactly one IMAGE. Use the next numbered "
                f"{queue_name} input instead of an IMAGE batch."
            )
    return values[: last_connected + 1]


class GPTImageBridgeReferenceList:
    # Legacy: native Batch Images now handles common same-sized reference sets.
    # Keep registered for historical workflows and mixed-size reference inputs.
    DEPRECATED = True
    DEV_ONLY = True
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                name: ("IMAGE",)
                for name in REFERENCE_IMAGE_INPUT_NAMES
            }
        }

    RETURN_TYPES = ("GPT_IMAGE_REFERENCES",)
    RETURN_NAMES = ("references",)
    FUNCTION = "collect"
    CATEGORY = CATEGORY

    def collect(self, **kwargs):
        if kwargs.get("image_1") is not None:
            legacy_names = tuple(f"image_{index}" for index in range(1, 9))
            ordered_slots = _ordered_single_image_slots(
                kwargs,
                legacy_names,
                queue_name="Edit Reference List",
            )
        else:
            ordered_slots = _ordered_single_image_slots(
                kwargs,
                REFERENCE_IMAGE_INPUT_NAMES,
                queue_name="Edit Reference List",
            )
        return (encode_reference_slots(*ordered_slots, start_slot=2),)


def _validate_references(
    value,
    *,
    queue_name: str,
) -> tuple[EncodedImage, ...]:
    if value is None:
        return ()
    references = tuple(value)
    if not all(isinstance(item, EncodedImage) for item in references):
        raise ValueError(
            f"references must come from GPT Image Bridge · {queue_name}."
        )
    return references


def _native_reference_batch(batch, *, start_slot: int, limit: int) -> tuple[EncodedImage, ...]:
    """Translate ComfyUI's standard IMAGE batch into ordered API references.

    Batch Images may resize unequal-sized inputs before they reach us; that is
    ComfyUI's composition behavior, not a bridge-side image transformation.
    """
    refs = encode_reference_slots(batch, start_slot=start_slot)
    if not refs:
        raise ValueError("reference_batch must contain at least one IMAGE frame.")
    if len(refs) > limit:
        raise ValueError(f"reference_batch accepts at most {limit} reference images.")
    return refs


def _run_and_convert(**kwargs):
    result = execute_operation(**kwargs)
    return (
        image_bytes_to_tensor(result.images),
        result.revised_prompt,
        report_json(result.report),
    )


class GPTImageBridgeGenerate:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "provider": ("GPT_IMAGE_PROVIDER",),
                "prompt": ("STRING", {"multiline": True, "default": "A cinematic image"}),
                "size": (SIZE_VALUES, {"default": "auto"}),
                "quality": (QUALITY_VALUES, {"default": "auto"}),
                "background": (BACKGROUND_VALUES, {"default": "auto"}),
                "output_format": (OUTPUT_FORMAT_VALUES, {"default": "png"}),
                "moderation": (MODERATION_VALUES, {"default": "auto"}),
                "n": ("INT", {"default": 1, "min": 1, "max": 8}),
                "timeout_sec": ("INT", {"default": 300, "min": 30, "max": 3600}),
            },
            "optional": {
                **{name: ("IMAGE",) for name in GENERATE_REFERENCE_INPUT_NAMES},
                "custom_width": ("INT", {"default": 1024, "min": 480, "max": 3840, "step": 16, "tooltip": "Used only for size=Custom."}),
                "custom_height": ("INT", {"default": 1024, "min": 480, "max": 3840, "step": 16, "tooltip": "Used only for size=Custom."}),
                "reference_batch": ("IMAGE", {"tooltip": "Connect ComfyUI Batch Images. Use instead of numbered reference inputs; original individual dimensions may be resized by the batch node."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "revised_prompt", "request_report")
    FUNCTION = "generate"
    CATEGORY = CATEGORY

    def generate(
        self,
        provider,
        prompt,
        size,
        quality,
        background,
        output_format,
        moderation,
        n,
        timeout_sec,
        reference_1=None,
        reference_2=None,
        reference_3=None,
        reference_4=None,
        reference_5=None,
        reference_6=None,
        reference_7=None,
        reference_8=None,
        reference_9=None,
        reference_10=None,
        reference_11=None,
        reference_12=None,
        reference_13=None,
        reference_14=None,
        reference_15=None,
        reference_16=None,
        custom_width=1024,
        custom_height=1024,
        reference_batch=None,
    ):
        if not isinstance(provider, ProviderConfig):
            raise ValueError("provider must come from GPT Image Bridge · Provider.")
        direct_values = _ordered_single_image_slots(
            {
                "reference_1": reference_1,
                "reference_2": reference_2,
                "reference_3": reference_3,
                "reference_4": reference_4,
                "reference_5": reference_5,
                "reference_6": reference_6,
                "reference_7": reference_7,
                "reference_8": reference_8,
                "reference_9": reference_9,
                "reference_10": reference_10,
                "reference_11": reference_11,
                "reference_12": reference_12,
                "reference_13": reference_13,
                "reference_14": reference_14,
                "reference_15": reference_15,
                "reference_16": reference_16,
            },
            GENERATE_REFERENCE_INPUT_NAMES,
            queue_name="GPT Image Generate",
        )
        if reference_batch is not None and direct_values:
            raise ValueError(
                "Use either reference_batch (native ComfyUI Batch Images) or "
                "numbered reference_1–reference_16 sockets, not both."
            )
        encoded_references = (
            _native_reference_batch(reference_batch, start_slot=1, limit=16)
            if reference_batch is not None
            else encode_reference_slots(*direct_values, start_slot=1)
        )
        return _run_and_convert(
            provider=provider,
            operation="generate",
            prompt=prompt,
            references=encoded_references,
            size=_effective_image_size(size, custom_width, custom_height),
            quality=quality,
            background=background,
            output_format=output_format,
            moderation=moderation,
            n=n,
            timeout=timeout_sec,
        )


class GPTImageBridgeEdit:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "provider": ("GPT_IMAGE_PROVIDER",),
                BASE_IMAGE_INPUT_NAME: ("IMAGE",),
                "prompt": ("STRING", {"multiline": True, "default": "Edit this image"}),
                "size": (SIZE_VALUES, {"default": "auto"}),
                "quality": (QUALITY_VALUES, {"default": "auto"}),
                "background": (BACKGROUND_VALUES, {"default": "auto"}),
                "output_format": (OUTPUT_FORMAT_VALUES, {"default": "png"}),
                "moderation": (MODERATION_VALUES, {"default": "auto"}),
                "n": ("INT", {"default": 1, "min": 1, "max": 8}),
                "timeout_sec": ("INT", {"default": 300, "min": 30, "max": 3600}),
            },
            "optional": {
                EDIT_REFERENCES_INPUT_NAME: ("GPT_IMAGE_REFERENCES",),
                "mask": ("MASK",),
                "custom_width": ("INT", {"default": 1024, "min": 480, "max": 3840, "step": 16, "tooltip": "Used only for size=Custom."}),
                "custom_height": ("INT", {"default": 1024, "min": 480, "max": 3840, "step": 16, "tooltip": "Used only for size=Custom."}),
                "reference_batch": ("IMAGE", {"tooltip": "Connect ComfyUI Batch Images for Image 2 onward. Use instead of legacy Edit Reference List; native batching may resize inputs."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "revised_prompt", "request_report")
    FUNCTION = "edit"
    CATEGORY = CATEGORY

    def edit(
        self,
        provider,
        prompt,
        size,
        quality,
        background,
        output_format,
        moderation,
        n,
        timeout_sec,
        references=None,
        mask=None,
        custom_width=1024,
        custom_height=1024,
        reference_batch=None,
        **kwargs,
    ):
        labeled_base_image = kwargs.pop(BASE_IMAGE_INPUT_NAME, None)
        legacy_base_image = kwargs.pop("base_image", None)
        labeled_references = kwargs.pop(EDIT_REFERENCES_INPUT_NAME, None)
        if kwargs:
            names = ", ".join(sorted(kwargs))
            raise ValueError(f"Unexpected GPT Image Edit inputs: {names}.")
        if labeled_base_image is not None and legacy_base_image is not None:
            raise ValueError(
                "Do not provide both base_image and base_image（Image 1）."
            )
        base_image = (
            labeled_base_image
            if labeled_base_image is not None
            else legacy_base_image
        )
        if base_image is None:
            raise ValueError("base_image（Image 1） is required.")
        if labeled_references is not None and references is not None:
            raise ValueError(
                "Do not provide both references and references（Image 2 开始）."
            )
        if labeled_references is not None:
            references = labeled_references
        if reference_batch is not None and references is not None:
            raise ValueError(
                "Use either reference_batch (native ComfyUI Batch Images) or "
                "legacy Edit Reference List, not both."
            )
        if not isinstance(provider, ProviderConfig):
            raise ValueError("provider must come from GPT Image Bridge · Provider.")
        encoded_base = tensor_to_png(base_image, source_slot=1, role="base")
        encoded_mask = mask_to_png(mask) if mask is not None else None
        if encoded_mask is not None:
            with Image.open(io.BytesIO(encoded_mask)) as mask_image:
                if mask_image.size != (encoded_base.width, encoded_base.height):
                    raise ValueError(
                        "mask dimensions must exactly match the base image dimensions."
                    )
        return _run_and_convert(
            provider=provider,
            operation="edit",
            prompt=prompt,
            base_image=encoded_base,
            references=(
                _native_reference_batch(reference_batch, start_slot=2, limit=15)
                if reference_batch is not None
                else _validate_references(
                    references,
                    queue_name="Edit Reference List (Image 2–16)",
                )
            ),
            mask_png=encoded_mask,
            size=_effective_image_size(size, custom_width, custom_height),
            quality=quality,
            background=background,
            output_format=output_format,
            moderation=moderation,
            n=n,
            timeout=timeout_sec,
        )

class GPTImageBridgeSaveImage:
    """Save a ComfyUI IMAGE batch as PNG, JPEG, or WebP in ComfyUI output."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "file_format": (("png", "jpeg", "webp"), {"default": "png"}),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "GPTImageBridge",
                        "tooltip": "Saved under the ComfyUI output directory. Subfolders and ComfyUI filename tokens are supported.",
                    },
                ),
                "quality": (
                    "INT",
                    {
                        "default": 90,
                        "min": 1,
                        "max": 100,
                        "tooltip": "JPEG/WebP quality. Ignored by PNG.",
                    },
                ),
                "png_compress_level": (
                    "INT",
                    {
                        "default": 4,
                        "min": 0,
                        "max": 9,
                        "tooltip": "PNG compression level. Higher values save space but take longer.",
                    },
                ),
                "webp_lossless": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Use lossless WebP encoding. WebP retains alpha in both modes.",
                    },
                ),
                "jpeg_background": (
                    "STRING",
                    {
                        "default": "#FFFFFF",
                        "tooltip": "Six-digit #RRGGBB matte used when JPEG input contains alpha.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "GPT Image Bridge/Output"
    DESCRIPTION = (
        "Save IMAGE batches as PNG, JPEG, or WebP in the ComfyUI output folder. "
        "PNG/WebP preserve alpha; JPEG composites alpha over a chosen matte color."
    )
    SEARCH_ALIASES = ["save", "export", "jpeg", "jpg", "webp", "png", "image output"]

    @staticmethod
    def _parse_jpeg_background(value: str) -> tuple[int, int, int]:
        if not isinstance(value, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", value) is None:
            raise ValueError("jpeg_background must be a six-digit hex color such as #FFFFFF.")
        return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))

    def save_images(
        self,
        images,
        file_format="png",
        filename_prefix="GPTImageBridge",
        quality=90,
        png_compress_level=4,
        webp_lossless=False,
        jpeg_background="#FFFFFF",
    ):
        import folder_paths

        if file_format not in ("png", "jpeg", "webp"):
            raise ValueError("file_format must be png, jpeg, or webp.")
        quality = int(quality)
        png_compress_level = int(png_compress_level)
        if not 1 <= quality <= 100:
            raise ValueError("quality must be between 1 and 100.")
        if not 0 <= png_compress_level <= 9:
            raise ValueError("png_compress_level must be between 0 and 9.")
        if not isinstance(filename_prefix, str) or not filename_prefix.strip():
            raise ValueError("filename_prefix must not be empty.")

        background = (
            self._parse_jpeg_background(jpeg_background)
            if file_format == "jpeg"
            else None
        )
        if file_format == "webp" and Image.registered_extensions().get(".webp") != "WEBP":
            raise RuntimeError(
                "This ComfyUI Python environment's Pillow build does not support WebP encoding."
            )

        if not hasattr(images, "detach") or not hasattr(images, "shape"):
            raise ValueError("images must be a ComfyUI IMAGE tensor.")
        batch = images.detach().cpu().float().numpy()
        if batch.ndim != 4 or batch.shape[0] < 1:
            raise ValueError("images must have shape [batch, height, width, channels].")
        height, width, channels = batch.shape[1:]
        if height < 1 or width < 1 or channels not in (3, 4):
            raise ValueError("images must contain non-empty RGB or RGBA frames.")
        if not np.isfinite(batch).all():
            raise ValueError("images contains NaN or infinite pixel values.")

        output_dir = folder_paths.get_output_directory()
        full_output_folder, filename, counter, subfolder, _ = (
            folder_paths.get_save_image_path(
                filename_prefix,
                output_dir,
                width,
                height,
            )
        )
        os.makedirs(full_output_folder, exist_ok=True)

        extension = {"png": "png", "jpeg": "jpg", "webp": "webp"}[file_format]
        encoder = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}[file_format]
        results = []
        for batch_number, frame in enumerate(batch):
            pixels = np.clip(frame * 255.0, 0, 255).astype(np.uint8)
            image = Image.fromarray(pixels)

            if file_format == "jpeg":
                if image.mode == "RGBA":
                    matte = Image.new("RGBA", image.size, (*background, 255))
                    image = Image.alpha_composite(matte, image).convert("RGB")
                else:
                    image = image.convert("RGB")

            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch_num}_{counter:05}_.{extension}"
            destination = os.path.join(full_output_folder, file)

            if file_format == "png":
                image.save(destination, format=encoder, compress_level=png_compress_level)
            elif file_format == "jpeg":
                image.save(destination, format=encoder, quality=quality, optimize=True)
            else:
                image.save(
                    destination,
                    format=encoder,
                    quality=quality,
                    lossless=bool(webp_lossless),
                    method=4,
                )

            results.append(
                {
                    "filename": file,
                    "subfolder": subfolder,
                    "type": "output",
                }
            )
            counter += 1

        return {"ui": {"images": results}, "result": (images,)}

