# LTX Creative Lab model reference

The catalog in `data/effects.json` covers all 15 adapters in the official [LTX-2.5 Creative Lab collection](https://huggingface.co/collections/Lightricks/ltx-25-creative-lab), checked on 2026-10-23. Filenames and operating requirements below come from the linked Lightricks model cards. Weights are not redistributed by this project. Hugging Face requires account access and acceptance of the model terms before downloading gated files.

## Choose the operation by its input

| Operation | Input | Main requirement | Official model card |
| --- | --- | --- | --- |
| Day to night | Daytime video | Reference at 24 fps; train bucket 768×448, 97 frames; start at strength 1 | [Day-To-Night](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Day-To-Night) |
| Clean plate | Video containing moving subjects | Full-frame removal with enough background visible; no region mask | [Clean-Plate](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Clean-Plate) |
| Water simulation | Dry video | `ADD WATER` prompt; native-resolution stage-1-only inference | [Water-Simulation](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Water-Simulation) |
| Pixel upscaler ×2 | Clean low-resolution video | Reference is half the output width and height; invents plausible detail | [Pixel-Spatial-Upscaler](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Pixel-Spatial-Upscaler) |
| Deblur | Defocused video | `DEBLUR` prompt; designed for defocus rather than motion blur | [Deblur](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Deblur) |
| Decompression | Compressed video | `ENHANCE QUALITY` prompt; targets compression artifacts specifically | [Decompression](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Decompression) |
| Colorization | Monochrome video | `COLORIZE` prompt with the desired colors; inferred color is not historical evidence | [Colorization](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Colorization) |
| Cinemagraph | Still image | `CINEMAGRAPH_MOTION` prompt; describe the isolated moving element and the frozen surroundings | [Cinemagraph](https://huggingface.co/Lightricks/LTX-2.5-22b-LoRA-Cinemagraph) |
| Slow motion | Still image | Dual-rate conditioning: motion fps = playback fps ÷ speed; not a video retimer | [Slow-Motion-Control](https://huggingface.co/Lightricks/LTX-2.5-22b-LoRA-Slow-Motion-Control) |
| Ingredients | Composite reference sheet | Repeat the sheet as a static reference for at least 121 frames | [Ingredients](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Ingredients) |
| SDR to HDR | SDR video | Dedicated HDR pipeline with scene embeddings, color transforms and HDR export | [SDR-To-HDR](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-SDR-To-HDR) |
| Layout to render | Playblast plus art-directed first frame | Two-stage workflow; first-frame guide at -1; adapter also active in stage 2 | [Layout-To-Render](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Layout-To-Render) |
| Refine details | Video | Upsize reference to output canvas; tiled fusion with 1024×576 tiles | [Refine-Details](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Refine-Details) |
| Restore archive | Damaged archive video | Deinterlace first; tiled fusion with 960×544 tiles and 97-frame windows | [Restore](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Restore) |
| Alpha matte | RGB video | Empty prompt; native-resolution stage 1; maximum 145 frames | [Alpha-Gen](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Alpha-Gen) |

## Base components

The [LTX-2.5 split pack](https://huggingface.co/Lightricks/LTX-2.5) supplies the distilled transformer, Gemma 4 text encoder and video VAE. Audio generation adds the audio VAE. Two-stage workflows add the x2 latent spatial upscaler. The catalog records exact repository-relative filenames and destination model directories. The BF16 variants work across native ComfyUI and official Python pipelines; Comfy-specific INT8 variants are not interchangeable with Python pipeline weights.

Day-to-night and Cinemagraph publish 30-step, classifier-free-guidance recipes. The catalog recommends the dev transformer for those non-distilled settings and includes its exact filename as an optional base asset. That recommendation is a sampling-family compatibility choice: it does not mean the adapter cannot run on a distilled transformer. When adapting them to distilled workflows, use that workflow's fixed schedule and CFG rather than carrying the 30-step settings over unchanged. The studio prepares conditioning; it does not switch your connected base model or sampler automatically.

The SDR-to-HDR adapter additionally ships `ltx-2.5-22b-ic-lora-sdr-to-hdr-scene-emb.safetensors`. Its dedicated workflow consumes those embeddings without a text encoder. An ordinary RGB sampler and MP4 encoder do not implement the ACEScct conversion, seam-keyframe conditioning, EXR sidecar and HLG master that the card requires.

## Workflow contracts

Most operations use in-context reference latents, not only a LoRA loader. Lightricks maintains the [ComfyUI-LTXVideo nodes and example workflows](https://github.com/Lightricks/ComfyUI-LTXVideo). The model cards are the source of truth for which graph and conditioning are required. Adapter presence alone does not mean a graph is ready to execute.

Common single-stage geometry uses dimensions divisible by 32 and `8n+1` frames. Layout and slow-motion two-stage examples require dimensions divisible by 64. Preserve source aspect ratio and frame timing; padding, cropping and resampling must be deliberate. The catalog distinguishes published training defaults from universal guarantees.

Restore was trained on LTX-2.3 and officially tested with the LTX-2.5 stack. Refinement and restoration need tiled sampling above their training tile size; their larger results are generated reconstructions, not recovered forensic detail. Alpha Gen returns a grayscale matte to composite with the source, not an automatically encoded RGBA file.

## License and verification

This repository's code license does not license the model weights. Consult the [LTX-2.x Community License](https://huggingface.co/Lightricks/LTX-2.5/blob/main/LICENSE) and the gated repository conditions before using or distributing the models.

The checked-in catalog validates names, files and requirements from published model cards. It is not evidence that inference has run on the current computer or a company deployment. Validate the complete selected graph on the target GPU and on representative footage before calling a deployment production-ready.
