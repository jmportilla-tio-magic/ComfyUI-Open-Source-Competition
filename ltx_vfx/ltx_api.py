"""Opt-in direct LTX API generation. No network work occurs during import.

The hosted API has its own operation set; it does not run Creative Lab LoRAs.
Docs: https://docs.ltx.io/api-documentation/api-reference/async-video-generation
"""
from __future__ import annotations

import base64
import hashlib
import io
import ipaddress
import json
import logging
import os
import random
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_ORIGIN = "https://api.ltx.io"
MODES = {"Text to video": "text-to-video", "Image to video": "image-to-video"}
MODELS = ("ltx-2-5-fast", "ltx-2-5-pro")
RESOLUTIONS = {
    "720p": ("1280x720", "720x1280", "720x720", "1080x720", "720x1080"),
    "1080p": ("1920x1080", "1080x1920", "1080x1080", "1620x1080", "1080x1620"),
    "1440p": ("2560x1440", "1440x2560", "1440x1440", "2160x1440", "1440x2160"),
    "4K": ("3840x2160", "2160x3840", "2160x2160", "3240x2160", "2160x3240"),
}
ALL_RESOLUTIONS = tuple(r for group in RESOLUTIONS.values() for r in group)
DURATIONS = (0, 6, 8, 10, 12, 14, 16, 18, 20)
MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024 * 1024
LOG = logging.getLogger(__name__)


class TransportError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, definitive_rejection: bool = False):
        super().__init__(message)
        self.retryable = retryable
        self.definitive_rejection = definitive_rejection


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _job_id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("LTX job ID must contain only letters, digits, hyphens or underscores.")
    return value


def _image_uri(image: Any) -> str:
    shape = tuple(getattr(image, "shape", ()))
    if len(shape) != 4 or shape[0] != 1 or shape[3] not in (3, 4) or min(shape[1:3]) < 1:
        raise ValueError("Image to video requires exactly one RGB/RGBA image, not a video batch.")
    from PIL import Image
    pixels = image[0].detach().cpu().clamp(0, 1).numpy()
    buffer = io.BytesIO()
    Image.fromarray((pixels * 255).round().astype("uint8")).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    # The documented 7 MB limit is for encoded image data, not decoded bytes.
    if len(encoded) > 7_000_000:
        raise ValueError("Encoded source image exceeds LTX's 7 MB inline limit. Resize the source before running.")
    return "data:image/png;base64," + encoded


def build_payload(mode: str, prompt: str, model: str, resolution: str,
                  duration_seconds: int, fps: int, generate_audio: bool,
                  image: Any = None) -> tuple[str, dict[str, Any]]:
    if mode not in MODES:
        raise ValueError("Choose Text to video or Image to video.")
    if model not in MODELS or resolution not in ALL_RESOLUTIONS:
        raise ValueError("Choose a supported LTX-2.5 model and resolution.")
    if type(fps) is not int or fps not in (24, 25, 48, 50):
        raise ValueError("LTX-2.5 supports 24, 25, 48 or 50 fps.")
    if type(duration_seconds) is not int or duration_seconds not in DURATIONS:
        raise ValueError("Duration must be 0 (automatic), 6, 8, 10, 12, 14, 16, 18 or 20 seconds.")
    if duration_seconds > 10 and not (model == "ltx-2-5-fast" and fps in (24, 25) and resolution in RESOLUTIONS["720p"] + RESOLUTIONS["1080p"]):
        raise ValueError("Durations above 10 seconds require Fast at 720p/1080p and 24/25 fps.")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 5000:
        raise ValueError("Enter a prompt containing 1–5000 characters.")
    if type(generate_audio) is not bool:
        raise ValueError("generate_audio must be a boolean.")
    payload = {"prompt": prompt.strip(), "model": model, "resolution": resolution,
               "duration": duration_seconds or None, "fps": fps, "generate_audio": generate_audio}
    if mode == "Image to video":
        payload["image_uri"] = _image_uri(image)
    return MODES[mode], payload


class HTTPTransport:
    """Fixed-origin API requests; output requests never carry the API key."""
    def __init__(self, token: str):
        self._token = token
        self._opener = urllib.request.build_opener(NoRedirect())

    def _json(self, method: str, endpoint: str, payload: dict | None = None, *, timeout: float = 30) -> dict:
        if endpoint.split("/", 1)[0] not in MODES.values():
            raise ValueError("Unsupported LTX endpoint.")
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(f"{API_ORIGIN}/v2/{endpoint}", data=data, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=timeout) as response:
                raw = response.read(1_048_577)
                if len(raw) > 1_048_576:
                    raise TransportError("LTX returned an oversized JSON response.")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise TransportError("LTX returned an invalid JSON response.")
                return result
        except urllib.error.HTTPError as exc:
            # Never echo a request, a source data URI, or response text with a key.
            hints = {401: "Check LTX_API_KEY in the ComfyUI server environment.", 402: "Check the LTX account balance.", 404: "The job may have expired or belongs to a different operation.", 413: "Reduce the source image size.", 422: "Check the generation parameters."}
            raise TransportError(f"LTX API returned HTTP {exc.code}. {hints.get(exc.code, 'Check the LTX API service status.')}", retryable=exc.code == 429 or exc.code >= 500, definitive_rejection=exc.code in (400, 401, 402, 413, 422, 429)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TransportError("LTX API connection failed.", retryable=True) from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise TransportError("LTX returned invalid JSON.") from None

    def submit(self, endpoint: str, payload: dict) -> dict:
        return self._json("POST", endpoint, payload)

    def status(self, endpoint: str, job_id: str, timeout: float) -> dict:
        return self._json("GET", f"{endpoint}/{_job_id(job_id)}", timeout=timeout)

    def download(self, url: str, destination: Path, deadline: float) -> None:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
            raise TransportError("LTX returned an invalid HTTPS output URL.")
        host = parsed.hostname.lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise TransportError("LTX returned a non-public output URL.")
        try:
            if not ipaddress.ip_address(host).is_global:
                raise TransportError("LTX returned a non-public output URL.")
        except ValueError:
            pass  # A domain name, as normally returned by the API.
        request = urllib.request.Request(url, headers={"Accept": "video/mp4"}, method="GET")
        descriptor, temp_path = tempfile.mkstemp(prefix=".download-", suffix=".mp4", dir=destination.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream, self._opener.open(request, timeout=min(30, max(1, deadline - time.monotonic()))) as response:
                length_header = response.headers.get("Content-Length")
                length = None
                if length_header is not None:
                    try:
                        length = int(length_header)
                    except (TypeError, ValueError):
                        raise TransportError("LTX output has an invalid Content-Length.") from None
                    if length < 0:
                        raise TransportError("LTX output has an invalid Content-Length.")
                    if length > MAX_DOWNLOAD_BYTES:
                        raise TransportError("LTX output exceeds the 2 GiB download limit.")
                total = 0
                first = True
                while True:
                    _check_interrupt()
                    if time.monotonic() >= deadline:
                        raise TimeoutError("LTX output download timed out.")
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    if first and (len(chunk) < 12 or chunk[4:8] != b"ftyp"):
                        raise TransportError("LTX output is not an MP4 file.")
                    first = False
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        raise TransportError("LTX output exceeds the 2 GiB download limit.")
                    stream.write(chunk)
                if not total:
                    raise TransportError("LTX returned an empty output file.")
                if length is not None and total != length:
                    raise TransportError("LTX output download is incomplete: byte count does not match Content-Length.")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, destination)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


def _check_interrupt() -> None:
    try:
        from comfy.model_management import throw_exception_if_processing_interrupted
    except ImportError:
        return
    throw_exception_if_processing_interrupted()


def _sleep(seconds: float, deadline: float) -> None:
    until = min(time.monotonic() + seconds, deadline)
    while time.monotonic() < until:
        _check_interrupt()
        time.sleep(min(0.25, max(0, until - time.monotonic())))


def _write_state(path: Path, state: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _reserve(path: Path, state: dict) -> None:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise RuntimeError("This render is already being submitted. Wait, then queue again to resume it.") from None
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(state, stream)
        stream.flush()
        os.fsync(stream.fileno())


def generate(*, output_root: Path, mode: str, prompt: str, model: str,
             resolution: str, duration_seconds: int, fps: int, generate_audio: bool,
             allow_api_requests: bool, render_id: int, timeout_seconds: int,
             image: Any = None, resume_job_id: str = "", transport_factory=HTTPTransport) -> tuple[Path, str]:
    if allow_api_requests is not True:
        raise ValueError("Direct LTX requests are disabled. Set allow_api_requests=true only when you intend to send media and run a billable LTX job.")
    if mode not in MODES:
        raise ValueError("Choose Text to video or Image to video.")
    if type(timeout_seconds) is not int or not 30 <= timeout_seconds <= 7200:
        raise ValueError("timeout_seconds must be between 30 and 7200.")
    if type(render_id) is not int or not 0 <= render_id <= 2**63 - 1:
        raise ValueError("render_id must be a nonnegative integer.")
    token = os.environ.get("LTX_API_KEY", "").strip() or os.environ.get("LTXV_API_KEY", "").strip()
    if not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError("Set LTX_API_KEY in the ComfyUI server environment, then restart it. Never put the key in a workflow.")
    resume_job_id = resume_job_id.strip()
    endpoint = MODES[mode]
    payload = None
    if resume_job_id:
        job_id = _job_id(resume_job_id)
        identity = f"resume:{endpoint}:{job_id}"
    else:
        endpoint, payload = build_payload(mode, prompt, model, resolution, duration_seconds, fps, generate_audio, image)
        identity = json.dumps([render_id, endpoint, payload], sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(identity.encode()).hexdigest()
    directory = output_root / "ltx_api"
    state_dir = directory / ".jobs"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / f"{digest}.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    if not isinstance(state, dict):
        raise RuntimeError("The local LTX job record is invalid; inspect it before running again.")
    transport = transport_factory(token)  # No I/O in construction.
    if resume_job_id:
        if state:
            if state.get("endpoint") != endpoint or state.get("job_id") != job_id:
                raise RuntimeError("The local recovery record does not match this LTX job. Inspect the record before running again.")
        else:
            state = {"endpoint": endpoint, "job_id": job_id, "status": "submitted"}
            _reserve(state_path, state)
    elif state:
        if not state.get("job_id"):
            raise RuntimeError("A previous submission has an unknown outcome. Check the LTX console and set resume_job_id; this node will not submit twice. Change render_id only for a deliberately new render.")
        job_id = _job_id(state["job_id"])
    else:
        state = {"endpoint": endpoint, "status": "submitting", "render_id": render_id}
        _check_interrupt()
        _reserve(state_path, state)
        try:
            submitted = transport.submit(endpoint, payload)
            job_id = _job_id(submitted.get("id"))
        except TransportError as exc:
            if exc.definitive_rejection:
                state_path.unlink()
                raise RuntimeError(f"{exc} The request was rejected; correct the issue before queueing again.") from None
            raise RuntimeError("LTX submission did not return a usable job ID; its outcome may be unknown. Check the LTX console before retrying, then use resume_job_id. No automatic resubmission was attempted.") from None
        except Exception:
            raise RuntimeError("LTX submission did not return a usable job ID; its outcome may be unknown. Check the LTX console before retrying, then use resume_job_id. No automatic resubmission was attempted.") from None
        state.update(job_id=job_id, status="submitted")
        try:
            _write_state(state_path, state)
        except OSError:
            raise RuntimeError(f"LTX accepted job {job_id}, but the local recovery record could not be saved. Set resume_job_id to {job_id}; do not request a new render.") from None
    LOG.info("LTX API job %s (%s). Use resume_job_id to recover it.", job_id, endpoint)
    destination = directory / f"{endpoint}-{job_id}.mp4"
    if destination.is_file() and state.get("status") == "completed":
        return destination, job_id
    deadline = time.monotonic() + timeout_seconds
    transient_failures = 0
    try:
        while True:
            _check_interrupt()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Timed out waiting for LTX.")
            try:
                result = transport.status(endpoint, job_id, min(30, remaining))
                transient_failures = 0
            except TransportError as exc:
                if not exc.retryable:
                    raise
                transient_failures += 1
                _sleep(min(30, 5 * 2 ** min(transient_failures - 1, 3)), deadline)
                continue
            status = result.get("status")
            if status == "failed":
                kind = result.get("error", {}).get("type", "generation_failed")
                kind = re.sub(r"[^A-Za-z0-9_-]", "", str(kind))[:80]
                state["status"] = "failed"
                _write_state(state_path, state)
                raise RuntimeError(f"LTX job failed ({kind}). Check the job in your LTX console.")
            if status == "completed":
                url = result.get("result", {}).get("video_url")
                if not isinstance(url, str):
                    raise RuntimeError("Completed LTX job has no video_url.")
                transport.download(url, destination, deadline)
                state["status"] = "completed"
                _write_state(state_path, state)
                return destination, job_id
            if status not in ("pending", "processing"):
                raise RuntimeError("LTX returned an unknown job status.")
            _sleep(random.uniform(5, 6), deadline)
    except Exception as exc:
        if exc.__class__.__name__ == "InterruptProcessingException":
            raise
        raise RuntimeError(f"{exc} Job ID: {job_id}. Set resume_job_id to this ID with the same mode to resume; do not request a new render.") from None


class LTXAPIGenerate:
    CATEGORY = "OpenPositive/LTX API"
    FUNCTION = "execute"
    RETURN_TYPES = ("VIDEO", "STRING")
    RETURN_NAMES = ("video", "job_id")
    DESCRIPTION = "Opt-in direct LTX-2.5 hosted generation. Uses server LTX_API_KEY. Does not apply Creative Lab LoRAs. Connect VIDEO to Save Video."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "mode": (list(MODES),),
            "prompt": ("STRING", {"default": "", "multiline": True}),
            "model": (list(MODELS),),
            "resolution": (list(ALL_RESOLUTIONS), {"default": "1920x1080"}),
            "duration_seconds": (list(DURATIONS), {"default": 6, "tooltip": "0 lets LTX choose duration. Above 10s requires Fast, 720p/1080p, 24/25fps."}),
            "fps": ([24, 25, 48, 50],),
            "generate_audio": ("BOOLEAN", {"default": True}),
            "allow_api_requests": ("BOOLEAN", {"default": False, "tooltip": "Opt in to sending inputs and creating a billable direct LTX job when queued."}),
            "render_id": ("INT", {"default": 0, "min": 0, "max": 2**63 - 1, "tooltip": "Change only for a new render. Reusing settings and this ID resumes the existing job; this is not a model seed."}),
            "timeout_seconds": ("INT", {"default": 1800, "min": 30, "max": 7200}),
        }, "optional": {
            "image": ("IMAGE", {"tooltip": "Exactly one source still; required for Image to video."}),
            "resume_job_id": ("STRING", {"default": "", "tooltip": "Recover an existing job with the same mode without submitting again."}),
        }}

    def execute(self, **kwargs):
        import folder_paths
        from comfy_api.latest import InputImpl
        path, job_id = generate(output_root=Path(folder_paths.get_output_directory()), **kwargs)
        return InputImpl.VideoFromFile(str(path)), job_id
