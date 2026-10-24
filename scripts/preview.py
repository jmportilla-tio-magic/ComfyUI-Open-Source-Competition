#!/usr/bin/env python3
"""Serve the design preview on localhost. No inference or credentials required."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class PreviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path in ("/", "/studio"):
            self.send_response(302)
            self.send_header("Location", "/web/studio.html")
            self.end_headers()
            return
        if path == "/ltx-vfx/catalog":
            self.path = "/data/effects.json"
        elif path.startswith("/ltx-vfx/workflows/"):
            name = path.removeprefix("/ltx-vfx/workflows/")
            if name not in ("sdr-to-hdr", "slow-motion-control"):
                self.send_error(404)
                return
            self.path = f"/examples/workflows/{name}.json"
        elif not path.startswith(("/web/", "/data/", "/examples/workflows/")):
            self.send_error(404)
            return
        resolved = Path(self.translate_path(self.path)).resolve()
        if not any(resolved.is_relative_to(ROOT / folder) for folder in ("web", "data", "examples/workflows")):
            self.send_error(404)
            return
        if resolved.is_dir():
            self.send_error(404)
            return
        super().do_GET()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    print(f"OpenPositive design preview: http://127.0.0.1:{args.port}", flush=True)
    print("Media stays in your browser. To generate, install the ComfyUI node.", flush=True)
    try:
        ThreadingHTTPServer(("127.0.0.1", args.port), PreviewHandler).serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
