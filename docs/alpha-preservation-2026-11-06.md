# Alpha preservation follow-up (2026-11-06)

## Scope

This follow-up fixes the plugin-side image decode boundary discovered in the Main 0.7.0 acceptance run. A subsequent real-service retest below returned transparent pixels; this is one observed result, not an upstream guarantee.

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

Code verification HEAD: `b0d47579ba7f98b03db43260633d346d43b5674a` (the later PR #5 commits only updated documentation).

- Python: **294 passed, 0 xfailed**.
- JavaScript: **14 passed, 0 failed**.
- Real ComfyUI 0.44.0 CPU server + fake CLIProxyAPI: **PASS**. All six plugin nodes registered; generated/editing graphs executed; the RGBA output passed through the plugin tensor and ComfyUI `SaveImage` without losing alpha.
- [Python/JavaScript CI](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/actions/runs/42220463919)
- [Real ComfyUI integration CI](https://github.com/Fuck-GH-Admin/comfyui-gpt-image-bridge/actions/runs/42220463982)

## Real-service retest after PR #5

At `main@abfacd3`, the same `transparent_png` case was queued once against the real CLIProxyAPI 8.0.57 / Codex service, without automatic retries. Unlike the earlier pre-fix RGB result, this response passed through the plugin and actual ComfyUI `SaveImage` as **RGBA PNG, 1536×1024, alpha extrema `(0, 254)`**. No alpha was synthesized locally. **This case is now PASS.**

- Request: `gpt-image-2.6-flare`, `background=transparent`, `quality=low`, `n=1`.
- Prompt ID: `32123eac-4c04-4fa7-a281-cf97bb89348f`; elapsed: 30.05 seconds.
- Saved PNG SHA-256: `630d3f1d288623934def60e5bbd5a507a237f01d3a3bb3586970c7bc2e5d3f96`.
- [Sanitized request report and pixel evidence](evidence/live-alpha-retest-2026-11-06.json); raw credentials were absent from history and PNG metadata.
- Local regression rerun: Python **294 passed**, JavaScript **14 passed**; real ComfyUI + simulated upstream **PASS**, including `(0, 255)` RGBA round-trip.

This single real success does not establish reliable transparency for every prompt, model or account. The earlier RGB observation remains valid historical evidence. The plugin preserves alpha when returned by upstream; it does not force upstream transparency. Size/format and Responses/Chat failures from the earlier matrix were not reclassified or re-tested here.

Reproduce with the existing runner (one potentially billable request):

```bash
python tools/real_acceptance_matrix.py --case transparent_png \
  --comfy-root /path/to/ComfyUI \
  --proxy-config /path/to/cliproxyapi/config.yaml \
  --output-dir /path/to/acceptance-evidence
```

## Separate format and size boundaries

The `IMAGE` output is a pixel tensor, not the original encoded file. The default ComfyUI `SaveImage` writes PNG. In the pinned ComfyUI source, `SaveImageAdvanced` exposes PNG, EXR and AVIF; AVIF's encoder explicitly rejects four-channel alpha. The Codex image-generation extension's request model has a GIF output override and otherwise stores the returned PNG/GIF bytes directly; it does not expose a general JPEG/WebP output selection.

The plugin's API `output_format` control and the local file encoder therefore remain separate concerns. The live CLIProxyAPI 8.0.57 tests still returned PNG 1536×1024 for JPEG/WebP, Custom, 2K and 4K requests. CLIProxyAPI forwards those request fields and passes the returned image payload through; this repository must not pretend it can force the upstream model to render a requested native size or format. A local JPEG/WebP saver can be added as a separate ComfyUI node if desired, but that would re-encode the tensor rather than preserve the upstream response bytes.
