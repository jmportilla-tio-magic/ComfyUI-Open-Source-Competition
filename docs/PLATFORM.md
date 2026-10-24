# Comfy Developer Platform

LTX VFX Studio is a native ComfyUI extension. Its Python nodes execute inside ComfyUI; the official SDK submits the **whole saved workflow** from outside it. The SDK does not install this extension or make the Creative Lab adapters available through Comfy Router. A Comfy API Build must contain this package and the dependencies of the selected route. [Comfy's SDK guide](https://docs.comfy.org/development/api-development/sdks) explains these separate surfaces.

| Graph route | Dependencies on the Comfy worker | Credentials |
| --- | --- | --- |
| Creative Lab effects with local weights | This pack, ComfyUI-LTXVideo, selected base models/encoders/adapter, suitable GPU | No LTX API key; Hugging Face access may be needed to obtain models |
| Hosted text/image generation | This pack, current native ComfyUI video nodes, outbound access to LTX | Personal `LTX_API_KEY` (or `LTXV_API_KEY`) in the worker environment |

The second route is the separate `LTXAPIGenerate` node described in [LTX-API.md](LTX-API.md). It does not offer the 15 Creative Lab LoRAs. `COMFY_API_KEY` authenticates this SDK runner to the Comfy service; it does not replace the LTX key. The LTX key stays on the worker, not in the graph, browser, or SDK asset upload. Built-in Comfy Partner Nodes use another credential/billing path.

## 1. Prepare a working environment

Install this repository under `ComfyUI/custom_nodes` and restart ComfyUI. For open-weights graphs, install a current [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo), then match the model variant and sampler recipe shown by the selected effect. This extension uses the host's PyTorch and model loaders. For hosted API graphs, skip the model-download steps below and follow [the hosted setup guide](LTX-API.md); configure the key on the eventual worker too.

Preview a download plan from the repository folder:

```bash
python scripts/download_models.py --effect clean-plate --with-base --comfy-root /path/to/ComfyUI
```

Accept the appropriate Hugging Face model terms, authenticate with `hf auth login` or `HF_TOKEN`, and add `--download` to execute that plan. Install its optional dependency with `pip install -e ".[models]"`. Use `--all --with-base` for all catalog adapters and their recommended transformer variants. The files are large; the default only prints a plan. `--optional-base` includes every catalogued base component.

For the official slow-motion graph:

```bash
python scripts/download_models.py --effect slow-motion-control --with-base --workflows --comfy-root /path/to/ComfyUI --download
```

This writes `examples/workflows/slow-motion-control.json` after Hugging Face grants access. It does not bypass the repository gate. HDR's official graph is already included as `examples/workflows/sdr-to-hdr.json`; its scene embedding is included when you select `--effect sdr-to-hdr`. Both specialist workflows need their own downstream nodes and controls. See [workflow notes](../examples/README.md).

## 2. Validate locally and export

For local effects, start from the appropriate official LTX-2.5 workflow, connect the Studio node and crop its guide frames before decoding, then run a short source shot on your GPU. For hosted generation, use an LTX API starter and enable `allow_api_requests` only when you intend to submit to LTX. Save the successful graph in **API format**. Canvas JSON with `nodes`/`links` is an authoring file; it is not an API request. Do not use the Studio node's recipe JSON as a workflow.

Keep the source-loader node ID and its input name (`image` or `video`), plus the final save-node ID. Those IDs depend on the graph you export. The example command below uses illustrative IDs; replace them with your graph's IDs.

```bash
pip install -e ".[platform]"
python scripts/platform_run.py workflow_api.json \
  --asset plate.mp4 --input-node 10 --input-name video --output-node 90 \
  --validate-only
```

Validation is offline and checks graph structure and input references. It does not check installed node schemas, model compatibility, VRAM or visual quality.

## 3. Start a local service, or package a company Build

### Local service

Keep your configured ComfyUI running, normally at `http://127.0.0.1:8188`. In a second terminal, install and start the official proxy:

```bash
python -m pip install comfy-api-proxy
comfy-api-proxy --comfyui http://127.0.0.1:8188 --port 8189 --state-dir .comfy-api-state
```

In the terminal used for `scripts/platform_run.py`:

```bash
export COMFY_BASE_URL="http://127.0.0.1:8189"
```

This loopback-only setup needs no `COMFY_API_KEY`; leave that variable unset in the runner. The proxy's `--state-dir` preserves its own job records. Your ComfyUI output folder separately holds saved renders and LTX job records. If you change ComfyUI's port, change `--comfyui` accordingly. For remote access, follow the proxy's documented authentication and network configuration. [Official API proxy instructions](https://docs.comfy.org/development/comfyui-server/api-proxy) · [Proxy CLI reference](https://github.com/Comfy-Org/comfy-api-proxy)

### Company workspace Build

[Comfy's Build Wizard](https://platform.comfy.org/) can import a Desktop snapshot or workflow JSON. In ComfyUI, **Workflow actions → Deploy to Comfy API → Deploy on Platform** opens that flow. Review the proposed node packs, model files and Python dependencies before creating a release. A saved local source plate is not a dependency: send each shot as a runtime asset.

For a CLI build, follow the current [official quickstart](https://docs.comfy.org/development/serverless/quickstart). From the **ComfyUI installation**:

```bash
comfy skills show comfy-build
comfy build init --name "ltx-vfx-studio" --models-dir ./models --custom-nodes-dir ./custom_nodes
```

Review the generated Build before upload. Pin this extension's commit and ComfyUI. For local-weight graphs, also pin ComfyUI-LTXVideo and include the exact selected adapters and base assets. Because Studio resolves a selected adapter at execution time, the Build Wizard may not infer every filename from its effect dropdown. Add those files explicitly. For hosted graphs, configure the LTX key through the deployment's server-side secret mechanism; do not bake it into the Build or workflow. Release and deploy after that review, using the platform's current resource options. This repository does not claim a tested GPU size or create a deployment for you.

[Build sources](https://docs.comfy.org/development/serverless/build-sources) documents snapshot and JSON import. The platform's release is an environment artifact; creating a billable running deployment is a separate step.

## 4. Run through the SDK

Set `COMFY_BASE_URL` to the company's deployment endpoint and `COMFY_API_KEY` in the server process environment. Do not put credentials in a node widget, workflow, recipe, browser bundle or checked-in file.

```bash
export COMFY_BASE_URL="https://YOUR-DEPLOYMENT.run.comfy.app"
# Set COMFY_API_KEY through your environment or secret manager.
python scripts/platform_run.py workflow_api.json \
  --asset plate.mp4 --input-node 10 --input-name video --output-node 90 \
  --state .ltx-vfx-jobs/shot-001.json --output-dir renders/shot-001
```

The helper uploads a lazy asset, submits once, shows progress, confirms success, and downloads output files into a separate job-ID folder below `--output-dir`. Repeat `--output-node` for several save nodes. A state file belongs to one workflow/source/endpoint combination. Rerunning it retrieves the same job; use a new state path for a deliberately new render.

The supplied runner is for image/video-input graphs and requires `--asset`. For the hosted [`ltx-api-image.json`](../examples/workflows/ltx-api-image.json) graph, use its Load Image and Save Video node IDs. Use the Comfy SDK directly for a text-only graph without an input asset. For hosted nodes, preserve both the outer Comfy job ID and the inner LTX job ID when recovering; changing `render_id` deliberately starts a new LTX generation.

Persist the worker's `output/ltx_api/.jobs` directory and output MP4s across restarts/replacements, or recover with the saved LTX `resume_job_id`. An ephemeral worker that loses this state cannot recognize a previously submitted provider request. The runner's `--state` file and proxy's `--state-dir` track the outer Comfy job; neither replaces the inner LTX record. See [hosted recovery](LTX-API.md).

If the submission response is lost before the job ID is saved, the helper stops. Check the deployment's job list before starting another job. Comfy API v2 rejects reuse of an idempotency key rather than replaying the original response. There is no blind resubmission loop.

For a local v2 endpoint, run `comfy-api-proxy` beside ComfyUI and set `COMFY_BASE_URL=http://127.0.0.1:8189`. A local proxy can run without an API key. Comfy Cloud uses the default URL when `COMFY_BASE_URL` is unset, but the required custom package and models still must be available there; a generic Cloud subscription does not imply that this custom Build is installed.

## Verification boundary

Repository tests exercise graph validation, submission recovery with a fake SDK, downloader selection, native-node contracts, and hosted transport with fake responses. No GPU inference, live LTX API request, company workspace Build, release, paid deployment, or authenticated cloud render has been run as part of creating this package.
