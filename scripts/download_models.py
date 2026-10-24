#!/usr/bin/env python3
"""Plan or download explicitly selected, catalogued LTX-2.5 assets.

Plans are read-only. --download uses huggingface_hub and the user's existing
HF_TOKEN/login. Accept gated model terms on Hugging Face before downloading.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Asset:
    repo_id: str
    filename: str
    destination: Path
    role: str


def plan_assets(catalog: dict, ids: list[str], all_effects: bool, base: bool, optional: bool, workflows: bool, comfy_root: Path) -> list[Asset]:
    effects = catalog["effects"]
    by_id = {effect["id"]: effect for effect in effects}
    unknown = set(ids) - set(by_id)
    if unknown:
        raise ValueError(f"Unknown effect(s): {', '.join(sorted(unknown))}. Use --list.")
    selected = effects if all_effects else [by_id[effect_id] for effect_id in dict.fromkeys(ids)]
    models = comfy_root / "models"
    assets = []
    for effect in selected:
        assets.append(Asset(effect["repo_id"], effect["filename"], models / "loras" / Path(effect["filename"]).name, "adapter"))
        for filename in effect.get("companion_files", []):
            if filename.endswith(".safetensors"):
                assets.append(Asset(effect["repo_id"], filename, models / "embeddings" / Path(filename).name, "scene embeddings"))
            elif workflows and filename.endswith(".json"):
                assets.append(Asset(effect["repo_id"], filename, ROOT / "examples" / "workflows" / f"{effect['id']}.json", "official workflow"))
    if base or optional:
        transformers = {effect.get("recommended_transformer") for effect in selected}
        transformers.discard(None)
        if not transformers:
            transformers = {catalog["base_model"]["assets"][0]["filename"]}
        specialist = any(effect.get("pipeline") in {"i2v_speed", "hdr", "ic_lora_two_stage"} for effect in selected)
        for asset in catalog["base_model"]["assets"]:
            needed = asset["required"]
            if asset["role"] in {"transformer", "dev_transformer"}:
                needed = asset["filename"] in transformers
            if specialist and asset["role"] == "audio_vae":
                needed = True
            if any(effect.get("pipeline") in {"i2v_speed", "ic_lora_two_stage"} for effect in selected) and asset["role"] == "spatial_upscaler":
                needed = True
            if needed or optional:
                assets.append(Asset(asset["repo_id"], asset["filename"], models / asset["destination"] / Path(asset["filename"]).name, asset["role"]))
    return list(dict.fromkeys(assets))


def download(assets: list[Asset]) -> None:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError('Install the download helper: pip install -e ".[models]"') from exc
    for asset in assets:
        # No remote code is imported, no repo snapshots, only named catalog files.
        cached = hf_hub_download(repo_id=asset.repo_id, filename=asset.filename)
        if asset.filename.endswith(".json"):
            workflow = json.loads(Path(cached).read_text(encoding="utf-8"))
            if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
                raise ValueError(f"Upstream {asset.filename} is not a ComfyUI canvas workflow.")
        asset.destination.parent.mkdir(parents=True, exist_ok=True)
        # Cached files are complete and verified by huggingface_hub before copying.
        descriptor, temporary = tempfile.mkstemp(prefix=f".{asset.destination.name}.", dir=asset.destination.parent)
        os.close(descriptor)
        try:
            shutil.copyfile(cached, temporary)
            os.replace(temporary, asset.destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print(f"Saved {asset.destination}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--comfy-root", type=Path, default=Path("ComfyUI"), help="ComfyUI installation folder (contains models/)")
    result.add_argument("--effect", action="append", default=[], help="Stable effect ID; repeat to select several")
    result.add_argument("--all", action="store_true", help="Select all 15 catalogued adapters")
    result.add_argument("--base", "--with-base", action="store_true", help="Include recommended transformer, text encoder and VAE assets")
    result.add_argument("--optional-base", action="store_true", help="Include all base assets, including audio VAE and spatial upscaler")
    result.add_argument("--workflows", action="store_true", help="Also retrieve selected effects' official JSON workflows (may be gated)")
    result.add_argument("--download", action="store_true", help="Download the printed plan; otherwise make no changes")
    result.add_argument("--list", action="store_true", help="List effect IDs")
    return result


def main() -> int:
    args = parser().parse_args()
    catalog = json.loads((ROOT / "data" / "effects.json").read_text(encoding="utf-8"))
    if args.list:
        for effect in catalog["effects"]:
            print(f"{effect['id']:24} {effect['name']}")
        return 0
    if not (args.effect or args.all or args.base or args.optional_base):
        parser().error("select --effect ID, --all, --base, or --optional-base (use --list for IDs)")
    try:
        assets = plan_assets(catalog, args.effect, args.all, args.base, args.optional_base, args.workflows, args.comfy_root)
        for asset in assets:
            print(f"{asset.repo_id}/{asset.filename}\n  → {asset.destination} ({asset.role})")
        print(f"\n{len(assets)} files. Gated model access and upstream model licenses apply.")
        if args.download:
            download(assets)
        else:
            print("Plan only. Add --download to fetch these files; no files were changed.")
        return 0
    except Exception as exc:
        print(f"LTX VFX download: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("For gated repositories, accept their terms in Hugging Face and authenticate with HF_TOKEN or hf auth login.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
