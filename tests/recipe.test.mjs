import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { PARAMETER_NAMES, RECIPE_SCHEMA, safeDefaults, specialistWorkflow, validateRecipe } from "../web/recipe.js";

const { effects } = JSON.parse(await readFile(new URL("../data/effects.json", import.meta.url), "utf8"));
const effect = id => effects.find(item => item.id === id);
const recipe = (id = "day-to-night", overrides = {}) => ({
  schema: RECIPE_SCHEMA,
  effect: id,
  parameters: { ...safeDefaults(effect(id)), ...overrides },
});

test("all 15 catalog effects have valid, independently allocated starting recipes", () => {
  assert.equal(effects.length, 15);
  assert.equal(new Set(effects.map(item => item.id)).size, 15);
  for (const item of effects) {
    const defaults = safeDefaults(item);
    const clean = validateRecipe(recipe(item.id), effects);
    assert.deepEqual(clean.parameters, defaults, item.id);
    assert.notEqual(defaults, safeDefaults(item));
    assert.equal(defaults.frames, item.defaults.frames);
    assert.equal(defaults.frame_rate, item.defaults.fps);
    assert.equal(defaults.strength, item.default_strength);
  }
});

test("validation returns only known fields and never mutates imported recipes", () => {
  const imported = recipe();
  imported.untrusted = "discard me";
  imported.parameters.extra = "discard me too";
  const snapshot = structuredClone(imported);
  const clean = validateRecipe(imported, effects);
  assert.deepEqual(imported, snapshot);
  assert.deepEqual(Object.keys(clean), ["schema", "effect", "parameters"]);
  assert.deepEqual(Object.keys(clean.parameters), PARAMETER_NAMES);
  assert.notEqual(clean.parameters, imported.parameters);
});

test("schema, effect and parameter structure must be recognized", () => {
  assert.throws(() => validateRecipe(null, effects), /schema/);
  assert.throws(() => validateRecipe({ ...recipe(), schema: "other/v1" }, effects), /schema/);
  assert.throws(() => validateRecipe({ ...recipe(), effect: "invented-effect" }, effects), /catalog/);
  assert.throws(() => validateRecipe({ ...recipe(), parameters: null }, effects), /parameters/);
});

test("untrusted numeric inputs cannot be coerced into valid controls", () => {
  for (const field of ["strength", "guide_strength", "width", "height", "frames", "frame_rate"]) {
    for (const value of [NaN, Infinity, -Infinity, "1", null, true, {}, []]) {
      assert.throws(() => validateRecipe(recipe("day-to-night", { [field]: value }), effects), undefined, `${field} = ${String(value)}`);
    }
  }
});

test("prompts are bounded text fields", () => {
  for (const field of ["prompt", "negative_prompt"]) {
    assert.throws(() => validateRecipe(recipe("day-to-night", { [field]: 1 }), effects), /Invalid/);
    assert.throws(() => validateRecipe(recipe("day-to-night", { [field]: "x".repeat(16001) }), effects), /Invalid/);
  }
  assert.equal(validateRecipe(recipe("day-to-night", { prompt: "x".repeat(16000) }), effects).parameters.prompt.length, 16000);
});

test("frame count follows the temporal grid and frame rate stays integral", () => {
  for (const frames of [8, 10, 96, 97.5]) assert.throws(() => validateRecipe(recipe("day-to-night", { frames }), effects));
  assert.equal(validateRecipe(recipe("day-to-night", { frames: 97 }), effects).parameters.frames, 97);
  assert.throws(() => validateRecipe(recipe("day-to-night", { frame_rate: 23.976 }), effects), /whole number/);
});

test("alpha matte keeps an empty prompt and caps the clip length", () => {
  assert.equal(safeDefaults(effect("alpha-gen")).prompt, "");
  assert.throws(() => validateRecipe(recipe("alpha-gen", { prompt: "blue background" }), effects), /empty prompt/);
  assert.throws(() => validateRecipe(recipe("alpha-gen", { frames: 153 }), effects), /145/);
  assert.equal(validateRecipe(recipe("alpha-gen", { frames: 145 }), effects).parameters.frames, 145);
});

test("HDR fixed embeddings cannot be replaced with a text prompt or variable strength", () => {
  assert.equal(safeDefaults(effect("sdr-to-hdr")).prompt, "");
  assert.throws(() => validateRecipe(recipe("sdr-to-hdr", { prompt: "make it brighter" }), effects), /prompt|embedding/i);
  assert.throws(() => validateRecipe(recipe("sdr-to-hdr", { strength: 0.5 }), effects), /fixed strength/);
});

test("Ingredients enforces a complete reference-sheet bucket", () => {
  assert.throws(() => validateRecipe(recipe("ingredients", { frames: 97 }), effects), /121/);
  assert.equal(validateRecipe(recipe("ingredients", { frames: 121 }), effects).parameters.frames, 121);
});

test("two-stage and 2x-reference geometry uses a 64-pixel grid", () => {
  for (const id of ["layout-to-render", "slow-motion-control", "pixel-spatial-upscaler"]) {
    assert.throws(() => validateRecipe(recipe(id, { width: 800, height: 576 }), effects), undefined, id);
    assert.equal(validateRecipe(recipe(id, { width: 1024, height: 576 }), effects).parameters.width, 1024);
  }
});

test("finishing recipes accept the padded 4K canvas required by LTX", () => {
  const clean = validateRecipe(recipe("refine-details", { width: 3840, height: 2176 }), effects);
  assert.equal(clean.parameters.height, 2176);
});

test("effect strength ranges retain the model-specific lower bound", () => {
  assert.throws(() => validateRecipe(recipe("cinemagraph", { strength: 0.4 }), effects), /between/);
  assert.equal(validateRecipe(recipe("cinemagraph", { strength: 1.2 }), effects).parameters.strength, 1.2);
});

test("only dedicated HDR and speed graphs use specialist workflow handoffs", () => {
  assert.equal(specialistWorkflow(effect("sdr-to-hdr")), "sdr-to-hdr.json");
  assert.equal(specialistWorkflow(effect("slow-motion-control")), "slow-motion-control.json");
  for (const item of effects.filter(item => !["hdr", "i2v_speed"].includes(item.pipeline))) assert.equal(specialistWorkflow(item), null);
});
