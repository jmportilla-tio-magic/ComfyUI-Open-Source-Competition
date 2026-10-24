/** Small, shared contract used by the standalone UI and the ComfyUI bridge. */
export const RECIPE_SCHEMA = "openpositive.ltx-vfx.recipe/v1";
export const PARAMETER_NAMES = ["prompt", "negative_prompt", "strength", "guide_strength", "width", "height", "frames", "frame_rate"];

export function validateRecipe(recipe, effects) {
  if (!recipe || recipe.schema !== RECIPE_SCHEMA) throw new Error("Choose an OpenPositive VFX recipe (schema v1).");
  const effect = effects.find(item => item.id === recipe.effect);
  if (!effect) throw new Error("This effect is not in the verified Creative Lab catalog.");
  const parameters = recipe.parameters;
  if (!parameters || typeof parameters !== "object") throw new Error("The recipe has no parameters.");
  for (const name of ["prompt", "negative_prompt"]) {
    if (typeof parameters[name] !== "string" || parameters[name].length > 16000) throw new Error(`Invalid ${name.replaceAll("_", " ")}.`);
  }
  const limits = { strength: effect.strength_range || [0, 2], guide_strength: [0, 1], width: [64, 8192], height: [64, 8192], frames: [9, 4097], frame_rate: [1, 120] };
  for (const [name, [min, max]] of Object.entries(limits)) {
    const value = parameters[name];
    if (typeof value !== "number" || !Number.isFinite(value) || value < min || value > max) throw new Error(`${name.replaceAll("_", " ")} must be between ${min} and ${max}.`);
  }
  const multiple = Math.max(effect.dimension_multiple || 32, 32 * (effect.reference_downscale_factor || 1));
  if (![parameters.width, parameters.height].every(value => Number.isInteger(value) && value % multiple === 0)) throw new Error(`Width and height must be multiples of ${multiple}.`);
  if (!Number.isInteger(parameters.frames) || (parameters.frames - 1) % 8) throw new Error("Use 8n + 1 frames: 9, 17, 25, …, 97, 121.");
  if (!Number.isInteger(parameters.frame_rate)) throw new Error("Frame rate must be a whole number.");
  if (effect.max_frames && parameters.frames > effect.max_frames) throw new Error(`${effect.name} supports at most ${effect.max_frames} frames.`);
  if (effect.min_frames && parameters.frames < effect.min_frames) throw new Error(`${effect.name} needs at least ${effect.min_frames} frames.`);
  if (effect.max_width && parameters.width > effect.max_width || effect.max_height && parameters.height > effect.max_height) throw new Error(`${effect.name} exceeds its supported dimensions.`);
  if (["empty", "fixed_embeddings"].includes(effect.prompt_policy) && parameters.prompt.trim()) throw new Error(`${effect.name} requires an empty prompt.`);
  if (effect.strength_fixed && parameters.strength !== effect.default_strength) throw new Error(`${effect.name} uses a fixed strength of ${effect.default_strength}.`);
  // Return a clean, allowlisted object rather than arbitrary imported fields.
  return { schema: RECIPE_SCHEMA, effect: effect.id, parameters: Object.fromEntries(PARAMETER_NAMES.map(name => [name, parameters[name]])) };
}

export function safeDefaults(effect) {
  const defaults = effect.defaults || {};
  return {
    prompt: effect.prompt_hint || "", negative_prompt: "blurry, distorted, low quality, artifacts",
    strength: effect.default_strength ?? 1, guide_strength: 1,
    width: defaults.width || 768, height: defaults.height || 512,
    frames: defaults.frames || 97, frame_rate: defaults.fps || 24,
  };
}

export function specialistWorkflow(effect) {
  return { hdr: "sdr-to-hdr.json", i2v_speed: "slow-motion-control.json" }[effect.pipeline] || null;
}
