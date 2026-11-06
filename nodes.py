from __future__ import annotations

import io

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


class GPTImageBridgeAPIProvider:
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
        encoded_references = encode_reference_slots(
            *direct_values,
            start_slot=1,
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
            references=_validate_references(
                references,
                queue_name="Edit Reference List (Image 2–9)",
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
