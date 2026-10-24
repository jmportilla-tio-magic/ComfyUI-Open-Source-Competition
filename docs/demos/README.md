# Original Lightricks demo previews

These animated GIFs are converted from the original **Lightricks LTX-2.5 Creative Lab** demo videos linked below. They show motion and the upstream comparison layouts directly in the README. Retrieved on October 24, 2026 after the user accepted the repositories’ access terms.

- Each GIF uses the first **up to 4.5 seconds**, at **8 fps**, with reduced dimensions and a 128-color palette. Frame sampling preserves the original playback speed; no interpolated or generated motion is added. See [previews.json](previews.json) for per-file dimensions, duration, frame count, size, and source hashes.
- The original comparison layout is preserved without cropping. GIFs repeat for convenience; their loop boundaries are preview edits, not evidence that the model output loops seamlessly.
- GIFs omit audio and cannot represent an HDR master or full-resolution fine detail. Use the original videos and model documentation for those properties.
- Original videos remain hosted by Hugging Face and may require sign-in and acceptance of the model repository’s access terms. No credentials, cookies, or temporary signed URLs are included here.
- The previews are credited to Lightricks and are not relicensed under the application’s MIT license. Refer to the original model card for the upstream material and terms.
- No model weights were downloaded, and no LTX inference was run to create these previews. They are upstream examples, not OpenPositive validation renders.
- Pixel Upscaler has no example video/image on its current model card. Its README section says so explicitly; no substitute output is presented as an official demo.

## Conversion

With a locally obtained original clip and FFmpeg installed, the previews use this filter chain (substitute the width recorded in `previews.json`):

```bash
ffmpeg -i original.mp4 -t 4.5 \
  -filter_complex "fps=8,scale=384:-2:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff:max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" \
  -loop 0 preview.gif
```

Widths are reduced where necessary to keep each preview below 2.5 MB. Only the finished GIFs and public source references are distributed; downloaded originals stay outside the repository.

## Sources

| Capability | Preview | Original video | Original model card |
| --- | --- | --- | --- |
| Day to night | [day-to-night.gif](day-to-night.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Day-To-Night/resolve/main/examples/Examples_6__step_003000_02.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Day-To-Night) |
| Clean plate | [clean-plate.gif](clean-plate.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Clean-Plate/resolve/main/examples/clean_plate_001_output_sbs.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Clean-Plate) |
| Water simulation | [water-simulation.gif](water-simulation.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Water-Simulation/resolve/main/examples/rabbit_forest_sbs.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Water-Simulation) |
| Pixel upscaler ×2 | No published demo | — | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Pixel-Spatial-Upscaler) |
| Deblur | [deblur.gif](deblur.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Deblur/resolve/main/examples/Examples_4__00_15485932_sbs.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Deblur) |
| Decompression | [decompression.gif](decompression.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Decompression/resolve/main/examples/Examples_2__27_sunflower_field_sbs.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Decompression) |
| Colorization | [colorization.gif](colorization.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Colorization/resolve/main/examples/Examples_5__00_rabbit_rocks_sbs.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Colorization) |
| Cinemagraph | [cinemagraph.gif](cinemagraph.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-LoRA-Cinemagraph/resolve/main/examples/Glasses_LTX_2.3_i2v_00272_.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-LoRA-Cinemagraph) |
| Slow motion | [slow-motion-control.gif](slow-motion-control.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-LoRA-Slow-Motion-Control/resolve/main/examples/ny_street_sbs.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-LoRA-Slow-Motion-Control) |
| Ingredients | [ingredients.gif](ingredients.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Ingredients/resolve/main/examples/ingredients_lora_1.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Ingredients) |
| SDR to HDR | [sdr-to-hdr.gif](sdr-to-hdr.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-SDR-To-HDR/resolve/main/examples/sdr-to-hdr-boxing_sbs.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-SDR-To-HDR) |
| Layout to render | [layout-to-render.gif](layout-to-render.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Layout-To-Render/resolve/main/examples/blocking.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Layout-To-Render) |
| Refine details | [refine-details.gif](refine-details.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Refine-Details/resolve/main/examples/refine_forest_stream_crop.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Refine-Details) |
| Restore archive | [restore.gif](restore.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Restore/resolve/main/examples/restore_family_meal_1954_crop.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Restore) |
| Alpha matte | [alpha-gen.gif](alpha-gen.gif) | [Original MP4](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Alpha-Gen/resolve/main/examples/dragon_fire_sbs.mp4) | [Model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Alpha-Gen) |
