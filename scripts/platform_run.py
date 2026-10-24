#!/usr/bin/env python3
"""Run an exported Comfy API workflow with durable submission tracking.

No SDK import or network call occurs for --validate-only. Each --state file
represents one job; reusing it resumes that job instead of creating another.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def read_graph(path: Path) -> dict[str, Any]:
    graph = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(graph, dict) or not graph:
        raise ValueError("Workflow must be a nonempty API-format object.")
    for node_id, node in graph.items():
        if not isinstance(node_id, str) or not isinstance(node, dict):
            raise ValueError("Export with Save (API Format); a canvas workflow is not accepted.")
        if not isinstance(node.get("class_type"), str) or not isinstance(node.get("inputs"), dict):
            raise ValueError(f"Node {node_id!r} needs class_type and inputs; export API format.")
    for node_id, node in graph.items():
        for name, value in node["inputs"].items():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int):
                if value[0] not in graph:
                    raise ValueError(f"Node {node_id} input {name} links to missing node {value[0]}.")
    return graph


def fingerprint(graph: dict[str, Any], asset: Path, node_id: str, input_name: str, target: str) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(graph, sort_keys=True, separators=(",", ":")).encode())
    digest.update(json.dumps([node_id, input_name, target]).encode())
    with asset.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def reserve_state(path: Path, data: dict[str, Any]) -> None:
    """Atomically reserve one submission, including across concurrent callers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("Another process reserved this state file. Rerun to resume once its job ID is recorded.") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def output_filename(name: str, index: int) -> str:
    # Never trust a server-provided relative path as a local destination.
    basename = name.replace("\\", "/").rsplit("/", 1)[-1]
    basename = re.sub(r"[^A-Za-z0-9._-]", "_", basename).strip(".") or "output.bin"
    return f"{index:03d}-{basename}"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("workflow", type=Path, help="Complete workflow exported with Save (API Format)")
    result.add_argument("--asset", type=Path, required=True, help="Local source image/video matching the loader input")
    result.add_argument("--input-node", required=True, help="Source loader node ID in the exported workflow")
    result.add_argument("--input-name", default="image", help="Asset input on the source loader, e.g. image or video")
    result.add_argument("--output-node", action="append", required=True, help="Save/output node ID; repeat for multiple outputs")
    result.add_argument("--state", type=Path, default=Path(".ltx-vfx-jobs/current.json"), help="Durable job record; choose a NEW path for each new render")
    result.add_argument("--output-dir", type=Path, default=Path("renders"))
    result.add_argument("--validate-only", action="store_true", help="Check local graph and inputs without importing SDK or submitting")
    return result


def execute(args: argparse.Namespace) -> list[Path]:
    graph = read_graph(args.workflow)
    if not args.asset.is_file():
        raise ValueError(f"Source asset does not exist: {args.asset}")
    if args.input_node not in graph or args.input_name not in graph[args.input_node]["inputs"]:
        raise ValueError(f"Workflow has no input {args.input_node}.{args.input_name}.")
    for node_id in args.output_node:
        if node_id not in graph:
            raise ValueError(f"Workflow has no output node {node_id}.")
    target = os.environ.get("COMFY_BASE_URL", "").strip() or "https://cloud.comfy.org"
    url = urlsplit(target)
    if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
        raise ValueError("COMFY_BASE_URL must be an HTTP(S) URL without embedded credentials.")
    if args.validate_only:
        print(f"Valid local API graph: {len(graph)} nodes; asset → {args.input_node}.{args.input_name}; outputs: {', '.join(args.output_node)}")
        print("Local structure only; installed node schemas, GPU capacity and execution require a live Comfy validation.")
        return []

    # Lazy import lets validation and unit tests run without optional SDK dependencies.
    try:
        from comfy_sdk import Comfy, Progress, StatusChange
    except ImportError as exc:
        raise RuntimeError('Install platform dependencies: pip install -e ".[platform]"') from exc

    signature = fingerprint(graph, args.asset, args.input_node, args.input_name, target)
    state: dict[str, Any] = {}
    if args.state.exists():
        state = json.loads(args.state.read_text(encoding="utf-8"))
        if state.get("fingerprint") != signature:
            raise ValueError("This state file belongs to a different workflow, source, or deployment. Choose a new --state path.")
        if not state.get("job_id"):
            raise RuntimeError("A previous submission has an unknown outcome. Check the deployment job list before choosing a new state file; this script will not resubmit it.")

    with Comfy() as client:
        if state.get("job_id"):
            job = client.jobs.get(state["job_id"])
            print(f"Resuming job {job.id}")
        else:
            workflow = client.workflows.from_json(graph)
            workflow.set_input(args.input_node, args.input_name, client.assets.from_file(str(args.asset)))
            state = {"version": 1, "fingerprint": signature, "idempotency_key": str(uuid.uuid4()), "status": "submitting"}
            reserve_state(args.state, state)
            # Intentionally one submit. A dropped response can still mean a billed job exists.
            job = client.submit(workflow, idempotency_key=state["idempotency_key"])
            state.update(job_id=job.id, status="submitted")
            save_state(args.state, state)
            print(f"Submitted job {job.id}")
        try:
            for event in job.events():
                if isinstance(event, Progress):
                    print(f"{event.value:.0%} {event.message or ''}", flush=True)
                elif isinstance(event, StatusChange):
                    print(f"Status: {event.status}", flush=True)
            job.result()  # Polling-backed authoritative success/failure check.
            state["status"] = "succeeded"
            save_state(args.state, state)
        except Exception:
            # Keep job_id so rerunning resumes retrieval; never submit as error recovery.
            state["status"] = "check_job"
            save_state(args.state, state)
            raise
        outputs = []
        for node_id in args.output_node:
            outputs.extend(job.get_outputs(node_id))
        if not outputs:
            raise RuntimeError("The job succeeded but selected output nodes returned no files. Verify --output-node IDs.")
        job_id = str(job.id)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", job_id):
            raise RuntimeError("Server returned an invalid job ID for the output directory.")
        output_dir = args.output_dir / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for index, output in enumerate(outputs):
            destination = output_dir / output_filename(output.name, index)
            descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=output_dir)
            os.close(descriptor)
            try:
                output.to_file(temporary)
                os.replace(temporary, destination)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            written.append(destination)
            print(f"Saved {destination}")
        return written


def main() -> int:
    try:
        execute(parser().parse_args())
        return 0
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"LTX VFX: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
