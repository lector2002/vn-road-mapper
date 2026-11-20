# AI Context

> Updated: 2026-11-20
> Level: Medium
> Status: active

## Project
vn-road-mapper: phone video from a motorbike → AI tags rural Vietnamese roads (surface, width, flood passability) → OpenStreetMap. For riders, ambulances and commune health stations.

## Current State
Prototype. Stages 1–2 of 6 (frames, segmentation) work on a demo clip. No real ride recorded yet. Not a git repo yet.

## Done
- [x] frames stage: video + GPX → 2 fps frames + `frames.csv` (lat, lon, heading).
- [x] segmentation stage: frames → `segmentation.csv` (surface label + class shares) + overlays.
- [x] Model probe and decision: SegFormer-B2 ADE20K (see Decisions).

## Now
- Record a real 1–2 min ride with a GPX logger and run both stages on it.

## Next
1. Check the frame/GPS sync on the real ride (Android `creation_time` can be the stop time).
2. Label ~200 VN frames (paved/dirt/mud/water) and fine-tune SegFormer-B2.
3. depth stage: Depth Anything V2 → road width.
4. mapmatch stage: OSRM/Valhalla onto OSM ways.

## Feature Map
- Pipeline > Frames - cut a ride video into GPS-tagged frames - `pipeline/frames/extract.py`
- Pipeline > Segmentation - label the road surface per frame - `pipeline/segmentation/segment.py`
- Pipeline > Depth / Mapmatch / Fusion / Export - not started - `pipeline/*/README.md`
- Capture app - not started - `capture/`

## Key Files
- `README.md` - plan, pipeline, roadmap.
- `HANDOFF.md` - original task list (GitHub push, sample clip, Devin prompts).
- `pipeline/frames/gps.py` - GPX loading, interpolation, bearing.
- `pipeline/segmentation/segment.py` - ADE20K → 6-class mapping, road box, overlays.
- `docs/decisions/` - decision records.

## Commands
- Setup (as run 2026-11-20): `py -3.12 -m venv .venv`, then `.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu`, then `.venv/Scripts/python -m pip install transformers gpxpy pillow numpy pytest`. `pip install -r requirements.txt` was not run (it also pulls packages for later stages). `scipy` is in the venv for the model probe only.
- Test: `.venv/Scripts/python -m pytest tests -q` (add `RUN_MODEL_TESTS=1` for the real model)
- Run: `python -m pipeline.frames.extract ride.mp4 ride.gpx --out output/ride1` then `python -m pipeline.segmentation.segment output/ride1/frames --out output/ride1`

## Decisions
- 2026-11-20: SegFormer-B2 ADE20K instead of Vistas, because no SegFormer-B2 Vistas checkpoint exists and Vistas labels dirt roads as `Road`. `docs/decisions/2026-11-20-segmentation-model.md`.
- 2026-11-20: Frame time = video start + index / fps (measured: ffmpeg `fps` filter puts frame i at i/fps s).
- 2026-11-20: `confidence` = pixel share of the winning class in the road box, not a model probability.

## Avoid
- Committing video: `.gitignore` blocks `*.mp4`/`*.mov`, so HANDOFF's "upload clip to data/samples" will not commit. Link the clip instead.
- Committing `output/` (ignored).
- Wikimedia probe photos: keep out of the repo (licences vary).

## Last Session
- Done: frames + segmentation stages, 18 tests, demo run on 12 Wikimedia photos.
- Pending: real ride clip; git init + GitHub push (user).
- Blocker: none.
