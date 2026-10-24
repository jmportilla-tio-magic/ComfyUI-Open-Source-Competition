"""Run real ComfyUI node contracts on CPU without downloading model weights.

Example:
  /path/to/comfy/python tests/comfy_integration.py --comfy-root /path/to/ComfyUI

This deliberately sits outside unittest's test_*.py discovery. CLIP embeddings,
VAE encoding and LoRA weights are controlled stand-ins; native node loading,
schema normalization, tensor guide handling and guide cropping are real.
It verifies integration mechanics, not generated-video quality.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import importlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy-root", type=Path, required=True)
    parser.add_argument("--ltx-root", type=Path)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    comfy_root = args.comfy_root.resolve()
    ltx_root = (args.ltx_root or comfy_root / "custom_nodes" / "ComfyUI-LTXVideo").resolve()
    sys.path.insert(0, str(comfy_root))
    sys.path.insert(1, str(project_root))

    # Set CPU before importing Comfy model management; never allocate a GPU.
    from comfy.cli_args import args as comfy_args
    comfy_args.cpu = True
    import torch
    import nodes

    async def load():
        for path in (
            comfy_root / "comfy_extras" / "nodes_lt.py",
            comfy_root / "comfy_extras" / "nodes_custom_sampler.py",
            comfy_root / "comfy_extras" / "nodes_video.py",
            ltx_root,
            project_root,
        ):
            if not await nodes.load_custom_node(str(path), set()):
                raise RuntimeError(f"ComfyUI could not load {path}; install the pack's requirements.")

    asyncio.run(load())
    from ltx_vfx.catalog import EFFECTS
    LTXVFXStudio = nodes.NODE_CLASS_MAPPINGS["LTXVFXStudio"]
    LTXVFXCropGuides = nodes.NODE_CLASS_MAPPINGS["LTXVFXCropGuides"]
    studio_module = importlib.import_module(LTXVFXStudio.__module__)
    from comfy_api.latest import _io
    from comfy_execution.graph_utils import is_link
    import execution
    import folder_paths

    class WeightlessClip:
        def tokenize(self, text):
            return text

        def encode_from_tokens_scheduled(self, tokens):
            return [[torch.zeros((1, 4, 8)), {"test_prompt": tokens}]]

    class WeightlessVAE:
        downscale_index_formula = (8, 32, 32)

        def encode(self, images):
            frames, height, width, _ = images.shape
            return torch.zeros((1, 128, (frames - 1) // 8 + 1, height // 32, width // 32))

        def encode_tiled(self, images, **kwargs):
            return self.encode(images)

    # Verify every native dependency through its actual registered schema.
    dependencies = ["LoraLoaderModelOnly", "CLIPTextEncode", "LTXVConditioning", "EmptyLTXVLatentVideo", "LTXVImgToVideo", "LTXAddVideoICLoRAGuide", "LTXVCropGuides"]
    for name in dependencies:
        cls = nodes.NODE_CLASS_MAPPINGS[name]
        if hasattr(cls, "GET_SCHEMA"):
            cls.GET_SCHEMA()
        inputs = cls.INPUT_TYPES()
        assert "required" in inputs, name
        assert callable(getattr(cls(), cls.FUNCTION)), name

    results = []
    with patch.object(studio_module, "resolve_lora_name", lambda effect: effect["filename"]), patch.object(
        nodes.NODE_CLASS_MAPPINGS["LoraLoaderModelOnly"], "load_lora_model_only", lambda self, model, **kwargs: (model,)
    ):
        for effect in EFFECTS:
            if effect["pipeline"] in {"hdr", "i2v_speed"}:
                try:
                    LTXVFXStudio().prepare(None, None, None, None, effect["id"])
                except ValueError as exc:
                    assert "dedicated workflow" in str(exc)
                else:
                    raise AssertionError(f"{effect['id']} silently used generic sampling")
                results.append({"effect": effect["id"], "status": "dedicated-workflow guard verified"})
                continue
            frames = max(9, effect.get("min_frames", 9))
            if effect["pipeline"] in {"tiled_refine", "tiled_restore"}:
                frames = 121  # Exercise the actual multi-window conditioning branch.
            source_frames = 1 if effect["conditioning"] in {"image", "reference_sheet"} else frames
            source = torch.zeros((source_frames, 128, 128, 3))
            result = LTXVFXStudio().prepare(
                object(), WeightlessClip(), WeightlessVAE(), source, effect["id"],
                prompt="Tiny CPU integration check", width=128, height=128, frames=frames,
                first_frame=torch.zeros((1, 128, 128, 3)) if effect["conditioning"] == "layout_and_image" else None,
            )
            positive, negative, latent = result[1:4]
            assert positive[0][1]["frame_rate"] == 24.0, effect["id"]
            _, _, cropped = LTXVFXCropGuides().crop(positive, negative, latent)
            stage_side = 64 if effect["pipeline"] == "ic_lora_two_stage" else 128
            expected = (1, 128, (frames - 1) // 8 + 1, stage_side // 32, stage_side // 32)
            assert tuple(cropped["samples"].shape) == expected, (effect["id"], cropped["samples"].shape, expected)
            assert torch.isfinite(cropped["samples"]).all(), effect["id"]
            if effect["prompt_policy"] == "empty":
                assert positive[0][1]["test_prompt"] == "", effect["id"]
            results.append({"effect": effect["id"], "status": "native CPU conditioning and crop passed", "shape": list(expected)})
    asset_fields = {"LoadImage": "image", "UNETLoader": "unet_name", "CLIPLoader": "clip_name", "VAELoader": "vae_name"}
    graphs = {}
    for filename in ("cinemagraph_api.json", "ltx-api-text.json", "ltx-api-image.json"):
        graph = json.loads((project_root / "examples" / "workflows" / filename).read_text())
        graphs[filename] = graph
        for node_id, node in graph.items():
            cls = nodes.NODE_CLASS_MAPPINGS[node["class_type"]]
            if hasattr(cls, "GET_SCHEMA"):
                cls.GET_SCHEMA()
            spec = cls.INPUT_TYPES()
            if hasattr(cls, "GET_SCHEMA"):
                spec, _, _ = _io.get_finalized_class_inputs(spec, node["inputs"])
            available = spec.get("required", {}) | spec.get("optional", {})
            missing = set(spec.get("required", {})) - node["inputs"].keys()
            assert not missing, (filename, node_id, "missing inputs", sorted(missing))
            unknown = node["inputs"].keys() - available.keys()
            assert not unknown, (filename, node_id, "unknown inputs", sorted(unknown))
            for name, value in node["inputs"].items():
                kind = available[name][0]
                if is_link(value):
                    upstream = nodes.NODE_CLASS_MAPPINGS[graph[value[0]]["class_type"]]
                    actual = upstream.RETURN_TYPES[value[1]]
                    assert actual == kind, (filename, node_id, name, actual, kind)
                elif isinstance(kind, list) and name != asset_fields.get(node["class_type"]):
                    assert value in kind, (filename, node_id, name, value, kind)
    starter = graphs["cinemagraph_api.json"]
    hosted_cls = nodes.NODE_CLASS_MAPPINGS["LTXAPIGenerate"]
    assert hosted_cls.INPUT_TYPES()["required"]["allow_api_requests"][1]["default"] is False
    hosted_module = importlib.import_module(hosted_cls.__module__)
    _, image_payload = hosted_module.build_payload(
        "Image to video", "Offline input contract", "ltx-2-5-fast", "1280x720",
        6, 24, False, torch.zeros((1, 32, 32, 3)),
    )
    assert base64.b64decode(image_payload["image_uri"].split(",", 1)[1]).startswith(b"\x89PNG\r\n\x1a\n")

    async def call_native(name, inputs):
        cls = nodes.NODE_CLASS_MAPPINGS[name]
        values, missing, metadata = execution.get_input_data(inputs, cls, "native-smoke")
        assert not missing, (name, missing)
        outputs, ui, expanded, pending = await execution.get_output_data(
            "native-smoke", "native-smoke", cls(), values, v3_data=metadata
        )
        assert not expanded and not pending, name
        return [slot[0] for slot in outputs], ui

    async def video_roundtrip(directory):
        create_inputs = dict(starter["80"]["inputs"], images=torch.zeros((3, 64, 64, 3)))
        (video,), _ = await call_native("CreateVideo", create_inputs)
        save_inputs = dict(starter["90"]["inputs"], video=video, filename_prefix="native-smoke")
        await call_native("SaveVideo", save_inputs)
        files = list(Path(directory).glob("*.mp4"))
        assert len(files) == 1 and files[0].stat().st_size > 0, files
        import av
        with av.open(str(files[0])) as exported:
            frames = list(exported.decode(video=0))
        assert len(frames) == 3 and (frames[0].width, frames[0].height) == (64, 64)
        # Use a synthetic local MP4 instead of running the API transport. This
        # exercises the registered node's real VIDEO wrapper and SaveVideo link.
        with patch.object(hosted_module, "generate", return_value=(files[0], "offline-smoke")):
            (hosted_video, job_id), _ = await call_native("LTXAPIGenerate", graphs["ltx-api-text.json"]["30"]["inputs"])
        assert job_id == "offline-smoke"
        await call_native("SaveVideo", dict(starter["90"]["inputs"], video=hosted_video, filename_prefix="hosted-wrapper-smoke"))
        hosted_files = list(Path(directory).glob("hosted-wrapper-smoke*.mp4"))
        assert len(hosted_files) == 1, hosted_files
        with av.open(str(hosted_files[0])) as exported:
            assert len(list(exported.decode(video=0))) == 3
        return {"format": "MP4", "frames": len(frames), "width": 64, "height": 64, "bytes": files[0].stat().st_size, "hosted_video_wrapper": "passed with local synthetic file; no API transport"}

    old_output = folder_paths.get_output_directory()
    with tempfile.TemporaryDirectory(prefix="ltx-vfx-video-smoke-") as directory:
        folder_paths.set_output_directory(directory)
        try:
            video_result = asyncio.run(video_roundtrip(directory))
        finally:
            folder_paths.set_output_directory(old_output)
    print(json.dumps({
        "weights": "stand-ins; no inference", "effects": results,
        "starter_schema_nodes": len(starter), "native_video_roundtrip": video_result,
        "hosted_graph_schema_nodes": {name: len(graph) for name, graph in graphs.items() if name != "cinemagraph_api.json"},
        "hosted_image_encoding": "real CPU tensor to inline PNG; no API transport",
    }, indent=2))


if __name__ == "__main__":
    main()
