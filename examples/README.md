# Workflow entry points

Choose a route before loading a workflow. The local effect graphs need LTX weights and ComfyUI-LTXVideo. The separate hosted graphs need a user-configured LTX key on the ComfyUI server and current native video nodes, with no local LTX weights.

## Hosted text and image generation

[`workflows/ltx-api-text.json`](workflows/ltx-api-text.json) and [`workflows/ltx-api-image.json`](workflows/ltx-api-image.json) use **LTX API · Generate → Save Video**. Open or drag either JSON into ComfyUI. Node `30` holds the generation settings; node `90` saves the video. In the image graph, choose a still in node `10` (Load Image).

Both ship with `allow_api_requests: false`. Configure your own server-side key and enable that switch only when you intend to send the request. `render_id` selects an intentional new request, not a random model seed. See [LTX API setup](../docs/LTX-API.md) for inputs, supported combinations, and job recovery. These graphs have passed installed-node schema/link checks; no live API render has been run. They do not apply any of the 15 Creative Lab adapters.

## Runnable Cinemagraph starter

[`workflows/cinemagraph_api.json`](workflows/cinemagraph_api.json) is a complete API graph using this package and current native ComfyUI nodes. It includes model loading, the Studio node, sampling, guide cropping, tiled VAE decode and MP4 saving. It uses the model card's 512×704, 25-frame, 30-step / CFG 4 recipe on the development transformer. Native LTX scheduler defaults and Euler ancestral are used; optional STG is not enabled. It produces silent video.

Install the Cinemagraph adapter and base files, then use a still with one clear moving element. The supplied prompt animates water; edit node `30`'s prompt to match your image.

```bash
python scripts/download_models.py --effect cinemagraph --with-base --comfy-root /path/to/ComfyUI --download
python scripts/platform_run.py examples/workflows/cinemagraph_api.json \
  --asset your-still.png --input-node 10 --input-name image --output-node 90 \
  --state .ltx-vfx-jobs/cinemagraph-001.json
```

Use `--validate-only` first for an offline structure check. Node `10` loads the image; node `30` holds creative controls; node `90` saves the output. Install the package on your target Comfy endpoint before running. This graph's node signatures and connections were checked against current upstream source; its visual result and GPU execution still require a live smoke test. See the adjacent `.source.json` for sources and limits.

## Standard Studio path

Start with the official [LTX-2.5 video-to-video template](https://github.com/Lightricks/ComfyUI-LTXVideo/tree/master/example_workflows/2.5), load your source, and replace the corresponding LoRA / text conditioning / input-conditioning section with **LTX VFX Studio**. Connect the same model variant, CLIP and video VAE the selected effect requires. Its outputs are:

1. Model → the workflow's guider/sampler.
2. Positive and negative conditioning → the workflow's guider.
3. Latent → the workflow's sampling latent input.
4. Recipe → a text display if desired.

After sampling, use **LTX VFX Crop Guides** before VAE decode; it removes reference latents from the generated output. Preserve the official sampling schedule. Day to night and Cinemagraph use the development model's published sampling recipe; distilled effects use their listed distilled recipe. Layout to render needs its first-frame input, Ingredients expects a reference sheet, and Alpha generation has its published frame limit. Read the Studio effect notes before running a graph.

These are integration instructions, not a claim that arbitrary LTX sampler graphs are interchangeable. Render a short validation shot and export **Save (API Format)** before using `scripts/platform_run.py`.

## SDR to HDR

[`workflows/sdr-to-hdr.json`](workflows/sdr-to-hdr.json) is an unmodified official ComfyUI-LTXVideo canvas workflow. Drag it into an updated ComfyUI with ComfyUI-LTXVideo installed. Choose your SDR source and resolve every missing model. The workflow includes its own model-location notes, fixed scene embeddings, ACEScct input conversion, float32 decode and HDR save paths. It is separate from the generic Studio preparation node.

Source revision and SHA-256 are in [`workflows/sdr-to-hdr.source.json`](workflows/sdr-to-hdr.source.json). This upstream file is distributed under [`workflows/LTXVideo.LICENSE`](workflows/LTXVideo.LICENSE), independently of this repository's MIT code license. The upstream repository's [current workflow](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/example_workflows/2.5/HDR_workflows/LTX-2.5_ICLoRA_SDR_to_HDR_Distilled.json) may change after the pinned snapshot.

## Slow motion

The official [model card](https://huggingface.co/Lightricks/LTX-2.5-22b-LoRA-Slow-Motion-Control) provides `LTX-2.5_I2V_Speed_Control_flow.json`. It is gated along with the model. After accepting its terms, use:

```bash
python scripts/download_models.py --effect slow-motion-control --with-base --workflows --comfy-root /path/to/ComfyUI --download
```

Load the resulting `workflows/slow-motion-control.json`, resolve missing nodes/models, choose a still image, set speed and leave playback at 24 fps. Its dual-rate conditioning is required; applying the LoRA alone does not implement speed control. This is image-to-video generation, not optical-flow retiming of a source clip.

The included HDR workflow and downloaded slow-motion workflow are **canvas** JSON. Open and validate them in ComfyUI, then export API format to call them from the SDK. They are not directly accepted by the platform runner.
