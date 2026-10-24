# Direct LTX API route

**LTX API · Generate** is an optional native ComfyUI node for hosted text-to-video and image-to-video using your own LTX account. It needs a current ComfyUI with native `VIDEO` support, but does not load local LTX model weights.

It is separate from **LTX VFX · Studio** and the 15 Creative Lab adapters. The direct API does not expose a custom LoRA field. Use the open-source ComfyUI route for Clean plate, Alpha generation, and the other collection-specific effects. This direct node currently implements only the two LTX-2.5 generation endpoints; it does not implement retake, extension, audio-input generation, or HDR conversion.

## Set up the server yourself

1. Obtain a key through the [LTX developer console](https://console.ltx.io/). Review your account's current billing and limits.
2. Set `LTX_API_KEY` in the environment of the process that launches **ComfyUI**. `LTXV_API_KEY` is accepted as a fallback alias; `LTX_API_KEY` takes precedence. Restart ComfyUI after changing the environment. A key in a browser or a different terminal does not configure an already-running server.
3. Install this extension under `ComfyUI/custom_nodes` and restart ComfyUI.
4. Add **LTX API · Generate**, then connect its `video` output to native **Save Video**. For Image to video, connect exactly one still from **Load Image** to `image`.
5. Set the mode, prompt, model, resolution, duration, frame rate and audio option. When ready to send inputs to LTX and create a billable generation, explicitly turn on `allow_api_requests` and queue the graph.

There is no API-key widget. Keys are not saved in a workflow, recipe, job record, or browser. The node makes no requests at import, discovery, or validation time. Its request toggle defaults to **off**. This project has not configured or tested an account on your behalf.

For a manual ComfyUI installation, start it from the same terminal where you set the key. These examples prompt for the key without echoing it or writing it as a literal command in shell history.

**macOS/Linux, Bash:**

```bash
cd /path/to/ComfyUI
read -r -s -p "LTX API key: " LTX_API_KEY
export LTX_API_KEY
printf '\n'
python main.py
```

**Windows, PowerShell:**

```powershell
cd C:\path\to\ComfyUI
$ltxSecret = Read-Host "LTX API key" -AsSecureString
$env:LTX_API_KEY = [System.Net.NetworkCredential]::new("", $ltxSecret).Password
python main.py
```

Use your installation's Python executable if it differs from `python`. For Desktop, a service manager, or a hosted worker, configure the environment in the launcher/service instead. A `.env` file is not loaded automatically by this node. Setting the key and starting ComfyUI do not send a generation request; the explicit switch and queue action are still required.

## Inputs and outputs

| Control | Meaning |
| --- | --- |
| Mode | Text to video, or Image to video. Text mode does not send a connected image. |
| Model | `ltx-2-5-fast` or `ltx-2-5-pro`. |
| Resolution | A supported landscape, portrait or square dimension; the dropdown also includes 3:2 and 2:3. |
| Duration | `0` sends automatic duration (`null`); other values are seconds. |
| FPS | 24, 25, 48, or 50. |
| Generate audio | Request synchronized generated audio, or a silent video. |
| Render ID | Local request discriminator. Reuse it to recover the same render; change it deliberately for a new render. It is not a model seed. |
| Timeout | Total polling/download budget, 30–7200 seconds. |
| Resume job ID | Recover a known job without submitting again. Keep the original mode. |

**Validation follows the [LTX-2.5 support matrix](https://docs.ltx.io/models/ltx-2-5).** Pro supports 6, 8, or 10 seconds. Fast also supports 12–20 seconds in steps of two at 720p/1080p and 24/25 fps. At higher resolution or frame rate it supports 6, 8, or 10 seconds. Automatic duration is supported by both models. A prompt is required and limited to 5000 characters.

For image mode, the node encodes one `IMAGE` tensor as PNG and sends it inline. It rejects a video batch and enforces the documented 7 MB encoded-image limit; resize oversized input before running. This node does not silently upload images elsewhere to work around the limit. [Input formats](https://docs.ltx.io/input-formats) describes the provider contract.

The outputs are a native ComfyUI **VIDEO** and the **job ID**. Connect VIDEO to Save Video or other compatible native video nodes. Downloaded MP4s and small recovery records are stored under `ComfyUI/output/ltx_api`; records contain no key, prompt, or source image. Keep that directory to retain local recovery across restarts.

## Recovery and request behavior

The node submits once, then polls at 5–6 second intervals. It checks ComfyUI cancellation while waiting. A timeout or interrupted download reports the job ID: paste it into `resume_job_id`, keep the original mode, and queue again. Resume never resubmits the generation. Canceling a ComfyUI queue entry stops local waiting; it does not cancel the remote LTX job.

If the submit response is lost before a job ID arrives, the local record marks the outcome as unknown and prevents another submission with the same settings/Render ID. Check your LTX console for the job first. Use `resume_job_id` when you find it. Only change Render ID when you intentionally want another generation. Explicit rejected requests, such as invalid credentials or parameters, can be retried after correcting the issue.

Completed output is downloaded atomically with a 2 GiB limit. API credentials are sent only to `https://api.ltx.io`; downloading the provider's HTTPS result URL uses no Authorization header. Redirects are rejected. The node reuses a completed local MP4 when the same render is queued again.

LTX job records and output URLs have limited retention; recover/download promptly. See [async jobs](https://docs.ltx.io/async-jobs).

## Example API graphs

- [`ltx-api-text.json`](../examples/workflows/ltx-api-text.json): node `30` generates text-to-video; node `90` saves it.
- [`ltx-api-image.json`](../examples/workflows/ltx-api-image.json): node `10` loads a still; node `30` generates image-to-video; node `90` saves it.

Both ship with `allow_api_requests: false`. These are **API-format** graphs: open or drag them into current ComfyUI, or send a graph to your own ComfyUI `/prompt` endpoint wrapped as `{"prompt": graph}`. Set the request toggle yourself and, for the image graph, use an image already in that server's input folder or upload it through that server's normal asset mechanism. The `LTX_API_KEY` belongs on that ComfyUI server, including when another service submits the graph.

References: [text endpoint](https://docs.ltx.io/api-documentation/api-reference/async-video-generation/submit-text-to-video), [image endpoint](https://docs.ltx.io/api-documentation/api-reference/async-video-generation/submit-image-to-video). Implementation checks here are offline with fake transports. No credential check, generation request, model download, or remote connection was performed while building this route.
