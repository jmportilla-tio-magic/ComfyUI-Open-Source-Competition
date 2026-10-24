# Competition submission readiness

Reviewed against the [official Open Source Higgsfield competition page](https://comfy.org/open-source-higgsfield/) on October 23, 2026, including the expanded **App requirements**, **Prepare your submission**, and **Submit** sections. This is a preparation checklist, not a submitted entry or a guarantee of eligibility.

## Deadline and required deliverables

The published submission deadline is **October 30, 2026 at 9:00 a.m. Pacific Time**. Winners are scheduled to be announced November 6. Local, Comfy Cloud, Developer Platform, SDK, and mixed ComfyUI implementations are allowed. A hosted app or endpoint is encouraged but optional. [Official rules and timeline](https://comfy.org/open-source-higgsfield/)

The entry needs:

1. A GitHub repository containing app code, workflow files, an open-source license, and instructions sufficient to run locally.
2. A demo video **no longer than two minutes** showing the work in action. For **Most Innovative**, explain what is innovative.
3. A social post linking the demo on Reddit, X, Instagram, LinkedIn, YouTube, or TikTok, tagged **`#OpenSourceHiggsfield`**.
4. The completed [submission form](https://form.typeform.com/to/V1dSQrkS). There is also a separate [sign-up form](https://form.typeform.com/to/Ayn9Cwfj).

The official page also requires lawful, SFW work without unlicensed IP or likenesses, limits entries to one submission per person, and says submission grants the named organizers and sponsors permission to feature the work with credit. The user must review those terms before submitting. Nothing in this repository automatically signs up, posts publicly, or submits a form. [App requirements](https://comfy.org/open-source-higgsfield/#challenge-content)

## Repository readiness

| Item | Current evidence | Remaining action before submission |
| --- | --- | --- |
| ComfyUI implementation | Three native custom nodes and the effect catalog registered in actual ComfyUI 0.42.0. Real CPU integration checked all 13 standard preparation paths, both specialist guards, the starter graph's schemas, and native MP4 output. | Verify the full weighted render on the GPU environment used for the demo. Follow the [native validation record](NATIVE-NODES.md); the standalone preview is not inference evidence. |
| Optional direct LTX API path | `LTXAPIGenerate` registered in actual ComfyUI; both hosted starter graphs passed schema/link checks. Its native VIDEO output was checked with a local synthetic MP4, and offline tests cover request/response and recovery contracts. It is separate from the 15-adapter local workflow. | A live hosted render requires the user's later opt-in; no such request or result is established here. |
| LTX as the core video model | The model catalog and sample graph use LTX-2.5; adapters come from Lightricks Creative Lab. | Capture an actual LTX render in the demo. |
| Open-source app license | Root `LICENSE` is MIT. Upstream workflow licensing and source provenance are included separately. | Keep those files in the public repository and distribution. |
| Local and service setup | Setup separates local ComfyUI weights, direct LTX credentials, and optional Comfy workflow transport. The compatibility work does not download model weights or make generation API calls. | Follow the documented path from a clean installation, recording exact versions and any provider used. Never publish an API key. |
| Shareable workflow | A Cinemagraph API graph and an official HDR canvas graph are included. | Provide the exact successfully executed graph with the demo. A settings-only `.ltx-vfx.json` recipe is not a workflow. |
| Public source revision | The Git remote is configured, but this implementation was still uncommitted local work at review time. | Publish the reviewed revision and verify the public link exposes all source, assets, licenses, and workflow files. |
| Real rendered demonstration | The interface sample is explicitly labeled an illustrative lighting study. Neither weighted GPU inference nor a live direct-LTX generation request has been validated. | Produce real output using the mode selected for the entry; do not use the CSS comparison as evidence of model inference. |
| Demo video and social post | Neither is included as a completed submission artifact. | Record the video, publish it and the tagged social post, and copy both URLs into the entry form. |
| Optional hosted link | A local preview and deployment helper are included. | If offering a hosted demo, test it with the same pinned models and workflow before sharing. Hosting is not required. |

## Describe the scope accurately

OpenPositive is a guided LTX-2.5 effect library, custom-node pack, and workflow companion. It has a catalog of all 15 Creative Lab adapters for the local open-weights path, plus an optional direct LTX API generation path. **The API path does not expose those 15 adapters, and catalog coverage is not a claim that 15 complete inference pipelines have been GPU-tested.**

- The Studio node prepares models and conditioning for the standard paths. The graph still owns sampling, guide cropping, VAE decoding, and saving.
- `LTXAPIGenerate` has its own text-to-video and image-to-video controls. It uses a personal LTX key from the ComfyUI server environment and does not take a local `MODEL`, `CLIP`, `VAE`, or Creative Lab LoRA. It is not a Comfy Partner Node using Comfy credits.
- HDR and slow-motion use dedicated upstream workflows because their color-management or dual-rate conditioning cannot be replaced by a generic LoRA selection.
- Layout to render requires the art-directed first frame and the official second-stage workflow. Restore and Refine details require the matching tiled sampling setup.
- The standalone UI is a local design/recipe preview. Browser-imported footage does not automatically become a graph input. For a real run, use the same source in ComfyUI.
- ComfyUI integration and schema tests establish compatibility only for the components they exercised. Offline API tests do not establish valid credentials, available credit, service availability, or a generated result. Neither kind of test establishes final video quality or GPU capacity.

For the competition, lead with **one complete, reproducible VFX experience**. Include its input, final output, exact graph, prompt and settings. Demonstrate additional effects only after each has a successful real render. The [model guide](MODELS.md) describes the per-effect requirements.

### Choose the path shown in the entry

For the local path, users supply compatible LTX weights in ComfyUI's model folders and follow the selected effect's workflow. No API key is needed for local inference. The download helper is optional and must be run explicitly; compatibility checks do not fetch weights.

For the hosted path, users obtain a personal key through the [LTX API page](https://ltx.io/model/api), set `LTX_API_KEY` in the **ComfyUI server process environment** (`LTXV_API_KEY` is also accepted), and restart that process. They use `LTXAPIGenerate` for its documented text/image generation operations. Its `allow_api_requests` control defaults to false; enabling it and queueing the graph sends input to LTX and can incur charges. Keep keys out of workflows, screenshots, and demo recordings. [Direct API authentication](https://docs.ltx.io/authentication)

The optional Comfy SDK/deployment path uses a different credential and runs a complete saved ComfyUI graph. `COMFY_API_KEY` is not a personal LTX API key. State which execution path the demo uses and do not present hosted generation as a local open-weights render.

## Category positioning

The published **VFX Workflow Built with LTX** bonus requires LTX to be the core video model. That is the intended architecture of this project, but the entry should demonstrate the executed workflow; organizers determine eligibility. The page states entries may be considered for both a main category and a model-provider bonus. [Prize criteria](https://comfy.org/open-source-higgsfield/)

For **Most Innovative**, a defensible explanation is the guided mapping from a creative goal to the appropriate LTX adapter, source type, prompt rules, dimensions, and specialist workflow. Explain the concrete errors it prevents, such as using text conditioning for Alpha Gen or treating ordinary RGB output as HDR. Avoid claiming the underlying Lightricks models as original inventions.

For **Open Weights Only**, the public rule excludes partner nodes and closed-source APIs. A workflow using `LTXAPIGenerate` is a hosted API workflow and must not be represented as an open-weights-only run. The native inference path uses locally loaded model weights; the optional Comfy SDK is workflow transport, not a model provider. If targeting this category, demonstrate the local path and audit the entire submitted graph and deployed environment for partner nodes, API-backed encoders, or other closed inference services. Do not claim the full two-mode application is guaranteed eligible; organizers decide whether the submitted entry qualifies. General competition entries may use other tools and models when explained in the demo. [Category and app rules](https://comfy.org/open-source-higgsfield/)

The bundled sample still was created with a proprietary image-generation tool and is documented in [`web/assets/README.md`](../web/assets/README.md). It is not a runtime dependency, nor an LTX-generated output. Disclose that provenance in the demo if it appears. For an unambiguous open-weights demonstration, use your own photograph/footage or a clearly licensed input and show the real LTX result. Model access gates and model licenses remain separate from the MIT app license.

## Execution validation record to complete

Record these next to the final demo workflow before publication:

| Field | Evidence to record |
| --- | --- |
| Source revision | Public repository commit SHA |
| Runtime | ComfyUI revision, frontend version, ComfyUI-LTXVideo revision, Python/PyTorch versions |
| Execution mode | Local weights, direct LTX API, or a named combination; do not conflate them |
| Hardware or service | For local inference: GPU, available VRAM, runtime flags and measured peak memory if available. For hosted inference: provider, operation, model variant and job ID, never the key |
| Models | For local inference: exact base model, encoder, VAE and adapter filenames. For hosted inference: API model identifier and supported operation |
| Input | A rights-cleared source, source dimensions, frames and frame rate |
| Execution | Local: prompt, seed, effect strength, schedule, steps, CFG, dimensions and frames. Direct API: prompt, model, resolution, duration and FPS; `render_id` is an application job identity, not a model seed |
| Result | Completed job, playable output, output metadata and visual checks |
| Reproduction | Fresh-environment installation and second run with the same graph |

At minimum, verify that the chosen graph registers without missing-node errors, accepts the source, produces the expected duration/dimensions, saves playable video, and preserves its connections after save/reload. Check the output for flicker, source drift, added content, or unintended motion. Do not mark GPU execution or live hosted generation complete from mocked tests or CPU-only preparation checks.

## Two-minute demo outline

| Time | Show |
| --- | --- |
| 0:00–0:15 | The real source and finished LTX output, labeled clearly. State the VFX task. |
| 0:15–0:35 | Open the project inside ComfyUI and show its model/source connections. |
| 0:35–0:55 | Open the Studio, select the effect, and show the meaningful controls and guidance. |
| 0:55–1:20 | Apply the settings to the graph, run or show the completed job, and identify LTX as the core model. Time-compress waiting if necessary and label the edit. |
| 1:20–1:40 | Play the real result and compare it with the source. |
| 1:40–1:55 | Explain the custom-node behavior, specialist workflow routing, and what is new in this project. Disclose outside tools used for assets. |
| 1:55–2:00 | Show the repository link, install entry point, and any optional working demo link. |

## Suggested entry description

> OpenPositive is a guided LTX-2.5 VFX studio inside ComfyUI. It organizes the Creative Lab adapters by creative task and applies validated, model-aware settings to native nodes. Its interface explains source requirements, prompt rules and specialist workflows while leaving the complete inference graph inspectable and editable.
>
> The submitted demo shows **[the actual tested effect]** running on **[the tested environment]**. The repository includes the exact workflow, setup instructions, model download plans, source provenance and an MIT license. **[Add the measured render details and public links after the real GPU run.]**

Replace every bracketed item with evidence before publishing. Use the [official submission form](https://form.typeform.com/to/V1dSQrkS) only after the repository, demo, social post, and consent review are complete.
