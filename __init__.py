"""OpenPositive LTX VFX Studio: native ComfyUI nodes and an optional editor UI."""

from .ltx_vfx.nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

# API-mode execution does not depend on the UI or on these read-only routes.
try:
    from .ltx_vfx.routes import register_routes
    register_routes()
except ImportError:
    # The package and its catalog can also be inspected outside ComfyUI.
    pass
