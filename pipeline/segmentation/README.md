# segmentation stage

Labels the road surface in each frame as `paved`, `dirt`, `mud`, `water`, `vegetation` or `other`.

## Usage

```bash
python -m pipeline.segmentation.segment output/ride1/frames --out output/ride1
```

Output:

```
output/ride1/segmentation.csv   filename,label,confidence,paved,dirt,mud,water,vegetation,other
output/ride1/overlays/*.jpg     5 frames spread over the clip, colored by class
```

`segmentation.csv` joins with `frames.csv` on `filename`.

## How a frame gets its label

1. The model labels every pixel with one of 150 ADE20K classes.
2. Each ADE20K class maps to one of our 6 classes (`ADE20K_TO_CLASS` in `segment.py`).
3. Only the road in front of the bike counts: the bottom 40% of the frame, middle 60% of the width (the yellow box in the overlays).
4. `label` is the ground class (`paved`, `dirt`, `mud`, `water`, `vegetation`) with the most pixels in that box. `other` pixels (vehicles, people, bike parts, walls) are left out, because they hide the surface. If less than 40% of the box is ground, `label` is `other`.
5. `confidence` is the share of the ground pixels in the box that the winning class covers (0–1). It is a pixel share, not a model probability.
6. The other six columns give the share of every class, so later stages can use them.
7. With the shipped probe (`surface_probe.json`), frames SegFormer calls `paved` get the CLIP dirt check (`probe.py`).
8. Frames that would not vote (`vegetation`, `other`, or confidence under 0.5) get the road check: the box around the `paved` and `dirt` pixels in the bottom 55% of the frame goes to CLIP, which scores it against "concrete / asphalt / paved road" and "dirt / gravel road, muddy track" prompts. If CLIP and the majority of those pixels agree, that becomes the label, with CLIP's probability as `confidence`. This is what lets narrow delta concrete lanes in greenery vote (`docs/evaluation/2026-11-22-delta-road-crop.md`). `--no-probe` turns both checks off.

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

On 47 hand-labelled frames from KartaView rides on unpaved roads (Cần Thơ, helmet camera), 27 of the 32 frames that voted were right. 5 dirt-road frames were called `paved`; no paved road was called `dirt`. 15 frames gave no vote. Leaving `other` out of the box added 9 right votes and no wrong ones. See `docs/evaluation/2026-11-20-kartaview-can-tho.md`. A larger set of 142 voting frames gave 112 right: 27 dirt frames called `paved` and 3 paved frames called `dirt` (`docs/evaluation/2026-11-20-can-tho-labels-and-probe.md`).

## Options

- `--overlays N` — number of overlay images (0 for none).
- `--model ID` — another Hugging Face semantic-segmentation model with ADE20K labels.

Tests: `RUN_MODEL_TESTS=1 python -m pytest tests` also runs the real model.
