# Native node contracts

`LTXVFXStudio` prepares real ComfyUI tensors and a patched model. It is not a sampler or an output node. Connect its outputs to the matching LTX sampling workflow, remove the IC guide tokens with `LTXVFXCropGuides`, then decode and save. The Studio UI edits ordinary serialized node widgets; the backend also works when a workflow is submitted through Comfy API without opening the UI.

| Node | Required sockets | Outputs |
| --- | --- | --- |
| `LTXVFXStudio` | MODEL `model`, CLIP `clip`, VAE `vae`, IMAGE `source` | MODEL, positive CONDITIONING, negative CONDITIONING, LATENT, JSON STRING `recipe` |
| `LTXVFXApplyEffect` | MODEL `model` | MODEL, JSON STRING `effect_info` |
| `LTXVFXCropGuides` | positive CONDITIONING, negative CONDITIONING, LATENT | positive CONDITIONING, negative CONDITIONING, LATENT |
| `LTXAPIGenerate` | No model sockets; text controls, optional IMAGE `image` | VIDEO, STRING `job_id` |

`LTXAPIGenerate` is a separate, opt-in hosted route. It does not use the Studio's LoRA library. See [LTX API setup and recovery](LTX-API.md). Its API key stays in the server environment and `allow_api_requests` defaults to false.

Studio widgets are `effect`, `prompt`, `negative_prompt`, `strength`, `guide_strength`, `width`, `height`, `frames`, and `frame_rate`. Layout to render additionally needs the optional IMAGE socket `first_frame`. Display names and stable catalog IDs both resolve in Python; the frontend combo serializes display names.

- Video effects trim source frames to the requested `8n+1` length. They reject a short input; there is no silent looping, padding, or frame-rate conversion. Resample the source to the requested fps in the video loader.
- Pixel upscaling supplies the catalog's reference downscale factor of 2 to the native guide node. Its output dimensions must be multiples of 64.
- Ingredients accepts one composite sheet and repeats it into a static reference clip of at least 121 frames.
- Cinemagraph uses native image-to-video conditioning and ensures the documented trigger is present. Alpha matte always encodes an empty positive prompt, returns grayscale matte imagery, and enforces the documented maximum frame count and dimensions.
- Layout takes both a layout video and an art-directed still. It prepares a half-resolution first-stage latent, adds the still at temporal position -1, and records the final and first-stage dimensions in `recipe`. The official second stage must upscale, reattach the appropriate guides, and sample with the adapter active again.
- Restore and Refine details prepare temporal guides using 97-frame streaming windows. Their spatial tile settings and dedicated tiled sampler remain the responsibility of the connected official workflow. The recipe includes those requirements.
- SDR to HDR and Slow motion do not go through Studio's generic preparation path. Their dedicated workflows carry essential color, embedding, seam-keyframe, or dual-fps logic. Use the UI's official workflow action. `LTXVFXApplyEffect` remains available as an adapter selector within those workflows.

## Verified upstream interfaces

Verified October 23, 2026 against ComfyUI `8baf68d53d751216dd95d4f678bf109d82db3442` and ComfyUI-LTXVideo `220e1d45aa0469f518e982102fca4dca92a61862`:

- [Lightricks `LTXAddVideoICLoRAGuide`](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/220e1d45aa0469f518e982102fca4dca92a61862/iclora.py): synchronous `execute(positive, negative, vae, latent, image, frame_idx, strength, latent_downscale_factor, crop, use_tiled_encode, tile_size, tile_overlap, use_streaming=False, tile_frames=0)`.
- [ComfyUI core LTX nodes](https://github.com/Comfy-Org/ComfyUI/blob/8baf68d53d751216dd95d4f678bf109d82db3442/comfy_extras/nodes_lt.py): `EmptyLTXVLatentVideo`, `LTXVImgToVideo`, `LTXVConditioning`, `LTXVCropGuides` use synchronous `execute` and return `io.NodeOutput`.
- [ComfyUI model and text nodes](https://github.com/Comfy-Org/ComfyUI/blob/8baf68d53d751216dd95d4f678bf109d82db3442/nodes.py): `LoraLoaderModelOnly.load_lora_model_only` and `CLIPTextEncode.encode` use the V1 `FUNCTION` contract and return tuples.
- [ComfyUI `io.NodeOutput`](https://github.com/Comfy-Org/ComfyUI/blob/8baf68d53d751216dd95d4f678bf109d82db3442/comfy_api/latest/_io.py) exposes result values through `.result`; V3 `FUNCTION` dispatches through `EXECUTE_NORMALIZED`.

The small runtime adapter dispatches the declared `FUNCTION`, or `execute` for V3, and unwraps tuple, V1 result dictionaries and V3 NodeOutput. It rejects an unexpected asynchronous native implementation explicitly. Missing native nodes produce an update/install message rather than substituted or simulated output.

## Verification boundary

`python -m unittest discover -s tests -v` exercises native-call contracts with lightweight doubles, catalog selection, special pipeline guards, frame and size validation, source requirements, reference conditioning, and optional/idempotent route registration. These checks require neither torch nor a GPU.

The separate live integration check uses an installed ComfyUI and ComfyUI-LTXVideo:

```bash
/path/to/comfy/python tests/comfy_integration.py --comfy-root /path/to/ComfyUI
```

This passed on the revisions above with Python 3.12 and PyTorch 2.14.1 on CPU. It loaded the actual packs through ComfyUI, exercised real native tensor preparation and guide cropping for all 13 supported preparation paths, and checked both dedicated-workflow guards. Restore and Refine details exercised multiple temporal windows; Layout exercised half-resolution conditioning. All 14 Cinemagraph starter nodes passed the installed schemas and link-type checks. The native CreateVideo → SaveVideo path produced a three-frame 64×64 MP4 that PyAV successfully decoded.

The added hosted node also registered in actual ComfyUI. Both hosted starter graphs passed their native schemas and link types (two nodes for text, three for image). A real CPU image tensor encoded to the expected inline PNG format. Its real `VideoFromFile` wrapper was connected to native SaveVideo and produced a decodable MP4 from a local synthetic file. The API transport was replaced for this check: it made no LTX request and used no API key. Separate unit tests exercise opt-in, request payloads, authentication boundaries, saved job recovery, cancellation, and bounded downloads with fake transports.

The machine-readable [integration result](comfy-integration-result.json) records those versions and outcomes.

## Browser integration

The live ComfyUI 0.42.0 interface (frontend 1.57.1, CPU/offline mode) was also tested:

- **Extensions → OpenPositive** opened the Studio inside ComfyUI and loaded all 15 catalog entries.
- Selecting Cinemagraph, editing its prompt, and applying it created an actual `LTXVFXStudio` node with 512×704 output, 25 frames and 24 fps.
- Reopening the Studio from that node restored its edited prompt and controls.
- Exporting the graph in API format preserved the selected effect, edited prompt and numeric settings. This was a state-persistence check on a preparation node; it was not an inference run.
- The bridge supports nodes inside subgraphs, rejects changes to controls supplied by connected nodes, and preserves same-origin reverse-proxy paths. Unit tests cover these additional cases.

The studio fonts are bundled locally for offline mode. [Studio inside ComfyUI](comfyui-integration.png) · [Native node screenshot](comfyui-node.png).

The integration check substitutes the model weights, text embeddings and VAE encoder; it performs **no LTX model inference**. It verifies API compatibility, tensor plumbing, and native video output rather than generated quality or GPU capacity. Run a GPU smoke test with the downloaded models and a real source clip before relying on a production endpoint.
