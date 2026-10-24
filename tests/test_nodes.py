"""Contract tests using lightweight native-node doubles; no GPU required."""

import json
import sys
import types
import unittest
from unittest.mock import patch

from ltx_vfx.catalog import get_effect
from ltx_vfx.nodes import LTXVFXApplyEffect, LTXVFXCropGuides, LTXVFXStudio, _node, resolve_lora_name
from ltx_vfx.routes import catalog_payload, register_routes


class Image:
    def __init__(self, frames=97):
        self.shape = (frames, 448, 768, 3)

    def __getitem__(self, key):
        return Image(len(range(self.shape[0])[key]))

    def repeat(self, frames, *_):
        return Image(frames)


class NativeDouble:
    def __init__(self):
        self.calls = []

    def __call__(self, name, **inputs):
        self.calls.append((name, inputs))
        if name == "LoraLoaderModelOnly":
            return ("adapted-model",)
        if name == "CLIPTextEncode":
            return ([inputs["text"]],)
        if name == "LTXVConditioning":
            return inputs["positive"], inputs["negative"]
        if name == "EmptyLTXVLatentVideo":
            return ({"samples": "empty"},)
        if name == "LTXVImgToVideo":
            return inputs["positive"], inputs["negative"], {"samples": "i2v"}
        if name == "LTXAddVideoICLoRAGuide":
            return inputs["positive"], inputs["negative"], {"samples": "guided"}
        if name == "LTXVCropGuides":
            return inputs["positive"], inputs["negative"], {"samples": "cropped"}
        raise AssertionError(name)


class NativeContracts(unittest.TestCase):
    def setUp(self):
        self.native = NativeDouble()
        self.native_patch = patch("ltx_vfx.nodes._node", self.native)
        self.lora_patch = patch("ltx_vfx.nodes.resolve_lora_name", lambda effect: effect["filename"])
        self.native_patch.start()
        self.lora_patch.start()
        self.addCleanup(self.native_patch.stop)
        self.addCleanup(self.lora_patch.stop)

    def prepare(self, **kwargs):
        settings = dict(model="model", clip="clip", vae="vae", source=Image(), effect="day-to-night")
        settings.update(kwargs)
        return LTXVFXStudio().prepare(**settings)

    def test_video_prepares_actual_model_and_native_reference(self):
        model, positive, negative, latent, info = self.prepare(prompt="Moonlit street")
        self.assertEqual(model, "adapted-model")
        self.assertEqual(positive, ["Moonlit street"])
        self.assertEqual(latent, {"samples": "guided"})
        guide = [args for name, args in self.native.calls if name == "LTXAddVideoICLoRAGuide"][0]
        self.assertEqual(guide["image"].shape[0], 97)
        self.assertEqual(guide["frame_idx"], 0)
        self.assertEqual(json.loads(info)["status"], "prepared")

    def test_alpha_forces_empty_positive_and_enforces_limits(self):
        out = self.prepare(effect="alpha-gen", prompt="make it blue")
        self.assertEqual(out[1], [""])
        with self.assertRaisesRegex(ValueError, "at most 145"):
            self.prepare(effect="alpha-gen", frames=153, source=Image(153))

    def test_short_video_never_silently_pads_or_repeats(self):
        with self.assertRaisesRegex(ValueError, "Source has 49 frames"):
            self.prepare(source=Image(49))
        self.assertEqual(self.native.calls, [])

    def test_cinemagraph_uses_i2v_and_adds_trigger(self):
        out = self.prepare(effect="cinemagraph", source=Image(1), prompt="Steam moves")
        self.assertEqual(out[1], ["CINEMAGRAPH_MOTION, Steam moves"])
        names = [name for name, _ in self.native.calls]
        self.assertIn("LTXVImgToVideo", names)
        self.assertNotIn("LTXAddVideoICLoRAGuide", names)

    def test_sheet_is_explicitly_repeated_and_minimum_duration_checked(self):
        self.prepare(effect="ingredients", source=Image(1), frames=121)
        guide = [args for name, args in self.native.calls if name == "LTXAddVideoICLoRAGuide"][0]
        self.assertEqual(guide["image"].shape[0], 121)
        with self.assertRaisesRegex(ValueError, "at least 121"):
            self.prepare(effect="ingredients", source=Image(1), frames=97)

    def test_layout_requires_art_directed_frame_and_places_it_at_minus_one(self):
        with self.assertRaisesRegex(ValueError, "first_frame"):
            self.prepare(effect="layout-to-render", height=448)
        out = self.prepare(effect="layout-to-render", first_frame=Image(1), height=448)
        guides = [args for name, args in self.native.calls if name == "LTXAddVideoICLoRAGuide"]
        self.assertEqual([guide["frame_idx"] for guide in guides], [0, -1])
        empty = [args for name, args in self.native.calls if name == "EmptyLTXVLatentVideo"][0]
        self.assertEqual((empty["width"], empty["height"]), (384, 224))
        self.assertEqual(json.loads(out[-1])["stage1_width"], 384)

    def test_upscale_passes_real_reference_downscale_factor(self):
        self.prepare(effect="pixel-spatial-upscaler", width=768, height=512)
        guide = [args for name, args in self.native.calls if name == "LTXAddVideoICLoRAGuide"][0]
        self.assertEqual(guide["latent_downscale_factor"], 2.0)
        with self.assertRaisesRegex(ValueError, "multiple of 64"):
            self.prepare(effect="pixel-spatial-upscaler", height=448, width=800)

    def test_specialist_pipelines_do_not_silently_run_generic_inference(self):
        for effect in ("sdr-to-hdr", "slow-motion-control"):
            with self.subTest(effect=effect), self.assertRaisesRegex(ValueError, "dedicated workflow"):
                self.prepare(effect=effect)
        self.assertEqual(self.native.calls, [])

    def test_crop_uses_native_guide_removal(self):
        self.assertEqual(LTXVFXCropGuides().crop("p", "n", {}), ("p", "n", {"samples": "cropped"}))

    def test_tiled_effects_prepare_matching_temporal_window_guides(self):
        self.prepare(effect="restore")
        guide = [args for name, args in self.native.calls if name == "LTXAddVideoICLoRAGuide"][0]
        self.assertTrue(guide["use_streaming"])
        self.assertEqual(guide["tile_frames"], 97)

    def test_adapter_remains_available_for_specialist_graph(self):
        out = LTXVFXApplyEffect().apply("model", "sdr-to-hdr", 1.0)
        self.assertEqual(out[0], "adapted-model")
        self.assertIn("HDR", json.loads(out[1])["notes"][0])

    def test_nonfinite_and_bad_frame_grids_fail_before_runtime(self):
        for settings in ({"strength": float("nan")}, {"frames": 96}, {"frame_rate": 0}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.prepare(**settings)
        self.assertEqual(self.native.calls, [])

    def test_effect_specific_strength_limits_apply_to_api_calls(self):
        with self.assertRaisesRegex(ValueError, "between 0.5 and 1.5"):
            self.prepare(effect="cinemagraph", source=Image(1), strength=2.0)
        with self.assertRaisesRegex(ValueError, "between 0.5 and 1.5"):
            LTXVFXApplyEffect().apply("model", "cinemagraph", 0.0)


class DiscoveryContracts(unittest.TestCase):
    def test_route_registration_is_optional_and_idempotent(self):
        class Routes:
            def __init__(self):
                self.paths = []

            def get(self, path):
                self.paths.append(path)
                return lambda function: function

        prompt_server = types.SimpleNamespace(instance=None)
        fake_modules = {
            "aiohttp": types.SimpleNamespace(web=types.SimpleNamespace()),
            "server": types.SimpleNamespace(PromptServer=prompt_server),
        }
        with patch.dict(sys.modules, fake_modules):
            self.assertFalse(register_routes())
            prompt_server.instance = types.SimpleNamespace(routes=Routes())
            self.assertTrue(register_routes())
            self.assertTrue(register_routes())
            self.assertEqual(prompt_server.instance.routes.paths, [
                "/ltx-vfx/catalog", "/ltx-vfx/health", "/ltx-vfx/workflows/{effect_id}",
            ])

    def test_runtime_adapter_accepts_v1_and_v3_native_node_outputs(self):
        class V1:
            FUNCTION = "run"

            def run(self, value):
                return {"result": (value,)}

        class V3:
            @classmethod
            def execute(cls, value):
                return types.SimpleNamespace(result=(value,))

        class AsyncNode:
            async def execute(self):
                return ("unsupported",)

        module = types.SimpleNamespace(NODE_CLASS_MAPPINGS={"V1": V1, "V3": V3, "Async": AsyncNode})
        with patch.dict(sys.modules, {"nodes": module}):
            self.assertEqual(_node("V1", value=4), (4,))
            self.assertEqual(_node("V3", value=5), (5,))
            with self.assertRaisesRegex(RuntimeError, "Update ComfyUI"):
                _node("Missing")
            with self.assertRaisesRegex(RuntimeError, "changed to async"):
                _node("Async")

    def test_subfolder_model_resolution_and_ambiguity(self):
        effect = get_effect("day-to-night")
        filename = effect["filename"]
        module = types.SimpleNamespace(get_filename_list=lambda _: [f"creative-lab/{filename}"])
        with patch.dict(sys.modules, {"folder_paths": module}):
            self.assertEqual(resolve_lora_name(effect), f"creative-lab/{filename}")
            module.get_filename_list = lambda _: [f"one/{filename}", f"two/{filename}"]
            with self.assertRaisesRegex(ValueError, "Multiple copies"):
                resolve_lora_name(effect)
            module.get_filename_list = lambda _: []
            with self.assertRaisesRegex(FileNotFoundError, "models/loras"):
                resolve_lora_name(effect)

    def test_catalog_distinguishes_preparation_from_dedicated_workflows(self):
        effects = {effect["id"]: effect for effect in catalog_payload()["effects"]}
        self.assertEqual(len(effects), 15)
        self.assertEqual(effects["sdr-to-hdr"]["studio_mode"], "dedicated_workflow")
        self.assertEqual(effects["day-to-night"]["studio_mode"], "prepare")


if __name__ == "__main__":
    unittest.main()
