# segmentation stage

Labels the road surface in each frame as `paved`, `dirt`, `mud`, `water`, `vegetation` or `other`.

## Usage

```bash
python -m pipeline.segmentation.segment output/ride1/frames --out output/ride1
```

Output:

```
output/ride1/segmentation.csv   filename,label,confidence,paved,dirt,mud,water,vegetation,other,tilt
output/ride1/overlays/*.jpg     5 frames spread over the clip, colored by class
```

`segmentation.csv` joins with `frames.csv` on `filename`.

## How a frame gets its label

1. The model labels every pixel with one of 150 ADE20K classes.
2. Each ADE20K class maps to one of our 6 classes (`ADE20K_TO_CLASS` in `segment.py`).
3. Only the road in front of the bike counts: the bottom 40% of the frame, middle 60% of the width (the yellow box in the overlays).
4. `label` is the class with the most pixels in that box.
5. `confidence` is the share of the box that class covers (0–1). It is a pixel share, not a model probability.
6. The other six columns give the share of every class, so later stages can use them.
7. `tilt` tells if the phone was upright: the angle in degrees from "road below everything else" to where the road actually sits. 0 is upright, ±90 is a phone on its side. It is blank when the road covers less than 40% or more than 98% of the frame. Fusion skips frames tilted more than 60°.

On two KartaView rides (1,034 frames), 54 frames had a tilt above 60°. By eye, 51 of them were tilted; the other 3 were upright with a vehicle close on one side.

## Model

`nvidia/segformer-b2-finetuned-ade-512-512` (110 MB, downloads on first run). About 1.2 s per frame on CPU (measured on a desktop, 1280×720 frames).

No SegFormer-B2 checkpoint for Mapillary Vistas exists on Hugging Face, and the Vistas label set calls dirt roads `Road`. See `docs/decisions/2026-11-20-segmentation-model.md`.

## Known limits of this baseline

- `mud` is never output. ADE20K has no mud class; it needs fine-tuning on VN frames.
- Floodwater that covers a road can be labeled `paved` (1 of 3 flood test photos).
- Narrow concrete village paths can come out as `dirt` (`path` maps to `dirt`).
- If the road is not in the bottom-center of the frame, the label describes the roadside instead. Mount the phone to face straight ahead.
- The frame shape matters: the same photo with black side bars changed 2 of 12 labels (a flood photo went from `water` to `paved`). Feed full camera frames, not letterboxed ones.

On 12 Wikimedia Commons road photos, the label matched a human reading for 6 of 11 (one photo was unclear).

## Options

- `--overlays N` — number of overlay images (0 for none).
- `--model ID` — another Hugging Face semantic-segmentation model with ADE20K labels.

Tests: `RUN_MODEL_TESTS=1 python -m pytest tests` also runs the real model.
