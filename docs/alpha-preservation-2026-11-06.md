# Alpha preservation follow-up (2026-11-06)

## Scope

This follow-up fixes the plugin-side image decode boundary discovered in the Main 0.7.0 acceptance run. It does not claim that the live Codex image service now generates transparent pixels when asked.

Baseline: `main@f8773d5df5d94feb0c11efb80d174cf55cbdc141`

Implementation PR: [#5 Preserve alpha in generated image tensors](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/pull/5)

## Root cause

Before this change, `gpt_image_bridge/images.py::image_bytes_to_tensor` unconditionally called `image.convert("RGB")`. Any alpha channel or palette transparency in a valid PNG/WebP was discarded before the ComfyUI `IMAGE` tensor was returned.

ComfyUI itself does not require this conversion. Its image conversion helper chooses RGBA when the source has an alpha band or palette transparency, and its unit tests assert that a fully transparent RGBA PNG remains four-channel. The pinned ComfyUI 0.44.0 `SaveImage` implementation constructs a PIL image directly from the tensor array; four-channel arrays are saved as RGBA PNG.

## Changes

- Detect explicit alpha bands and palette transparency before decoding.
- Preserve RGBA pixels in the returned ComfyUI tensor.
- When a batch mixes RGB and RGBA results, promote the batch to RGBA and give RGB frames an opaque alpha channel. This keeps the batch stackable without inventing transparency.
- Remove the strict XFAIL and add tests for RGBA PNG, palette transparency, and mixed RGB/RGBA batches.
- Extend the actual ComfyUI CPU smoke test: the fake upstream returns a half-transparent RGBA PNG, and the real ComfyUI `SaveImage` output is checked for RGBA mode and alpha extrema `(0, 255)`.

## Verification

PR #5 exact HEAD: `b0d47579ba7f98b03db43260633d346d43b5674a`.

- Python: **294 passed, 0 xfailed**.
- JavaScript: **14 passed, 0 failed**.
- Real ComfyUI 0.44.0 CPU server + fake CLIProxyAPI: **PASS**. All six plugin nodes registered; generated/editing graphs executed; the RGBA output passed through the plugin tensor and ComfyUI `SaveImage` without losing alpha.
- [Python/JavaScript CI](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/actions/runs/42220463919)
- [Real ComfyUI integration CI](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/actions/runs/42220463982)

## Remaining upstream limitation

The earlier live acceptance case `transparent_png` sent `background=transparent` through CLIProxyAPI 8.0.57, but the real service returned a PNG decoded as RGB at 1536×1024; the evidence had no alpha extrema. Therefore:

- The plugin now preserves alpha **if the upstream response contains it**.
- The actual Codex/CLIProxyAPI live path still needs a successful transparent RGBA response before transparent generation can be marked PASS.
- This local fix does not synthesize an alpha mask from an opaque image.

## Separate format and size boundaries

The `IMAGE` output is a pixel tensor, not the original encoded file. The default ComfyUI `SaveImage` writes PNG. In the pinned ComfyUI source, `SaveImageAdvanced` exposes PNG, EXR and AVIF; AVIF's encoder explicitly rejects four-channel alpha. The Codex image-generation extension's request model has a GIF output override and otherwise stores the returned PNG/GIF bytes directly; it does not expose a general JPEG/WebP output selection.

The plugin's API `output_format` control and the local file encoder therefore remain separate concerns. The live CLIProxyAPI 8.0.57 tests still returned PNG 1536×1024 for JPEG/WebP, Custom, 2K and 4K requests. CLIProxyAPI forwards those request fields and passes the returned image payload through; this repository must not pretend it can force the upstream model to render a requested native size or format. A local JPEG/WebP saver can be added as a separate ComfyUI node if desired, but that would re-encode the tensor rather than preserve the upstream response bytes.
