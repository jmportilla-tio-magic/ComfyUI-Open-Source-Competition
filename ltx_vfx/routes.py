"""Read-only catalog/installation discovery for the optional Studio interface."""

from __future__ import annotations

import copy
from pathlib import Path, PurePosixPath

from .catalog import CATALOG, EFFECTS

WORKFLOWS = Path(__file__).resolve().parent.parent / "examples" / "workflows"
SPECIALIST_WORKFLOWS = {"sdr-to-hdr", "slow-motion-control"}


def catalog_payload():
    payload = copy.deepcopy(CATALOG)
    for effect in payload["effects"]:
        effect["studio_mode"] = ("dedicated_workflow" if effect["pipeline"] in ("hdr", "i2v_speed") else "prepare")
        if effect["id"] in SPECIALIST_WORKFLOWS:
            effect["bundled_workflow"] = (WORKFLOWS / f"{effect['id']}.json").is_file()
            effect["workflow_endpoint"] = f"/ltx-vfx/workflows/{effect['id']}"
    return payload


def health_payload():
    import folder_paths
    import nodes

    def filenames(category):
        try:
            return folder_paths.get_filename_list(category)
        except KeyError:
            return []

    installed = filenames("loras")
    by_basename = {PurePosixPath(name.replace("\\", "/")).name for name in installed}
    required_nodes = ["LoraLoaderModelOnly", "CLIPTextEncode", "LTXVConditioning",
                      "EmptyLTXVLatentVideo", "LTXAddVideoICLoRAGuide", "LTXVCropGuides"]
    return {
        "status": "ready" if all(name in nodes.NODE_CLASS_MAPPINGS for name in required_nodes) else "missing_nodes",
        "missing_nodes": [name for name in required_nodes if name not in nodes.NODE_CLASS_MAPPINGS],
        "effects": {effect["id"]: {"installed": effect["filename"] in by_basename,
                                    "filename": effect["filename"]} for effect in EFFECTS},
        "base_assets": [{"role": asset["role"], "required": asset["required"],
                         "filename": PurePosixPath(asset["filename"]).name,
                         "installed": any(PurePosixPath(name).name == PurePosixPath(asset["filename"]).name
                                          for name in filenames(asset["destination"]))}
                        for asset in CATALOG["base_model"]["assets"]],
        "inference_tested": False,
    }


def register_routes():
    from aiohttp import web
    from server import PromptServer

    server = getattr(PromptServer, "instance", None)
    # Comfy's schema/validation tools can import node packages before creating
    # a web server. The graph nodes must remain importable in that environment.
    if server is None:
        return False
    if getattr(server, "_openpositive_vfx_routes_registered", False):
        return True

    @server.routes.get("/ltx-vfx/catalog")
    async def catalog(request):
        return web.json_response(catalog_payload())

    @server.routes.get("/ltx-vfx/health")
    async def health(request):
        return web.json_response(health_payload())

    @server.routes.get("/ltx-vfx/workflows/{effect_id}")
    async def workflow(request):
        effect_id = request.match_info["effect_id"]
        if effect_id not in SPECIALIST_WORKFLOWS:
            raise web.HTTPNotFound(text="No dedicated workflow is registered for this effect.")
        path = WORKFLOWS / f"{effect_id}.json"
        if not path.is_file():
            return web.json_response({
                "error": "workflow_not_downloaded",
                "message": "Download the gated official workflow after accepting the LTX model terms: "
                           f"python scripts/download_models.py --effect {effect_id} --workflows --download. "
                           "Then retry opening the workflow.",
            }, status=404)
        return web.FileResponse(path, headers={"Content-Type": "application/json"})

    server._openpositive_vfx_routes_registered = True
    return True
