import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { applyRecipeToGraph, bridgeToken, recipeFromNode } from "./graph-bridge.js";

let currentDialog;
let opening;

async function createStudio(node) {
  const response = await api.fetchApi("/ltx-vfx/catalog");
  if (!response.ok) throw new Error("OpenPositive catalog is unavailable. Restart ComfyUI after installing the node.");
  const { effects } = await response.json();
  const token = bridgeToken();
  const dialog = document.createElement("dialog");
  dialog.setAttribute("aria-label", "OpenPositive LTX VFX Studio");
  Object.assign(dialog.style, {
    padding: "0", border: "1px solid #ffffff33", borderRadius: "12px", background: "#131416",
    width: "min(1560px, 96vw)", height: "94vh", maxWidth: "96vw", maxHeight: "94vh", overflow: "hidden",
  });
  const close = document.createElement("button");
  close.textContent = "Close studio ×";
  close.setAttribute("aria-label", "Close VFX studio");
  Object.assign(close.style, {
    position: "absolute", right: "16px", top: "22px", background: "#23262a", color: "#f7f7f8",
    border: "1px solid #ffffff33", borderRadius: "5px", fontSize: "11px", padding: "6px 9px", cursor: "pointer", zIndex: 2,
  });
  close.addEventListener("focus", () => { close.style.outline = "2px solid #d1fe17"; close.style.outlineOffset = "3px"; });
  close.addEventListener("blur", () => { close.style.outline = ""; });
  const frame = document.createElement("iframe");
  frame.title = "LTX VFX Studio";
  const frameUrl = new URL("./studio.html", import.meta.url);
  frameUrl.searchParams.set("bridge", token);
  frameUrl.searchParams.set("apiBase", new URL(api.apiURL("/ltx-vfx/"), location.href).href);
  frame.src = frameUrl.href;
  frame.allow = "fullscreen";
  Object.assign(frame.style, { width: "100%", height: "100%", border: "0" });
  const post = data => frame.contentWindow.postMessage({ ...data, token }, location.origin);
  const onMessage = event => {
    if (event.origin !== location.origin || event.source !== frame.contentWindow || event.data?.token !== token) return;
    if (event.data.type === "openpositive:ready") post({ type: "openpositive:init", nodeId: node?.id, recipe: recipeFromNode(node, effects) });
    if (event.data.type !== "openpositive:apply") return;
    try {
      const createNode = type => {
        if (!globalThis.LiteGraph?.createNode) throw new Error("The ComfyUI graph API is unavailable. Open the studio from an existing LTX VFX node.");
        return globalThis.LiteGraph.createNode(type);
      };
      node = applyRecipeToGraph(app, createNode, node, event.data.recipe, effects);
      post({ type: "openpositive:applied", nodeId: node.id });
    } catch (error) {
      post({ type: "openpositive:applied", error: error.message });
    }
  };
  window.addEventListener("message", onMessage);
  dialog.addEventListener("close", () => {
    window.removeEventListener("message", onMessage);
    dialog.remove();
    if (currentDialog === dialog) currentDialog = null;
  }, { once: true });
  close.addEventListener("click", () => dialog.close());
  dialog.append(frame, close);
  document.body.append(dialog);
  try {
    dialog.showModal();
    currentDialog = dialog;
  } catch (error) {
    window.removeEventListener("message", onMessage);
    dialog.remove();
    throw error;
  }
}

async function openStudio(node) {
  if (currentDialog?.open) { currentDialog.focus(); return; }
  if (opening) return opening;
  opening = createStudio(node);
  try { await opening; } finally { opening = null; }
}

function report(error) {
  app.extensionManager?.toast?.add({ severity: "error", summary: "OpenPositive Studio", detail: error.message, life: 7000 });
  console.error("OpenPositive Studio:", error);
}

app.registerExtension({
  name: "OpenPositive.LTXVFXStudio",
  commands: [{ id: "OpenPositive.OpenVFXStudio", label: "OpenPositive · LTX VFX Studio", function: () => openStudio().catch(report) }],
  menuCommands: [{ path: ["Extensions", "OpenPositive"], commands: ["OpenPositive.OpenVFXStudio"] }],
  nodeCreated(node) {
    if (node.comfyClass !== "LTXVFXStudio" || node.widgets?.some(widget => widget.name === "Open VFX Studio")) return;
    const button = node.addWidget("button", "Open VFX Studio", null, () => openStudio(node).catch(report), { serialize: false });
    button.options.serialize = false;
    node.color = "#23262a";
    node.bgcolor = "#131416";
    node.setSize([Math.max(node.size[0], 330), node.size[1]]);
  },
});
