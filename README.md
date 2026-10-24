# OpenPositive · LTX VFX Studio

**A visual LTX-2.5 finishing desk that runs inside ComfyUI.** Explore all 15 Creative Lab adapters, understand each effect's requirements, and apply its settings to native ComfyUI nodes. Use your own open-source model installation, or choose a separate node for LTX's hosted text/image generation API.

![OpenPositive running inside ComfyUI](docs/comfyui-integration.png)

## Choose how to run

| Route | What you get | What you configure |
| --- | --- | --- |
| **Open weights in ComfyUI** | All 15 Creative Lab adapters, visual Studio, and editable native workflows | Current ComfyUI, ComfyUI-LTXVideo, suitable hardware, and the selected model files |
| **Your own LTX API key** | A separate **LTX API · Generate** node for hosted LTX-2.5 text-to-video and image-to-video | Current ComfyUI, an LTX account/key, and internet access; no local LTX weights |
| **Comfy service / company workspace** | Run a saved graph remotely through the official Comfy SDK | A Comfy API endpoint with this node pack and that graph's dependencies installed |

The hosted LTX API does **not** expose the Creative Lab LoRA library in its public generation schema. It cannot replace the 15 local effect workflows. The Studio's effect selector belongs to the open-weights route. [LTX model/API documentation](https://docs.ltx.io/models/ltx-2-5)

**Nothing connects to LTX or downloads weights when you install this package or open the Studio.** API workflows ship with requests disabled. Model downloads require an explicit `--download` flag. You configure and run the route you choose.

## 1. Install the node pack

First [install ComfyUI](https://docs.comfy.org/installation/manual_install) or update your existing installation. This package was tested with **ComfyUI 0.42.0**, frontend **1.57.1**, and ComfyUI-LTXVideo revision `220e1d45`. Older installations without the native LTX-2.5/video nodes need an update.

From your **ComfyUI folder**:

```bash
cd /path/to/ComfyUI
git clone https://github.com/jmportilla-tio-magic/ComfyUI-Open-Source-Competition.git custom_nodes/ComfyUI-Open-Source-Competition
```

Alternatively, use this repository's **Code → Download ZIP**, extract it, and put the extracted folder directly inside `ComfyUI/custom_nodes/`. Its `__init__.py` must be directly inside that folder, not another nested copy. Restart ComfyUI after installation.

The node pack itself has no extra pip dependencies. The optional model downloader and Comfy SDK runner have separate extras below. For commands using `python` or `pip`, use **the Python environment that runs your ComfyUI**; a different system Python will not install dependencies into ComfyUI. Desktop and portable installations have their own Python environments and `custom_nodes` locations.

## 2A. Run the 15 effects with open weights

### Install LTX support

From your ComfyUI folder, with its Python environment active:

```bash
git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git custom_nodes/ComfyUI-LTXVideo
python -m pip install -r custom_nodes/ComfyUI-LTXVideo/requirements.txt
```

If this pack is already installed, update that copy and install its requirements instead of cloning it twice. Restart ComfyUI.

### Choose and download models

From **this repository's folder**, install the optional downloader and inspect a plan:

```bash
cd /path/to/ComfyUI/custom_nodes/ComfyUI-Open-Source-Competition
python -m pip install -e ".[models]"
python scripts/download_models.py --effect cinemagraph --with-base --comfy-root /path/to/ComfyUI
```

That command only lists files and destinations. To download, accept the upstream terms on Hugging Face, authenticate locally with `hf auth login` or `HF_TOKEN`, and repeat with `--download`:

```bash
python scripts/download_models.py --effect cinemagraph --with-base --comfy-root /path/to/ComfyUI --download

# Optional: every adapter and its recommended base variants.
python scripts/download_models.py --all --with-base --comfy-root /path/to/ComfyUI --download
```

The helper puts files in ComfyUI's model folders and does not execute remote code. These are large 22B model assets; choose hardware for the upstream model/workflow requirements. You can also download manually using the exact filenames and destinations in [the model guide](docs/MODELS.md). Model licenses and access conditions are separate from this repository's MIT license.

### Make your first shot

1. Restart ComfyUI after adding models. Open or drag in [`examples/workflows/cinemagraph_api.json`](examples/workflows/cinemagraph_api.json). ComfyUI can import this API-format graph.
2. Choose your still in **Load Image**. Confirm the model, text encoder, and VAE dropdowns match the installed files. The included starter uses the development transformer.
3. Find **LTX VFX · Studio** and click **Open VFX Studio**, or use **Extensions → OpenPositive**. Select Cinemagraph, describe the part that should move, and click **Apply to ComfyUI node**.
4. Queue the workflow in ComfyUI. The graph loads models, prepares conditioning, samples, crops guides, decodes, and saves a silent MP4. Open the output from **Save Video** or ComfyUI's output folder.
5. To compare a finished render in the Studio, choose **Load a rendered reference**. Files imported into the Studio's viewer are local previews; choose the actual inference source in the graph's loader.

The example's node connections and native output path have been checked; a weighted LTX render is still required on your own configured hardware. For another effect, start from its matching upstream workflow and follow [workflow entry points](examples/README.md).

### Know which workflow an effect needs

| Effects | Workflow requirements |
| --- | --- |
| Day to night, Water simulation, Colorization | Source video, prompt, native IC sampling |
| Clean plate, Alpha matte | Source video; Alpha uses an empty prompt and produces a grayscale matte |
| Pixel upscaler ×2, Deblur, Decompression | Correct reference scale and native-resolution sampling |
| Restore archive, Refine details | Matching spatial tiled sampler plus temporal guide encoding |
| Ingredients | One prepared reference sheet, repeated as conditioning |
| Layout to render | Layout video, art-directed `first_frame`, and the official second stage |
| Cinemagraph | Still image, image-to-video conditioning, locked-camera prompt |
| Slow motion | Dedicated dual-rate image-to-video workflow; does not retime existing footage |
| SDR to HDR | Dedicated ACES/scene-embedding pipeline and HDR-compatible output |

The standard Studio node prepares model, conditioning, and latent outputs; the surrounding graph performs sampling and saving. **HDR and Slow motion use dedicated workflow handoffs.** The official HDR graph is included; the gated Slow motion graph can be fetched with the downloader's `--workflows` option. All 15 adapters are selectable through **LTX VFX · Apply Effect** inside their matching graphs. [Exact models and limits](docs/MODELS.md) · [Native node contracts](docs/NATIVE-NODES.md)

## 2B. Run hosted generation with your LTX key

This route needs **no local LTX model downloads or ComfyUI-LTXVideo installation**. It uses this package and current ComfyUI's video support.

1. Obtain a key through [LTX's API page](https://ltx.io/model/api).
2. Set `LTX_API_KEY` in the environment of the process that starts ComfyUI, then start or restart ComfyUI from that environment. `LTXV_API_KEY` is accepted as an alias. Use your OS/environment or deployment's secret manager; there is no API-key widget and keys must not go in a workflow or frontend file.
3. Open the text or image starter linked in [the LTX API guide](docs/LTX-API.md), or add **OpenPositive → LTX API → LTX API · Generate** and connect its `VIDEO` output to **Save Video**.
4. Set the prompt, model, supported resolution, duration, and frame rate. For image-to-video, connect **Load Image** to `image`.
5. When you are ready to send that request to LTX, enable **allow_api_requests** and queue it. The node submits once, polls the job, downloads the MP4, and returns a native ComfyUI `VIDEO` plus its job ID. Hosted requests use your LTX account and may incur charges.

`render_id` identifies an intentional new request; it is **not a model seed**. Keep it unchanged to retrieve the same recorded request, and change it deliberately for a new generation. The guide explains saved job state, timeouts, recovery, supported combinations, and the distinction from Comfy's built-in Partner Nodes. No API call or credential check was performed while preparing this repository.

## 3. Use the graph as a service

A Comfy service executes the **same complete graph**. Install this node pack on the server/worker, along with either its local model dependencies or its server-side LTX key. Then export the working graph using **Save (API Format)**. A `.ltx-vfx.json` Studio recipe contains settings only and is not a service workflow.

For a company workspace, package the environment as a [Comfy API Build](https://comfy.org/platform/). For a local v2 service, run the official `comfy-api-proxy` beside ComfyUI. The [platform guide](docs/PLATFORM.md) covers both and explains which runtime dependencies belong in the Build.

From this repository, install the official SDK helper and validate an image-input graph without connecting to anything:

```bash
python -m pip install -e ".[platform]"
python scripts/platform_run.py examples/workflows/cinemagraph_api.json \
  --asset your-still.png --input-node 10 --input-name image --output-node 90 \
  --validate-only
```

When you configure your endpoint, set `COMFY_BASE_URL` and, where required, `COMFY_API_KEY` in the runner's environment. Remove `--validate-only` and add a unique `--state .ltx-vfx-jobs/shot-001.json` for each intended render. Reusing that state resumes the same job. For another graph, use its actual loader/save node IDs. Hosted LTX graphs also need their request switch enabled deliberately before service execution.

**These credentials serve different purposes:** `COMFY_API_KEY` authenticates the runner to Comfy; `LTX_API_KEY` authenticates the optional hosted node from inside the worker to LTX. Local open-weights inference does not need an LTX API key. The SDK does not install custom nodes or make the Creative Lab adapters available through Comfy Router.

## Preview the interface without ComfyUI

Requires Python 3.10+. From this repository:

```bash
python3 scripts/preview.py
```

Open **http://127.0.0.1:8765**. Search/favorite effects, preview local media, edit controls, and import/export validated recipes. Press `/` to search or `⌘/Ctrl + Enter` to apply/export. No accounts, GPU, models, or Node build step are needed.

This is a design/recipe preview and does not generate video. Its sample comparison is an **illustrative lighting study, not an LTX render**. Local viewer files stay in the browser.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| OpenPositive nodes are missing | Verify the folder sits directly under `custom_nodes`, restart ComfyUI, and read its startup import errors. |
| Native LTX/video nodes are missing | Update ComfyUI. For local effects, install/update ComfyUI-LTXVideo in the same environment. |
| A model is absent from a dropdown | Check the exact filename/folder in [MODELS.md](docs/MODELS.md), then restart or refresh ComfyUI's model list. |
| The standalone preview does not render | It is a settings/preview UI. Run a complete workflow inside ComfyUI. |
| A Studio selection does not alter a connected control | A graph connection owns that input; edit/disconnect it in ComfyUI before applying a widget value. |
| Hosted API requests are disabled or the key is missing | Enable the switch only when ready; set the key in the actual ComfyUI process environment and restart. |
| Hosted request times out after submission | Preserve its job ID/state and follow the recovery guide; do not create another request just to check status. |
| A service rejects the graph | Export API format, install its node dependencies on the worker, and use actual loader/output IDs. |

## Verification and contribution

```bash
python3 -m unittest discover -s tests -v
node --test tests/*.test.mjs
node --check web/studio.js
node --check web/extension.js
```

Python contract tests and API transport tests use controlled stand-ins and do not require network, keys, torch, or weights. Node 22+ is sufficient for the JavaScript checks. GitHub Actions runs these checks and builds the package.

For an already installed ComfyUI/LTXVideo environment, the separate CPU integration check is:

```bash
/path/to/comfy/python tests/comfy_integration.py --comfy-root /path/to/ComfyUI
```

It checks actual pack registration, native tensor preparation/cropping for 13 standard paths, two specialist guards, starter graph schemas, and native MP4 encoding/decoding. Model weights, text embeddings, and the VAE encoder are substituted. The live ComfyUI browser's Studio open/apply/API-export flow also passed. [Versions and evidence](docs/NATIVE-NODES.md)

**Validation boundary:** no weighted LTX inference, live LTX API request, company Build, or authenticated service render has been executed here. The code and setup paths are prepared; validate a real shot in the environment you choose before claiming a completed demo.

## Open-source competition

The repository includes MIT-licensed application code, reproducible setup instructions, workflows, model/source provenance, and a [submission guide](docs/COMPETITION.md) mapped to the [official competition requirements](https://comfy.org/open-source-higgsfield/). Published deadline: **October 30, 2026, 9:00 a.m. Pacific Time**.

Before submission, publish the reviewed source revision and a real working demo of at most two minutes, then complete the required social post/form. Hosted API use and the **Open Weights Only** category have different rules; choose the submitted route accordingly. Eligibility is determined by the organizers. The preview image is not evidence of LTX inference.
