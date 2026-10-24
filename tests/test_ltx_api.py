"""Direct LTX API contracts, using fake HTTP/Comfy objects only."""
from __future__ import annotations

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

spec = importlib.util.spec_from_file_location("ltx_api_test_module", Path(__file__).parents[1] / "ltx_vfx/ltx_api.py")
api = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = api
spec.loader.exec_module(api)


class PayloadTests(unittest.TestCase):
    def payload(self, **changes):
        values = dict(mode="Text to video", prompt="A slow aerial shot", model="ltx-2-5-fast", resolution="1920x1080", duration_seconds=6, fps=24, generate_audio=False)
        values.update(changes)
        return api.build_payload(**values)

    def test_text_payload_has_no_image_or_lora(self):
        endpoint, payload = self.payload(image=object())
        self.assertEqual(endpoint, "text-to-video")
        self.assertNotIn("image_uri", payload)
        self.assertNotIn("lora", payload)
        self.assertIs(payload["generate_audio"], False)

    def test_auto_duration_sent_as_null(self):
        self.assertIsNone(self.payload(duration_seconds=0)[1]["duration"])

    def test_model_specific_duration_validation(self):
        self.payload(duration_seconds=20)
        for overrides in ({"model": "ltx-2-5-pro"}, {"fps": 48}, {"resolution": "3840x2160"}):
            with self.subTest(**overrides), self.assertRaisesRegex(ValueError, "above 10"):
                self.payload(duration_seconds=20, **overrides)

    def test_unsupported_values_fail_before_network(self):
        for override in ({"fps": 30}, {"resolution": "1024x1024"}, {"model": "custom-lora"}, {"duration_seconds": 7}, {"prompt": ""}, {"prompt": "x" * 5001}):
            with self.subTest(**override), self.assertRaises(ValueError):
                self.payload(**override)

    def test_image_mode_requires_exactly_one_image(self):
        for image in (None, types.SimpleNamespace(shape=(2, 32, 32, 3))):
            with self.assertRaisesRegex(ValueError, "exactly one"):
                self.payload(mode="Image to video", image=image)
        with patch.object(api, "_image_uri", return_value="data:image/png;base64,dGVzdA=="):
            endpoint, payload = self.payload(mode="Image to video", image=object())
        self.assertEqual(endpoint, "image-to-video")
        self.assertTrue(payload["image_uri"].startswith("data:image/png;base64,"))


class FakeTransport:
    def __init__(self, token):
        self.token = token
        self.calls = []
        self.pending = False
        self.submit_error = None
        self.download_error = None
    def submit(self, endpoint, payload):
        self.calls.append(("submit", endpoint, payload))
        if self.submit_error:
            raise self.submit_error
        return {"id": "job-123"}
    def status(self, endpoint, job_id, timeout):
        self.calls.append(("status", endpoint, job_id))
        if self.pending:
            self.pending = False
            return {"status": "processing"}
        return {"status": "completed", "result": {"video_url": "https://storage.googleapis.com/example/video.mp4"}}
    def download(self, url, destination, deadline):
        self.calls.append(("download", url))
        if self.download_error:
            raise self.download_error
        destination.write_bytes(b"video-test-data")


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.transport = FakeTransport("secret-token")
        self.kwargs = dict(output_root=self.root, mode="Text to video", prompt="A slow aerial shot", model="ltx-2-5-fast", resolution="1920x1080", duration_seconds=6, fps=24, generate_audio=True, allow_api_requests=True, render_id=0, timeout_seconds=30, transport_factory=lambda token: self.transport)
        self.env = patch.dict(os.environ, {"LTX_API_KEY": "secret-token", "LTXV_API_KEY": ""})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.sleep = patch.object(api, "_sleep")
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def test_requests_disabled_by_default(self):
        self.kwargs["allow_api_requests"] = False
        with self.assertRaisesRegex(ValueError, "requests are disabled"):
            api.generate(**self.kwargs)
        self.assertEqual(self.transport.calls, [])
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertFalse(api.LTXAPIGenerate.INPUT_TYPES()["required"]["allow_api_requests"][1]["default"])

    def test_missing_server_key_never_connects(self):
        with patch.dict(os.environ, {"LTX_API_KEY": "", "LTXV_API_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "Set LTX_API_KEY"):
                api.generate(**self.kwargs)
        self.assertEqual(self.transport.calls, [])

    def test_alias_key_supported_without_key_widget(self):
        self.kwargs["transport_factory"] = lambda token: self.assertEqual(token, "alias-token") or self.transport
        with patch.dict(os.environ, {"LTX_API_KEY": "", "LTXV_API_KEY": "alias-token"}):
            api.generate(**self.kwargs)
        self.assertNotIn("api_key", api.LTXAPIGenerate.INPUT_TYPES()["required"])

    def test_submit_poll_download_and_reuse_are_durable(self):
        self.transport.pending = True
        path, job_id = api.generate(**self.kwargs)
        self.assertEqual(job_id, "job-123")
        self.assertEqual(path.read_bytes(), b"video-test-data")
        api.generate(**self.kwargs)
        self.assertEqual(len([x for x in self.transport.calls if x[0] == "submit"]), 1)
        records = list((self.root / "ltx_api/.jobs").glob("*.json"))
        self.assertEqual(len(records), 1)
        text = records[0].read_text()
        self.assertNotIn("secret-token", text)
        self.assertNotIn("aerial", text)
        self.assertEqual(json.loads(text)["status"], "completed")

    def test_ambiguous_submit_does_not_repeat(self):
        self.transport.submit_error = api.TransportError("Network failure", retryable=True)
        with self.assertRaisesRegex(RuntimeError, "unknown"):
            api.generate(**self.kwargs)
        with self.assertRaisesRegex(RuntimeError, "unknown outcome"):
            api.generate(**self.kwargs)
        self.assertEqual(len([x for x in self.transport.calls if x[0] == "submit"]), 1)

    def test_definitive_rejection_releases_record_for_manual_retry(self):
        self.transport.submit_error = api.TransportError("HTTP 401", definitive_rejection=True)
        with self.assertRaisesRegex(RuntimeError, "request was rejected"):
            api.generate(**self.kwargs)
        self.assertEqual(list((self.root / "ltx_api/.jobs").glob("*.json")), [])

    def test_resume_job_never_submits_or_requires_source_again(self):
        self.kwargs.update(mode="Image to video", image=None, resume_job_id="previous-job")
        _, job_id = api.generate(**self.kwargs)
        self.assertEqual(job_id, "previous-job")
        self.assertFalse(any(x[0] == "submit" for x in self.transport.calls))
        self.assertIn(("status", "image-to-video", "previous-job"), self.transport.calls)

    def test_completed_explicit_resume_reuses_local_output_without_remote_lookup(self):
        self.kwargs["resume_job_id"] = "previous-job"
        expected = api.generate(**self.kwargs)
        calls_before = list(self.transport.calls)
        self.assertEqual(api.generate(**self.kwargs), expected)
        self.assertEqual(self.transport.calls, calls_before)
        self.assertFalse(any(call[0] == "submit" for call in self.transport.calls))

    def test_completed_resume_redownloads_if_local_output_is_missing(self):
        self.kwargs["resume_job_id"] = "previous-job"
        path, _ = api.generate(**self.kwargs)
        path.unlink()
        restored, _ = api.generate(**self.kwargs)
        self.assertTrue(restored.is_file())
        self.assertEqual(sum(call[0] == "download" for call in self.transport.calls), 2)
        self.assertFalse(any(call[0] == "submit" for call in self.transport.calls))

    def test_resume_rejects_mismatching_local_record_without_overwriting_it(self):
        self.kwargs["resume_job_id"] = "previous-job"
        api.generate(**self.kwargs)
        record = next((self.root / "ltx_api/.jobs").glob("*.json"))
        original = json.loads(record.read_text())
        original["job_id"] = "different-job"
        record.write_text(json.dumps(original))
        calls_before = list(self.transport.calls)
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            api.generate(**self.kwargs)
        self.assertEqual(json.loads(record.read_text()), original)
        self.assertEqual(self.transport.calls, calls_before)

    def test_download_failure_reports_recoverable_job(self):
        self.transport.download_error = RuntimeError("Download interrupted")
        with self.assertRaisesRegex(RuntimeError, "Job ID: job-123.*resume_job_id"):
            api.generate(**self.kwargs)
        self.transport.download_error = None
        api.generate(**self.kwargs)
        self.assertEqual(len([x for x in self.transport.calls if x[0] == "submit"]), 1)

    def test_record_write_failure_preserves_accepted_job_id_in_error(self):
        with patch.object(api, "_write_state", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(RuntimeError, "accepted job job-123.*resume_job_id"):
                api.generate(**self.kwargs)
        self.assertEqual(len([x for x in self.transport.calls if x[0] == "submit"]), 1)

    def test_timeout_retains_job_and_never_resubmits(self):
        self.transport.status = lambda *args: {"status": "processing"}
        with patch.object(api.time, "monotonic", side_effect=[0, 0, 31]):
            with self.assertRaisesRegex(RuntimeError, "Timed out.*job-123"):
                api.generate(**self.kwargs)
        self.assertEqual(len([x for x in self.transport.calls if x[0] == "submit"]), 1)

    def test_cancellation_keeps_job_for_later_recovery(self):
        class InterruptProcessingException(Exception):
            pass
        with patch.object(api, "_check_interrupt", side_effect=[None, InterruptProcessingException()]):
            with self.assertRaises(InterruptProcessingException):
                api.generate(**self.kwargs)
        record = json.loads(next((self.root / "ltx_api/.jobs").glob("*.json")).read_text())
        self.assertEqual(record["job_id"], "job-123")
        api.generate(**self.kwargs)
        self.assertEqual(len([x for x in self.transport.calls if x[0] == "submit"]), 1)

    def test_node_returns_native_video(self):
        folder_paths = types.SimpleNamespace(get_output_directory=lambda: str(self.root))
        latest = types.SimpleNamespace(InputImpl=types.SimpleNamespace(VideoFromFile=lambda path: ("native-video", path)))
        with patch.dict(sys.modules, {"folder_paths": folder_paths, "comfy_api.latest": latest}), patch.object(api, "generate", return_value=(self.root / "done.mp4", "job-1")):
            video, job_id = api.LTXAPIGenerate().execute()
        self.assertEqual(video, ("native-video", str(self.root / "done.mp4")))
        self.assertEqual(job_id, "job-1")


class Response(io.BytesIO):
    def __init__(self, content):
        super().__init__(content)
        self.headers = {"Content-Length": str(len(content))}


class HTTPContracts(unittest.TestCase):
    def setUp(self):
        self.transport = api.HTTPTransport("private-key")
        self.requests = []
        def open_(request, timeout):
            self.requests.append(request)
            if request.get_method() == "POST":
                return Response(b'{"id":"job-123"}')
            return Response(b'\x00\x00\x00\x18ftypisom' + b'0' * 20)
        self.transport._opener = types.SimpleNamespace(open=open_)

    def test_auth_only_goes_to_fixed_api_origin(self):
        self.transport.submit("text-to-video", {"prompt": "test"})
        with tempfile.TemporaryDirectory() as root:
            self.transport.download("https://storage.googleapis.com/video.mp4", Path(root) / "video.mp4", api.time.monotonic() + 30)
        self.assertEqual(self.requests[0].full_url, "https://api.ltx.io/v2/text-to-video")
        self.assertEqual(self.requests[0].get_header("Authorization"), "Bearer private-key")
        self.assertIsNone(self.requests[1].get_header("Authorization"))

    def test_download_limit_is_atomic(self):
        with tempfile.TemporaryDirectory() as root, patch.object(api, "MAX_DOWNLOAD_BYTES", 10):
            destination = Path(root) / "video.mp4"
            with self.assertRaisesRegex(api.TransportError, "download limit"):
                self.transport.download("https://storage.googleapis.com/video.mp4", destination, api.time.monotonic() + 30)
            self.assertFalse(destination.exists())
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_non_public_or_insecure_outputs_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            for url in ("http://example.com/video.mp4", "https://127.0.0.1/video.mp4", "https://localhost/video.mp4", "https://key@example.com/video.mp4"):
                with self.subTest(url=url), self.assertRaises(api.TransportError):
                    self.transport.download(url, Path(root) / "video.mp4", api.time.monotonic() + 30)
        self.assertEqual(self.requests, [])

    def test_truncated_output_does_not_replace_existing_file(self):
        def open_truncated(request, timeout):
            response = Response(b'\x00\x00\x00\x18ftypisom' + b'0' * 20)
            response.headers["Content-Length"] = "1000"
            return response
        self.transport._opener = types.SimpleNamespace(open=open_truncated)
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "video.mp4"
            destination.write_bytes(b"existing complete output")
            with self.assertRaisesRegex(api.TransportError, "incomplete"):
                self.transport.download("https://storage.googleapis.com/video.mp4", destination, api.time.monotonic() + 30)
            self.assertEqual(destination.read_bytes(), b"existing complete output")
            self.assertEqual(list(Path(root).iterdir()), [destination])

    def test_invalid_content_length_is_rejected(self):
        for header in ("not-a-number", "-1"):
            def open_invalid(request, timeout):
                response = Response(b'\x00\x00\x00\x18ftypisom' + b'0' * 20)
                response.headers["Content-Length"] = header
                return response
            self.transport._opener = types.SimpleNamespace(open=open_invalid)
            with self.subTest(header=header), tempfile.TemporaryDirectory() as root:
                destination = Path(root) / "video.mp4"
                with self.assertRaisesRegex(api.TransportError, "invalid Content-Length"):
                    self.transport.download("https://storage.googleapis.com/video.mp4", destination, api.time.monotonic() + 30)
                self.assertEqual(list(Path(root).iterdir()), [])


class ExampleContracts(unittest.TestCase):
    def test_examples_are_complete_and_requests_default_off(self):
        folder = Path(__file__).parents[1] / "examples/workflows"
        for name in ("text", "image"):
            graph = json.loads((folder / f"ltx-api-{name}.json").read_text())
            self.assertEqual(graph["30"]["class_type"], "LTXAPIGenerate")
            self.assertIs(graph["30"]["inputs"]["allow_api_requests"], False)
            self.assertEqual(graph["90"]["inputs"]["video"], ["30", 0])
            self.assertNotIn("api_key", graph["30"]["inputs"])
            if name == "image":
                self.assertEqual(graph["30"]["inputs"]["image"], ["10", 0])


if __name__ == "__main__":
    unittest.main()
