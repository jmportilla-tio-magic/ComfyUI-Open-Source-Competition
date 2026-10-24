import { RECIPE_SCHEMA, validateRecipe, safeDefaults, specialistWorkflow } from "./recipe.js";
import { studioApiBase } from "./graph-bridge.js";

const paths = {
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  star: '<path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9Z"/>',
  moon: '<path d="M20.7 13.1A8.8 8.8 0 0 1 10.9 3.3 9 9 0 1 0 20.7 13.1Z"/>',
  sparkles: '<path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4Z"/><path d="m20 2 .6 1.4L22 4l-1.4.6L20 6l-.6-1.4L18 4l1.4-.6Z"/>',
  'arrow-up-right': '<path d="M6 18 18 6M6 6h12v12"/>', 'arrow-right': '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 16v4h16v-4"/>', download: '<path d="M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 2-2.5 2-2.5 4m0 3h.01"/>',
  rotate: '<path d="M3 10a9 9 0 1 1 2 8M3 4v6h6"/>', columns: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/>',
  expand: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
  chevrons: '<path d="m9 8-4 4 4 4m6-8 4 4-4 4"/>', play: '<path d="m8 4 12 8-12 8Z"/>', pause: '<path d="M8 4v16M16 4v16"/>',
  mouse: '<rect x="6" y="2" width="12" height="20" rx="6"/><path d="M12 2v7"/>', plus: '<path d="M12 5v14M5 12h14"/>',
  frame: '<path d="M4 9V4h5m6 0h5v5M4 15v5h5m6 0h5v-5"/><rect x="8" y="8" width="8" height="8" rx="1"/>',
  'chevron-down': '<path d="m6 9 6 6 6-6"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>', close: '<path d="m5 5 14 14M5 19 19 5"/>',
  layers: '<path d="m12 3 10 6-10 6L2 9Zm-10 12 10 6 10-6M2 15l10 6 10-6"/>',
  droplet: '<path d="M12 2c-2 4-7 8-7 13a7 7 0 0 0 14 0c0-5-5-9-7-13Z"/><path d="M8 15c0 2 1 3 3 3"/>',
  aperture: '<circle cx="12" cy="12" r="9"/><path d="m9 3 7 12m5-6H7m13 9-7-12M7 20l7-12M3 9l7 12M3 15h14"/>',
  grid: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
  film: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4m10 0h4M3 16h4m10 0h4"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>', palette: '<path d="M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 1-3.7 1 1 0 0 1 .6-1.8H17A4 4 0 0 0 21 11a9 9 0 0 0-9-8Z"/><path d="M7 9h.01M12 6h.01M17 9h.01M6 14h.01"/>',
  eraser: '<path d="m4 12 9-9 8 8-9 10H8l-6-6Zm3-3 8 8M12 21h10"/>', box: '<path d="m12 2 10 5v10l-10 5-10-5V7Zm0 10 10-5M2 7l10 5v10"/>',
};
const icons = {"day-to-night":"moon","clean-plate":"eraser","water-simulation":"droplet","pixel-spatial-upscaler":"expand",deblur:"aperture",decompression:"grid",colorization:"palette",cinemagraph:"film","slow-motion-control":"clock",ingredients:"layers","sdr-to-hdr":"sun","layout-to-render":"box","refine-details":"sparkles",restore:"rotate","alpha-gen":"layers"};
const groupNames = {transform:"TRANSFORM THE SCENE",finishing:"RESTORE & REFINE",composite:"BUILD THE IMPOSSIBLE",motion:"MAKE IT MOVE"};
export function icon(name) { return `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.sparkles}</svg>`; }
function hydrateIcons(root = document) {root.querySelectorAll("i[data-icon]").forEach(el => {el.innerHTML = icon(el.dataset.icon);});}
const $ = id => document.getElementById(id);

// ComfyUI discovers every JS module in WEB_DIRECTORY; only boot in our isolated page.
if ($("studio")) boot().catch(error => {$("effect-list").textContent = `Unable to load the effect catalog: ${error.message}. Serve the repository over HTTP.`;$("apply-button").disabled = true;});

async function loadCatalog(apiBase) {
  for (const url of [new URL("catalog", apiBase), new URL("../data/effects.json", import.meta.url)]) {
    try {const response = await fetch(url); if (!response.ok) continue; const data = await response.json(); if (Array.isArray(data.effects) && data.effects.length) return data;} catch { /* Try the standalone source. */ }
  }
  throw new Error("no verified catalog found");
}

async function boot() {
  hydrateIcons();
  const query = new URLSearchParams(location.search);
  const apiBase = studioApiBase(query.get("apiBase"), location.href);
  const catalog = await loadCatalog(apiBase);
  const homeUrl = new URL("./studio.html", location.href);
  homeUrl.search = location.search;
  document.querySelector(".brand").href = homeUrl.href;
  const effects = catalog.effects;
  let selected = effects.find(effect => effect.id === "day-to-night") || effects[0];
  let filter = "all", connected = false, pending = false, sourceUrl = null, referenceUrl = null, toastTimer, activeNode, health=null;
  let favorites;
  try {favorites = new Set(JSON.parse(localStorage.getItem("openpositive.favorites") || "[]"));} catch {favorites = new Set();}
  let originalSource = true;
  const bridgeToken = query.get("bridge");
  const sourceVideo = document.querySelector(".source-video");
  const referenceVideo = document.querySelector(".reference-video");
  const sourceImage = document.querySelector(".source-layer img");
  const referenceImage = document.querySelector(".reference-layer img");
  $("effect-count").textContent = effects.length;

  function toast(message) {clearTimeout(toastTimer);$("toast").textContent=message;$("toast").hidden=false;toastTimer=setTimeout(()=>{$("toast").hidden=true;},5500);}
  function persistFavorites() {try {localStorage.setItem("openpositive.favorites",JSON.stringify([...favorites]));} catch {/* Browser privacy mode may deny storage. */}}
  function renderLibrary() {
    const search = $("effect-search").value.trim().toLowerCase();
    const shown = effects.filter(effect => (filter !== "favorites" || favorites.has(effect.id)) && `${effect.name} ${effect.summary} ${effect.category}`.toLowerCase().includes(search));
    $("effect-list").replaceChildren();
    for (const group of Object.keys(groupNames)) {
      const items = shown.filter(effect => effect.category === group);
      if (!items.length) continue;
      const section = document.createElement("section");section.className="effect-group";
      const heading=document.createElement("h3");heading.className="group-heading";heading.textContent=groupNames[group];section.append(heading);
      for (const effect of items) {
        const button = document.createElement("button");button.className=`effect-button${effect.id===selected.id?" active":""}`;button.setAttribute("aria-pressed",String(effect.id===selected.id));button.dataset.effect=effect.id;
        const emblem=document.createElement("span");emblem.className="effect-icon";emblem.innerHTML=icon(icons[effect.id]);
        const text=document.createElement("span");text.className="effect-text";text.textContent=effect.name;
        const type=document.createElement("span");type.className="effect-type";type.textContent=effect.conditioning==="image"?"Image to video":effect.conditioning==="reference_sheet"?"Reference to video":"Video to video";text.append(type);
        const arrow=document.createElement("i");arrow.className="effect-arrow";arrow.innerHTML=icon("arrow-right");button.append(emblem,text,arrow);button.addEventListener("click",()=>select(effect));section.append(button);
      }
      $("effect-list").append(section);
    }
    if (!shown.length) {const empty=document.createElement("p");empty.className="empty-library";empty.textContent=filter==="favorites"?"Save your go-to effects with the star in the inspector.":"No effects found. Try a different search.";$("effect-list").append(empty);}
  }
  function writeParameters(parameters) {
    $("prompt").value=parameters.prompt;$("negative-prompt").value=parameters.negative_prompt;$("strength").value=parameters.strength;$("guidance").value=parameters.guide_strength;
    for (const key of ["width","height","frames"]) $(key).value=parameters[key];
    const frameRate = String(parameters.frame_rate);
    if (![...$("frame-rate").options].some(option=>option.value===frameRate)) $("frame-rate").add(new Option(`${frameRate} fps`, frameRate));
    $("frame-rate").value=frameRate;refreshSliders();refreshDimensions();
  }
  function select(effect, parameters) {
    selected=effect;renderLibrary();
    $("effect-title").textContent=effect.name;$("effect-summary").textContent=effect.summary;$("effect-family").textContent=effect.category.toUpperCase();
    $("effect-hero-icon").innerHTML=icon(icons[effect.id]);$("model-link").href=effect.source_url;$("model-kind").textContent=effect.adapter_type==="lora"?"LoRA":"IC-LoRA";
    $("favorite-button").setAttribute("aria-pressed",String(favorites.has(effect.id)));
    $("favorite-button").setAttribute("aria-label",favorites.has(effect.id)?"Unsave effect":"Save effect");
    const specialist=!!specialistWorkflow(effect);
    $("effect-note").querySelector("p").textContent=(specialist?"Configure this effect in its dedicated workflow. These controls do not alter that graph. ":"")+effect.notes.join(" ");
    $("sampler-recommendation").textContent=`${effect.base_variant || "distilled"} · ${effect.defaults.steps} steps · CFG ${effect.defaults.cfg}${effect.pipeline==="ic_lora_two_stage"?" · two stages":""}`;
    $("workflow-guide").href=effect.workflow_url;
    $("strength").min=effect.strength_range?.[0]??0;$("strength").max=effect.strength_range?.[1]??2;$("strength").disabled=!!effect.strength_fixed||specialist;
    for (const id of ["width","height"]) $(id).step=effect.dimension_multiple||32;
    $("frames").min=effect.min_frames||9;$("frames").max=effect.max_frames||4097;
    for(const id of ["width","height","frames","frame-rate","guidance","negative-prompt"])$(id).disabled=specialist;
    document.querySelectorAll("[data-size]").forEach(button=>button.disabled=specialist);
    $("prompt").disabled=specialist||["empty","fixed_embeddings"].includes(effect.prompt_policy);
    $("prompt-suggestion").disabled=$("prompt").disabled;
    $("prompt").placeholder=effect.prompt_policy==="empty"?"This effect uses an empty prompt automatically.":effect.prompt_policy==="fixed_embeddings"?"The HDR workflow uses supplied scene embeddings.":"Describe the look, lighting, and feeling you have in mind…";
    writeParameters(parameters||safeDefaults(effect));updateAction();updateHealth();
    if (originalSource && !referenceUrl) {
      document.querySelector(".result-label").innerHTML='LIGHTING STUDY <span>✦</span>';
      $("viewer-caption").innerHTML='<span class="status-dot"></span>Illustrative preview · not an LTX render';
    }
  }
  function updateAction() {
    const specialist=specialistWorkflow(selected);
    $("apply-button").querySelector("span").textContent=specialist?"Get specialist workflow":connected?"Apply to ComfyUI node":"Export effect recipe";
    $("apply-caption").textContent=specialist?"Opens the official graph with its own controls.":connected?"Sets the node. Sampling runs from your graph.":"Take your creative direction into ComfyUI.";
    $("connection-status").textContent=connected?`Connected to ComfyUI · node ${activeNode ?? "new"}`:"Local design preview";
  }
  function updateHealth(){
    const el=$("model-install-status");el.hidden=!health;
    if(!health)return;
    const installed=health.effects?.[selected.id]?.installed;
    el.textContent=health.missing_nodes?.length?"LTX nodes missing · see installation guide":installed?"Adapter found in this ComfyUI installation":"Adapter needed · run the model download plan";
    el.classList.toggle("installed",!!installed&&!health.missing_nodes?.length);
    el.title=health.missing_nodes?.length?health.missing_nodes.join(", "):selected.filename;
  }
  function refreshSliders() {
    for (const [id,output] of [["strength","strength-value"],["guidance","guidance-value"]]) {const el=$(id);$(output).value=Number(el.value).toFixed(2);el.style.background=`linear-gradient(to right,var(--accent) ${(Number(el.value)-Number(el.min))/(Number(el.max)-Number(el.min))*100}%,var(--range-track) 0%)`;}
  }
  function refreshDimensions() {document.querySelectorAll("[data-size]").forEach(button=>{button.classList.toggle("active",button.dataset.size===`${$("width").value},${$("height").value}`);});}
  function recipe() {return validateRecipe({schema:RECIPE_SCHEMA,effect:selected.id,parameters:{prompt:$("prompt").value,negative_prompt:$("negative-prompt").value,strength:Number($("strength").value),guide_strength:Number($("guidance").value),width:Number($("width").value),height:Number($("height").value),frames:Number($("frames").value),frame_rate:Number($("frame-rate").value)}},effects);}
  function download(content, filename) {const url=URL.createObjectURL(new Blob([content],{type:"application/json"}));const anchor=document.createElement("a");anchor.href=url;anchor.download=filename;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  async function apply() {
    if (pending) return;
    try {
      const specialist=specialistWorkflow(selected);
      if (specialist) {
        let graph;
        for(const url of [new URL(`workflows/${selected.id}`,apiBase),new URL(`../examples/workflows/${specialist}`,import.meta.url)]){
          try{const response=await fetch(url);if(response.ok){graph=await response.json();break;}}catch{/* Try the standalone copy. */}
        }
        if(!graph){toast("Access is required for this workflow. Use the model card link to accept its terms, then run the documented model downloader with --workflows.");return;}
        download(JSON.stringify(graph,null,2),`openpositive-${specialist}`);toast("Workflow downloaded. Open it in ComfyUI and follow its model and input notes.");return;
      }
      const next=recipe();
      if (connected) {pending=true;$("apply-button").disabled=true;parent.postMessage({type:"openpositive:apply",token:bridgeToken,recipe:next},location.origin);setTimeout(()=>{if(pending){pending=false;$("apply-button").disabled=false;toast("No response from ComfyUI. Close and reopen the studio to reconnect.");}},8000);}
      else {download(JSON.stringify(next,null,2),`${selected.id}.ltx-vfx.json`);toast("Recipe exported. Open the studio from a ComfyUI node to apply it.");}
    } catch(error){toast(error.message);}
  }
  window.addEventListener("message",event=>{
    if(event.origin!==location.origin||event.source!==parent||!bridgeToken||event.data?.token!==bridgeToken)return;
    const data=event.data;
    if(data.type==="openpositive:init") {
      connected=true;activeNode=data.nodeId;
      if(data.recipe) {try {const clean=validateRecipe(data.recipe,effects);select(effects.find(effect=>effect.id===clean.effect),clean.parameters);}catch(error){toast(`Node settings need attention: ${error.message}`);}}
      updateAction();
      fetch(new URL("health",apiBase)).then(response=>response.ok?response.json():null).then(data=>{health=data;updateHealth();}).catch(()=>{});
    }
    if(data.type==="openpositive:applied"){pending=false;$("apply-button").disabled=false;activeNode=data.nodeId;updateAction();toast(data.error||"Creative direction applied. Connect your source and sample from the graph.");}
  });
  if(bridgeToken&&parent!==window)parent.postMessage({type:"openpositive:ready",token:bridgeToken},location.origin);
  function timecode(seconds){const safe=Number.isFinite(seconds)?Math.max(0,seconds):0;return [Math.floor(safe/60),Math.floor(safe%60),Math.floor((safe%1)*Number($("frame-rate").value))].map(value=>String(value).padStart(2,"0")).join(":");}
  function syncPlayback(){if(!referenceVideo.hidden&&Math.abs(referenceVideo.currentTime-sourceVideo.currentTime)>.15)referenceVideo.currentTime=Math.min(sourceVideo.currentTime,referenceVideo.duration||0);$("timecode").textContent=timecode(sourceVideo.currentTime);$("scrubber").value=sourceVideo.duration?sourceVideo.currentTime/sourceVideo.duration*1000:0;}
  function pause(){sourceVideo.pause();referenceVideo.pause();$("play-button").innerHTML=icon("play");$("play-button").setAttribute("aria-label","Play source clip");}
  async function importMedia(file, isReference){
    if(!file)return;if(!/^image\//.test(file.type)&&!/^video\//.test(file.type)){toast("Choose an image or video file.");return;}
    pause();const url=URL.createObjectURL(file);const video=isReference?referenceVideo:sourceVideo;const img=isReference?referenceImage:sourceImage;const isVideo=file.type.startsWith("video/");
    const previous=isReference?referenceUrl:sourceUrl;if(previous)URL.revokeObjectURL(previous);if(isReference)referenceUrl=url;else {sourceUrl=url;originalSource=false;}
    video.hidden=!isVideo;img.hidden=isVideo;video.removeAttribute("src");video.load();img.classList.remove("sample-image");
    if(isVideo){video.src=url;video.load();}else {img.src=url;img.alt=`${isReference?"Rendered reference":"Source"}: ${file.name}`;}
    document.querySelector(".media-error").hidden=true;
    if(!isReference){$("shot-name").textContent=file.name;$("play-button").disabled=!isVideo;$("scrubber").disabled=!isVideo;$("timecode").textContent="00:00:00";$("duration").textContent=isVideo?"LOADING":"STILL";$("source-resolution").textContent="LOCAL SOURCE";
      if(!referenceUrl){referenceImage.src=url;referenceImage.hidden=isVideo;referenceImage.classList.remove("sample-image");referenceImage.alt="Source reference, no render loaded";referenceVideo.hidden=!isVideo;referenceVideo.removeAttribute("src");if(isVideo)referenceVideo.src=url;referenceVideo.load();document.querySelector(".result-label").textContent="REFERENCE";$("viewer-caption").textContent="Source only · load a rendered reference to compare";}
    } else {document.querySelector(".reference-layer").classList.add("has-reference");document.querySelector(".result-label").textContent="YOUR REFERENCE";$("viewer-caption").textContent="Comparing imported media · no render generated here";}
    toast(isReference?"Reference loaded for comparison.":"Shot loaded locally. Connect the same source in your ComfyUI graph.");
  }
  sourceVideo.addEventListener("loadedmetadata",()=>{$("duration").textContent=timecode(sourceVideo.duration);$("source-resolution").textContent=`${sourceVideo.videoWidth} × ${sourceVideo.videoHeight}`;});
  sourceVideo.addEventListener("timeupdate",syncPlayback);sourceVideo.addEventListener("ended",pause);
  for(const video of [sourceVideo,referenceVideo])video.addEventListener("error",()=>toast("This browser cannot decode that video. Try an MP4 with H.264 video."));
  sourceImage.addEventListener("error",()=>{$("viewer").querySelector(".media-error").hidden=false;});
  $("play-button").addEventListener("click",async()=>{if(sourceVideo.paused){try{await sourceVideo.play();if(!referenceVideo.hidden)await referenceVideo.play();$("play-button").innerHTML=icon("pause");$("play-button").setAttribute("aria-label","Pause source clip");}catch{pause();toast("Unable to play this clip in your browser.");}}else pause();});
  $("scrubber").addEventListener("input",()=>{sourceVideo.currentTime=sourceVideo.duration*Number($("scrubber").value)/1000;syncPlayback();});
  $("source-file").addEventListener("change",event=>importMedia(event.target.files[0],false));$("reference-file").addEventListener("change",event=>importMedia(event.target.files[0],true));
  $("replace-source").addEventListener("click",()=>$("source-file").click());$("import-reference").addEventListener("click",()=>$("reference-file").click());
  $("comparison").addEventListener("input",event=>$("viewer").style.setProperty("--split",`${event.target.value}%`));
  document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>{document.querySelectorAll("[data-view]").forEach(item=>{item.classList.toggle("active",item===button);item.setAttribute("aria-pressed",String(item===button));});$("viewer").dataset.view=button.dataset.view;}));
  document.querySelectorAll("[data-filter]").forEach(button=>button.addEventListener("click",()=>{filter=button.dataset.filter;document.querySelectorAll("[data-filter]").forEach(item=>{item.classList.toggle("active",item===button);item.setAttribute("aria-pressed",String(item===button));});renderLibrary();}));
  $("effect-search").addEventListener("input",renderLibrary);
  $("favorite-button").addEventListener("click",()=>{favorites.has(selected.id)?favorites.delete(selected.id):favorites.add(selected.id);persistFavorites();$("favorite-button").setAttribute("aria-pressed",String(favorites.has(selected.id)));$("favorite-button").setAttribute("aria-label",favorites.has(selected.id)?"Unsave effect":"Save effect");renderLibrary();});
  for(const id of ["strength","guidance"])$(id).addEventListener("input",refreshSliders);
  for(const id of ["width","height"])$(id).addEventListener("input",refreshDimensions);
  document.querySelectorAll("[data-size]").forEach(button=>button.addEventListener("click",()=>{const [width,height]=button.dataset.size.split(",");$("width").value=width;$("height").value=height;refreshDimensions();}));
  $("prompt-suggestion").addEventListener("click",()=>{$("prompt").value=selected.prompt_hint||"";$("prompt").focus();});
  $("reset-button").addEventListener("click",()=>{writeParameters(safeDefaults(selected));toast("Effect controls reset to the model’s starting values.");});
  $("help-button").addEventListener("click",()=>$("help-dialog").showModal());document.querySelector(".dialog-close").addEventListener("click",()=>$("help-dialog").close());
  $("fullscreen-button").addEventListener("click",async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $("viewer").requestFullscreen();}catch{toast("Fullscreen is not available in this browser view.");}});
  $("apply-button").addEventListener("click",apply);
  $("import-recipe").addEventListener("click",()=>$("recipe-file").click());
  $("recipe-file").addEventListener("change",async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>256000)throw new Error("Recipe is too large. Choose a settings-only JSON file.");const clean=validateRecipe(JSON.parse(await file.text()),effects);select(effects.find(effect=>effect.id===clean.effect),clean.parameters);toast("Recipe imported. Your controls are ready.");}catch(error){toast(`Could not import: ${error.message}`);}finally{event.target.value="";}});
  document.addEventListener("keydown",event=>{if(event.key==="/"&&!/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)){event.preventDefault();$("effect-search").focus();}if((event.metaKey||event.ctrlKey)&&event.key==="Enter"){event.preventDefault();apply();}});
  window.addEventListener("pagehide",()=>{if(sourceUrl)URL.revokeObjectURL(sourceUrl);if(referenceUrl)URL.revokeObjectURL(referenceUrl);});
  select(selected);
}
