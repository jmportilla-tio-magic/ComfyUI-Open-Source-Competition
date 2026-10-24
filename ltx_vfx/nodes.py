"""Composable native LTX nodes, using upstream ComfyUI sampling contracts.

The local effect nodes prepare real model/conditioning/latent values. The graph
retains control of sampling, audio, guide cropping, decoding and delivery.
A separately named, opt-in LTX API node handles hosted generation.
"""

from __future__ import annotations

import importlib
import inspect
import json
import math
from pathlib import PurePosixPath
from typing import Any

from .catalog import effect_names, get_effect


def _node(name: str, **inputs: Any) -> tuple:
    """Call a registered V1 or V3 native node without importing it at startup."""
    nodes = importlib.import_module("nodes")
    node_class = nodes.NODE_CLASS_MAPPINGS.get(name)
    if node_class is None:
        raise RuntimeError(
            f"Required node {name} is unavailable. Update ComfyUI and install "
            "Lightricks/ComfyUI-LTXVideo, then restart ComfyUI."
        )
    instance = node_class()
    function = getattr(node_class, "FUNCTION", "execute")
    result = getattr(instance, function)(**inputs)
    if inspect.isawaitable(result):
        # All native nodes used here are synchronous in the verified upstream
        # version. Never silently return an unexecuted coroutine as a tensor.
        if inspect.iscoroutine(result):
            result.close()
        raise RuntimeError(f"Native node {name} changed to async execution; update LTX VFX Studio for this ComfyUI version.")
    if isinstance(result, dict):
        return tuple(result["result"])
    if hasattr(result, "result"):
        return tuple(result.result)
    return tuple(result)


def resolve_lora_name(effect: dict[str, Any]) -> str:
    """Allow an installed adapter in a subfolder, but never guess ambiguously."""
    folder_paths = importlib.import_module("folder_paths")
    names = folder_paths.get_filename_list("loras")
    expected = effect["filename"]
    if expected in names:
        return expected
    matches = [name for name in names if PurePosixPath(name.replace("\\", "/")).name == expected]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Multiple copies of {expected} are installed. Keep one copy in models/loras.")
    raise FileNotFoundError(
        f"{effect['name']} needs {expected} in ComfyUI/models/loras. "
        f"Download it from {effect['source_url']} or run scripts/download_models.py "
        f"--effect {effect['id']} --comfy-root /path/to/ComfyUI --download."
    )


def _number(value: float, name: str, low: float, high: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number.")
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}.")


def validate_settings(effect: dict[str, Any], *, width: int, height: int, frames: int,
                      frame_rate: float, strength: float, guide_strength: float) -> None:
    multiple = effect.get("dimension_multiple", 32)
    factor = int(effect.get("reference_downscale_factor") or 1)
    multiple = math.lcm(multiple, 32 * factor)
    for name, value in (("width", width), ("height", height)):
        _number(value, name, 64, 8192)
        if not isinstance(value, int) or value % multiple:
            raise ValueError(f"{name} must be an integer multiple of {multiple} for {effect['name']}.")
        if effect.get(f"max_{name}") and value > effect[f"max_{name}"]:
            raise ValueError(f"{effect['name']} supports {name} up to {effect[f'max_{name}']}.")
    _number(frames, "frames", 9, 4097)
    if not isinstance(frames, int) or frames % 8 != 1:
        raise ValueError("LTX frame count must be 8n + 1, for example 49, 97 or 121.")
    if effect.get("min_frames") and frames < effect["min_frames"]:
        raise ValueError(f"{effect['name']} requires at least {effect['min_frames']} frames.")
    if effect.get("max_frames") and frames > effect["max_frames"]:
        raise ValueError(f"{effect['name']} supports at most {effect['max_frames']} frames.")
    _number(frame_rate, "frame_rate", 1, 120)
    _number(strength, "strength", *effect.get("strength_range", [0, 2]))
    _number(guide_strength, "guide_strength", 0, 1)


def _source_shape(source: Any) -> tuple[int, int, int, int]:
    shape = tuple(source.shape)
    if len(shape) != 4 or shape[0] < 1 or shape[-1] not in (3, 4):
        raise ValueError("Source must be a nonempty ComfyUI IMAGE batch [frames, height, width, RGB/RGBA].")
    return shape


def _encode(clip: Any, text: str) -> Any:
    return _node("CLIPTextEncode", clip=clip, text=text)[0]


def _guide(positive, negative, vae, latent, image, strength, factor=1, frame_idx=0,
           streaming=False, tile_frames=97):
    return _node(
        "LTXAddVideoICLoRAGuide", positive=positive, negative=negative, vae=vae,
        latent=latent, image=image, frame_idx=frame_idx, strength=strength,
        latent_downscale_factor=float(factor), crop="center", use_tiled_encode=False,
        tile_size=256, tile_overlap=64, use_streaming=streaming, tile_frames=tile_frames,
    )


class LTXVFXApplyEffect:
    """Adapter-only building block for official specialist workflows."""

    CATEGORY = "OpenPositive/LTX VFX"
    FUNCTION = "apply"
    RETURN_TYPES = ("MODEL", "STRING")
    RETURN_NAMES = ("model", "effect_info")
    DESCRIPTION = "Apply a verified Creative Lab adapter. Conditioning and sampling remain in your graph."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "effect": (effect_names(),),
            "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
        }}

    def apply(self, model, effect, strength=1.0):
        selected = get_effect(effect)
        _number(strength, "strength", *selected.get("strength_range", [0, 2]))
        if selected.get("strength_fixed") and strength != 1.0:
            raise ValueError(f"{selected['name']} requires adapter strength 1.0.")
        name = resolve_lora_name(selected)
        patched = _node("LoraLoaderModelOnly", model=model, lora_name=name, strength_model=strength)[0]
        info = {"effect": selected["id"], "adapter": name,
                "pipeline": selected["pipeline"], "notes": selected["notes"],
                "workflow_url": selected["workflow_url"]}
        return patched, json.dumps(info, indent=2)


class LTXVFXStudio:
    """One preparation node; upstream samplers remain visible and replaceable."""

    CATEGORY = "OpenPositive/LTX VFX"
    FUNCTION = "prepare"
    RETURN_TYPES = ("MODEL", "CONDITIONING", "CONDITIONING", "LATENT", "STRING")
    RETURN_NAMES = ("model", "positive", "negative", "latent", "recipe")
    DESCRIPTION = (
        "Prepare LTX-2.5 footage with a Creative Lab adapter and native conditioning. "
        "Connect outputs to the matching LTX sampler, crop guides, then decode. "
        "SDR-to-HDR and speed control require their dedicated official workflows."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "clip": ("CLIP",), "vae": ("VAE",), "source": ("IMAGE",),
            "effect": (effect_names(),),
            "prompt": ("STRING", {"default": "", "multiline": True}),
            "negative_prompt": ("STRING", {"default": "", "multiline": True}),
            "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
            "guide_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
            "width": ("INT", {"default": 768, "min": 64, "max": 8192, "step": 32}),
            "height": ("INT", {"default": 448, "min": 64, "max": 8192, "step": 32}),
            "frames": ("INT", {"default": 97, "min": 9, "max": 4097, "step": 8}),
            "frame_rate": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 1.0}),
        }, "optional": {
            "first_frame": ("IMAGE", {"tooltip": "Required art-directed first frame for Layout to render."}),
        }}

    def prepare(self, model, clip, vae, source, effect, prompt="", negative_prompt="",
                strength=1.0, guide_strength=1.0, width=768, height=448, frames=97,
                frame_rate=24.0, first_frame=None):
        selected = get_effect(effect)
        if selected["pipeline"] in ("hdr", "i2v_speed"):
            reason = ("ACEScct conversion, fixed scene embeddings, seam-keyframe conditioning and HDR export"
                      if selected["pipeline"] == "hdr" else "separate motion-fps and playback-fps conditioning")
            raise ValueError(
                f"{selected['name']} needs its dedicated workflow for {reason}. "
                f"Open {selected['source_url']} and load the linked official workflow. "
                "Use LTX VFX · Apply Effect inside that workflow to choose this adapter."
            )
        validate_settings(selected, width=width, height=height, frames=frames,
                          frame_rate=frame_rate, strength=strength, guide_strength=guide_strength)
        source_frames, _, _, _ = _source_shape(source)
        kind = selected["conditioning"]
        if kind in ("image", "reference_sheet"):
            if source_frames != 1:
                raise ValueError(f"{selected['name']} expects one still image, not {source_frames} frames.")
        elif source_frames < frames:
            raise ValueError(
                f"Source has {source_frames} frames but output requests {frames}. "
                "Load a longer clip or choose a shorter 8n+1 frame count. Match source fps before loading."
            )
        if kind == "layout_and_image":
            if first_frame is None or _source_shape(first_frame)[0] != 1:
                raise ValueError("Layout to render needs one art-directed still connected to first_frame, plus the layout video.")

        model, _ = LTXVFXApplyEffect().apply(model, effect, strength)
        effective_prompt = "" if selected["prompt_policy"] == "empty" else prompt.strip() or selected["prompt_hint"]
        if selected.get("trigger") and selected["trigger"] not in effective_prompt:
            effective_prompt = selected["trigger"] + ", " + effective_prompt
        positive, negative = _encode(clip, effective_prompt), _encode(clip, negative_prompt)
        positive, negative = _node("LTXVConditioning", positive=positive, negative=negative, frame_rate=frame_rate)

        # Layout's documented two-stage workflow generates at half resolution,
        # then applies the same IC adapter again after a 2x latent upscale.
        stage1_width = width // 2 if selected["pipeline"] == "ic_lora_two_stage" else width
        stage1_height = height // 2 if selected["pipeline"] == "ic_lora_two_stage" else height
        if kind == "image":
            positive, negative, latent = _node(
                "LTXVImgToVideo", positive=positive, negative=negative, vae=vae, image=source,
                width=stage1_width, height=stage1_height, length=frames, batch_size=1, strength=guide_strength,
            )
        else:
            latent = _node("EmptyLTXVLatentVideo", width=stage1_width, height=stage1_height, length=frames, batch_size=1)[0]
            reference = source.repeat(frames, 1, 1, 1) if kind == "reference_sheet" else source[:frames]
            factor = selected.get("reference_downscale_factor") or 1
            positive, negative, latent = _guide(
                positive, negative, vae, latent, reference, guide_strength, factor,
                streaming=selected["pipeline"] in ("tiled_refine", "tiled_restore"),
                tile_frames=selected.get("tile", {}).get("frames", 97),
            )
            if kind == "layout_and_image":
                positive, negative, latent = _guide(positive, negative, vae, latent, first_frame, guide_strength, frame_idx=-1)

        recipe = {
            "effect": selected["id"], "pipeline": selected["pipeline"], "status": "prepared",
            "prompt": effective_prompt, "negative_prompt": negative_prompt,
            "width": width, "height": height, "frames": frames, "frame_rate": frame_rate,
            "stage1_width": stage1_width, "stage1_height": stage1_height,
            "source_frames": source_frames, "strength": strength, "guide_strength": guide_strength,
            "reference_downscale_factor": selected.get("reference_downscale_factor"),
            "recommended_sampler_settings": selected["defaults"], "notes": selected["notes"],
            "next": "Use the matching official LTX sampling stages, crop IC guides, decode and save.",
            "workflow_url": selected["workflow_url"],
        }
        return model, positive, negative, latent, json.dumps(recipe, indent=2)


class LTXVFXCropGuides:
    CATEGORY = "OpenPositive/LTX VFX"
    FUNCTION = "crop"
    RETURN_TYPES = ("CONDITIONING", "CONDITIONING", "LATENT")
    RETURN_NAMES = ("positive", "negative", "latent")
    DESCRIPTION = "Remove IC reference tokens after sampling, before VAE decoding."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"positive": ("CONDITIONING",), "negative": ("CONDITIONING",), "latent": ("LATENT",)}}

    def crop(self, positive, negative, latent):
        return _node("LTXVCropGuides", positive=positive, negative=negative, latent=latent)


from .ltx_api import LTXAPIGenerate


NODE_CLASS_MAPPINGS = {
    "LTXVFXStudio": LTXVFXStudio,
    "LTXVFXApplyEffect": LTXVFXApplyEffect,
    "LTXVFXCropGuides": LTXVFXCropGuides,
    "LTXAPIGenerate": LTXAPIGenerate,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "LTXVFXStudio": "LTX VFX · Studio",
    "LTXVFXApplyEffect": "LTX VFX · Apply Effect",
    "LTXVFXCropGuides": "LTX VFX · Crop Guides",
    "LTXAPIGenerate": "LTX API · Generate",
}
