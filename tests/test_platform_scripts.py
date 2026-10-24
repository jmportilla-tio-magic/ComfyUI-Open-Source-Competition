"""Offline checks for deployment helpers; no network calls or GPU required."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = load_script("platform_run")
downloader = load_script("download_models")


class PlatformRunnerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name)
        self.graph = {"10": {"class_type": "LoadVideo", "inputs": {"video": "clip.mp4"}}, "90": {"class_type": "SaveVideo", "inputs": {"video": ["10", 0]}}}
        self.workflow = self.path / "workflow.json"
        self.workflow.write_text(json.dumps(self.graph))
        self.asset = self.path / "plate.mp4"
        self.asset.write_bytes(b"local test content, not a real mp4")
        self.args = runner.parser().parse_args([str(self.workflow), "--asset", str(self.asset), "--input-node", "10", "--input-name", "video", "--output-node", "90", "--state", str(self.path / "state.json"), "--output-dir", str(self.path / "renders")])
        self.prints = contextlib.redirect_stdout(io.StringIO())
        self.prints.__enter__()
        self.addCleanup(self.prints.__exit__, None, None, None)

    def fake_sdk(self):
        calls = []
        class Job:
            id = "test-job"
            def events(self): return iter(())
            def result(self): calls.append("result"); return self
            def get_outputs(self, node_id):
                calls.append(("output", node_id))
                def save(path): Path(path).write_bytes(b"result")
                return [types.SimpleNamespace(name="../../result.mp4", to_file=save)]
        class Client:
            def __init__(self):
                self.workflows = types.SimpleNamespace(from_json=lambda graph: types.SimpleNamespace(set_input=lambda *args: calls.append(("input", args))))
                self.assets = types.SimpleNamespace(from_file=lambda path: path)
                self.jobs = types.SimpleNamespace(get=lambda job_id: calls.append(("get", job_id)) or Job())
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def submit(self, workflow, **kwargs): calls.append("submit"); return Job()
        module = types.SimpleNamespace(Comfy=Client, Progress=type("Progress", (), {}), StatusChange=type("StatusChange", (), {}))
        return module, calls

    def test_canvas_format_rejected(self):
        self.workflow.write_text(json.dumps({"nodes": []}))
        with self.assertRaisesRegex(ValueError, "API Format"):
            runner.read_graph(self.workflow)

    def test_dangling_link_rejected(self):
        self.graph["90"]["inputs"]["video"] = ["404", 0]
        self.workflow.write_text(json.dumps(self.graph))
        with self.assertRaisesRegex(ValueError, "missing node"):
            runner.read_graph(self.workflow)

    def test_validate_only_never_imports_or_submits_sdk(self):
        self.args.validate_only = True
        with patch.dict(sys.modules, {"comfy_sdk": None}):
            self.assertEqual(runner.execute(self.args), [])
        self.assertFalse(self.args.state.exists())

    def test_submit_once_then_resume(self):
        sdk, calls = self.fake_sdk()
        with patch.dict(sys.modules, {"comfy_sdk": sdk}), patch.dict(os.environ, {"COMFY_BASE_URL": "http://127.0.0.1:8189"}):
            files = runner.execute(self.args)
            runner.execute(self.args)
        self.assertEqual(calls.count("submit"), 1)
        self.assertIn(("get", "test-job"), calls)
        self.assertEqual(files[0].name, "000-result.mp4")
        self.assertEqual(files[0].read_bytes(), b"result")
        self.assertEqual(json.loads(self.args.state.read_text())["status"], "succeeded")

    def test_unknown_submit_outcome_never_retries(self):
        signature = runner.fingerprint(self.graph, self.asset, "10", "video", "http://127.0.0.1:8189")
        self.args.state.write_text(json.dumps({"fingerprint": signature, "idempotency_key": "held"}))
        sdk, calls = self.fake_sdk()
        with patch.dict(sys.modules, {"comfy_sdk": sdk}), patch.dict(os.environ, {"COMFY_BASE_URL": "http://127.0.0.1:8189"}):
            with self.assertRaisesRegex(RuntimeError, "unknown outcome"):
                runner.execute(self.args)
        self.assertNotIn("submit", calls)

    def test_changed_source_does_not_reuse_job(self):
        sdk, _ = self.fake_sdk()
        with patch.dict(sys.modules, {"comfy_sdk": sdk}), patch.dict(os.environ, {"COMFY_BASE_URL": "http://127.0.0.1:8189"}):
            runner.execute(self.args)
            self.asset.write_bytes(b"different plate")
            with self.assertRaisesRegex(ValueError, "different workflow"):
                runner.execute(self.args)

    def test_concurrent_reservation_is_exclusive(self):
        runner.reserve_state(self.args.state, {"idempotency_key": "first"})
        with self.assertRaisesRegex(RuntimeError, "Another process"):
            runner.reserve_state(self.args.state, {"idempotency_key": "second"})
        self.assertEqual(json.loads(self.args.state.read_text())["idempotency_key"], "first")

    def test_server_filename_cannot_escape_output_dir(self):
        self.assertEqual(runner.output_filename("..\\..\\malicious.mp4", 2), "002-malicious.mp4")


class DownloaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / "data" / "effects.json").read_text())

    def plan(self, ids, **overrides):
        options = dict(all_effects=False, base=False, optional=False, workflows=False, comfy_root=Path("/test/ComfyUI"))
        options.update(overrides)
        return downloader.plan_assets(self.catalog, ids, **options)

    def test_all_collection_adapters_selected(self):
        plan = self.plan([], all_effects=True)
        self.assertEqual(len([a for a in plan if a.role == "adapter"]), 15)

    def test_hardware_assets_not_downloaded_implicitly(self):
        plan = self.plan(["clean-plate"])
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].destination.parent, Path("/test/ComfyUI/models/loras"))

    def test_dev_effect_uses_recommended_dev_transformer(self):
        transformers = [a.filename for a in self.plan(["day-to-night"], base=True) if "transformer" in a.role]
        self.assertEqual(transformers, ["diffusion_models/ltx-2.5-22b-dev-transformer-bf16.safetensors"])

    def test_hdr_scene_embeddings_and_slow_motion_workflow(self):
        hdr = self.plan(["sdr-to-hdr"])
        self.assertTrue(any(a.destination.parent.name == "embeddings" for a in hdr))
        slow = self.plan(["slow-motion-control"], workflows=True, base=True)
        self.assertTrue(any(a.destination.name == "slow-motion-control.json" for a in slow))
        self.assertTrue(any(a.role == "audio_vae" for a in slow))
        self.assertTrue(any(a.role == "spatial_upscaler" for a in slow))

    def test_unknown_effect_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown effect"):
            self.plan(["made-up"])


class StarterGraphTests(unittest.TestCase):
    def test_cinemagraph_starter_stays_aligned_with_catalog(self):
        graph = runner.read_graph(ROOT / "examples/workflows/cinemagraph_api.json")
        catalog = json.loads((ROOT / "data/effects.json").read_text())
        effect = next(item for item in catalog["effects"] if item["id"] == "cinemagraph")
        studio = graph["30"]["inputs"]
        self.assertEqual(graph["30"]["class_type"], "LTXVFXStudio")
        self.assertEqual(studio["effect"], effect["name"])
        self.assertEqual(graph["20"]["inputs"]["unet_name"], Path(effect["recommended_transformer"]).name)
        self.assertEqual(graph["43"]["inputs"]["steps"], effect["defaults"]["steps"])
        self.assertEqual(graph["41"]["inputs"]["cfg"], effect["defaults"]["cfg"])
        self.assertEqual(studio["frames"], effect["defaults"]["frames"])
        self.assertEqual(graph["90"]["class_type"], "SaveVideo")
        # The exported output must remain connected through decode + sampling
        # to the source and Studio rather than becoming an inert recipe fragment.
        reached = set()
        def walk(node_id):
            if node_id in reached:
                return
            reached.add(node_id)
            for value in graph[node_id]["inputs"].values():
                if isinstance(value, list) and len(value) == 2:
                    walk(value[0])
        walk("90")
        self.assertTrue({"10", "30", "50", "60", "70"}.issubset(reached))


if __name__ == "__main__":
    unittest.main()
