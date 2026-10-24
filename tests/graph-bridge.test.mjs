import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { activeGraph, applyRecipeToGraph, bridgeToken, recipeFromNode, studioApiBase } from '../web/graph-bridge.js';
import { safeDefaults, RECIPE_SCHEMA } from '../web/recipe.js';

const { effects } = JSON.parse(await readFile(new URL('../data/effects.json', import.meta.url), 'utf8'));
const effect = effects.find(item => item.id === 'day-to-night');
const recipe = { schema: RECIPE_SCHEMA, effect: effect.id, parameters: safeDefaults(effect) };

function graph() {
  return { nodes: new Map(), before: 0, after: 0, next: 1,
    getNodeById(id) { return this.nodes.get(id); },
    add(node) { node.id = this.next++; node.graph = this; this.nodes.set(node.id, node); },
    remove(node) { this.nodes.delete(node.id); node.graph = null; },
    beforeChange() { this.before++; }, afterChange() { this.after++; },
  };
}
function node() {
  const values = { effect: effect.name, ...safeDefaults(effect) };
  return { widgets: Object.entries(values).map(([name, value]) => ({ name, value })),
    inputs: [{ name: 'model', link: 10 }], setDirtyCanvas() { this.dirty = true; } };
}
function values(target) { return Object.fromEntries(target.widgets.map(widget => [widget.name, widget.value])); }

test('a new node receives a validated recipe in the active canvas graph', () => {
  const root = graph(), current = graph(), newNode = node();
  const target = applyRecipeToGraph({ rootGraph: root, canvas: { graph: current } }, () => newNode, null, recipe, effects);
  assert.equal(target, newNode); assert.equal(root.nodes.size, 0); assert.equal(current.nodes.size, 1);
  assert.equal(target.dirty, true); assert.equal(current.before, 1); assert.equal(current.after, 1);
  assert.deepEqual(values(target), { effect: effect.name, ...recipe.parameters });
});

test('an existing nested node changes in its own subgraph, not the root graph', () => {
  const root = graph(), nested = graph(), existing = node(); nested.add(existing);
  const changed = structuredClone(recipe); changed.parameters.prompt = 'Blue moonlight.';
  applyRecipeToGraph({ rootGraph: root, canvas: { graph: root } }, () => { throw Error('must not create'); }, existing, changed, effects);
  assert.equal(nested.before, 1); assert.equal(root.before, 0);
  assert.equal(values(existing).prompt, 'Blue moonlight.');
  assert.equal(activeGraph({ rootGraph: root }, existing), nested);
});

test('widget values supplied by connected inputs are never silently overwritten', () => {
  const current = graph(), existing = node(); current.add(existing);
  existing.inputs.push({ name: 'prompt', link: 0 });
  const previous = values(existing);
  assert.throws(() => applyRecipeToGraph({ canvas: { graph: current } }, node, existing, recipe, effects), /connected nodes: prompt/);
  assert.deepEqual(values(existing), previous); assert.equal(current.before, 0);
});

test('missing-widget versions do not leave a partial new node in the graph', () => {
  const current = graph(), bad = node(); bad.widgets.pop();
  assert.throws(() => applyRecipeToGraph({ graph: current }, () => bad, null, recipe, effects), /version mismatch/);
  assert.equal(current.nodes.size, 0); assert.equal(current.before, 0);
});

test('callback failures restore values and remove an incomplete new node', () => {
  const current = graph(), bad = node(), original = values(bad);
  bad.widgets.find(widget => widget.name === 'prompt').callback = () => { throw Error('callback failure'); };
  const changed = structuredClone(recipe); changed.parameters.prompt = 'Changed.';
  assert.throws(() => applyRecipeToGraph({ graph: current }, () => bad, null, changed, effects), /callback failure/);
  assert.deepEqual(values(bad), original); assert.equal(current.nodes.size, 0); assert.equal(current.after, 1);
});

test('deleted nodes and read-only canvases fail before mutation', () => {
  const current = graph(), existing = node(); current.add(existing); current.nodes.delete(existing.id);
  assert.throws(() => applyRecipeToGraph({ graph: current }, node, existing, recipe, effects), /removed/);
  assert.throws(() => applyRecipeToGraph({ graph: current, canvas: { read_only: true } }, node, null, recipe, effects), /read-only/);
  assert.equal(current.before, 0);
});

test('dedicated workflows cannot be injected into a generic Studio node', () => {
  const hdr = effects.find(item => item.id === 'sdr-to-hdr');
  const current = graph();
  assert.throws(() => applyRecipeToGraph({ graph: current }, node, null, { schema: RECIPE_SCHEMA, effect: hdr.id, parameters: safeDefaults(hdr) }, effects), /dedicated workflow/);
  assert.equal(current.nodes.size, 0);
});

test('node controls rehydrate the panel without losing zero values', () => {
  const existing = node(); existing.widgets.find(widget => widget.name === 'strength').value = 0;
  assert.equal(recipeFromNode(existing, effects).parameters.strength, 0);
  assert.equal(recipeFromNode(null, effects), null);
});

test('session tokens work without randomUUID on HTTP LAN installations', () => {
  assert.equal(bridgeToken({ randomUUID: () => 'uuid' }), 'uuid');
  const token = bridgeToken({ getRandomValues: bytes => { bytes.fill(16); return bytes; } });
  assert.equal(token, '10'.repeat(24));
  assert.throws(() => bridgeToken({}), /secure studio session token/);
});

test('API discovery accepts same-origin reverse-proxy prefixes', () => {
  assert.equal(studioApiBase(null, 'http://localhost:8188/extensions/pack/studio.html').href, 'http://localhost:8188/ltx-vfx/');
  const base = studioApiBase('/comfy/api/ltx-vfx/', 'https://example.test/comfy/extensions/pack/studio.html');
  assert.equal(new URL('catalog', base).href, 'https://example.test/comfy/api/ltx-vfx/catalog');
});

test('API discovery rejects remote and arbitrary routes from untrusted query strings', () => {
  for (const candidate of ['https://evil.test/ltx-vfx/', '//evil.test/ltx-vfx/', 'javascript:alert(1)', '/admin/', '/ltx-vfx/?token=x', '/ltx-vfx/#fragment', 'https://name:secret@example.test/ltx-vfx/']) {
    assert.throws(() => studioApiBase(candidate, 'https://example.test/extensions/pack/studio.html'), /same-origin/);
  }
});
