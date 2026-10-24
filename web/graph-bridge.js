import { PARAMETER_NAMES, RECIPE_SCHEMA, safeDefaults, validateRecipe, specialistWorkflow } from "./recipe.js";

/** The graph owning a node may be a subgraph rather than the root canvas. */
export function activeGraph(app, node) {
  return node?.graph || app.canvas?.graph || app.rootGraph || app.graph;
}

export function recipeFromNode(node, effects) {
  if (!node) return null;
  const widgets = new Map((node.widgets || []).map(widget => [widget.name, widget]));
  const value = widgets.get("effect")?.value;
  const effect = effects.find(item => item.id === value || item.name === value);
  if (!effect) return null;
  const defaults = safeDefaults(effect);
  return {
    schema: RECIPE_SCHEMA,
    effect: effect.id,
    parameters: Object.fromEntries(PARAMETER_NAMES.map(name => [name, widgets.get(name)?.value ?? defaults[name]])),
  };
}

/** Apply ordinary widget values in one graph transaction without replacing a workflow. */
export function applyRecipeToGraph(app, createNode, node, untrustedRecipe, effects) {
  const recipe = validateRecipe(untrustedRecipe, effects);
  const effect = effects.find(item => item.id === recipe.effect);
  if (specialistWorkflow(effect)) {
    throw new Error(`${effect.name} needs its dedicated workflow. Use Get specialist workflow in the studio.`);
  }
  const graph = activeGraph(app, node);
  if (!graph) throw new Error("Open a ComfyUI workflow before applying this effect.");
  if (app.canvas?.read_only) throw new Error("This workflow is read-only. Switch to an editable workflow first.");
  if (node && graph.getNodeById(node.id) !== node) {
    throw new Error("The target node was removed. Reopen the studio from an existing node.");
  }
  const isNew = !node;
  const target = node || createNode("LTXVFXStudio");
  if (!target) throw new Error("LTXVFXStudio is not registered. Check the ComfyUI startup log.");
  const widgets = new Map((target.widgets || []).map(widget => [widget.name, widget]));
  const values = { effect: effect.name, ...recipe.parameters };
  const missing = Object.keys(values).filter(name => !widgets.has(name));
  if (missing.length) throw new Error(`Node version mismatch: missing ${missing.join(", ")}. Restart ComfyUI.`);
  const connected = (target.inputs || []).filter(input =>
    Object.hasOwn(values, input.name) && (input.link != null || input.links?.length)
  );
  if (connected.length) {
    throw new Error(`These controls are supplied by connected nodes: ${connected.map(input => input.name).join(", ")}. Edit or disconnect those inputs first.`);
  }
  const previous = Object.fromEntries(Object.keys(values).map(name => [name, widgets.get(name).value]));
  graph.beforeChange?.();
  try {
    if (isNew) {
      target.pos = [120, 120];
      graph.add(target);
    }
    for (const [name, value] of Object.entries(values)) {
      const widget = widgets.get(name);
      widget.value = value;
      widget.callback?.(value);
    }
    target.setDirtyCanvas(true, true);
  } catch (error) {
    for (const [name, value] of Object.entries(previous)) widgets.get(name).value = value;
    if (isNew) graph.remove(target);
    throw error;
  } finally {
    graph.afterChange?.();
  }
  return target;
}

/** randomUUID needs HTTPS; getRandomValues also works on ordinary LAN HTTP. */
export function bridgeToken(cryptoSource = globalThis.crypto) {
  if (cryptoSource?.randomUUID) return cryptoSource.randomUUID();
  if (!cryptoSource?.getRandomValues) throw new Error("This browser cannot create a secure studio session token.");
  const bytes = cryptoSource.getRandomValues(new Uint8Array(24));
  return Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
}

/** Accept a Comfy reverse-proxy prefix, never a remote or arbitrary endpoint. */
export function studioApiBase(candidate, pageUrl) {
  const page = new URL(pageUrl);
  const base = new URL(candidate || "/ltx-vfx/", page);
  if (!/^https?:$/.test(base.protocol) || base.origin !== page.origin || base.username || base.password || base.search || base.hash || !base.pathname.endsWith("/ltx-vfx/")) {
    throw new Error("The studio API route must be a same-origin ComfyUI /ltx-vfx/ endpoint.");
  }
  return base;
}
