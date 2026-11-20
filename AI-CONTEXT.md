# AI Context

> Updated: 2026-11-20
> Level: Medium
> Status: active

## Project
vn-road-mapper: phone video from a motorbike → AI tags rural Vietnamese roads (surface, width, flood passability) → OpenStreetMap. For riders, ambulances and commune health stations. Public repo: github.com/lector2002/vn-road-mapper.

## Current State
Prototype. All six pipeline stages run end to end on test data and on two public KartaView motorbike rides (Thanh Hóa, 2021). On those rides paved roads come out right (48/48 hand sample; 28/28 OSM-tagged ways agree). Width works only on narrow roads with both edges in view. Unpaved, mud and flood are untested on real footage. CI runs the tests on every push.

## Done
- [x] frames: video + GPX → frames + `frames.csv` (time, lat, lon, heading).
- [x] segmentation: SegFormer-B2 ADE20K → surface label per frame (6 of 11 test photos right).
- [x] width: road mask + camera height → width per frame (flat-ground fit).
- [x] mapmatch: Valhalla `trace_attributes` → OSM way per frame.
- [x] fusion: majority vote per way across rides, water share, median width.
- [x] export: OSM API tags → `proposals.csv`, `changes.osc`, `review.html` map. No upload.
- [x] CI (GitHub Actions), MIT LICENSE.
- [x] `tools/kartaview.py`: public KartaView sequence → `frames/` + `frames.csv` (stand-in for a real ride).
- [x] First real-ride evaluation: `docs/evaluation/2026-11-20-kartaview-thanh-hoa.md`. Width now rejects fits that contradict frame-filling rows.

## Now
- Record a real 1–2 min ride with a GPX logger and measured camera height; pass one road of tape-measured width.

## Next
1. Run all stages on the real ride; check GPS sync (Android `creation_time` can be the stop time) and width against the tape.
2. Skip blurred frames by a sharpness score (blur caused all 4 false `water` labels on KartaView ride 2).
3. Find real unpaved, mud and flood footage (KartaView or own rides) to test the surface model's weak spots.
4. Label ~200 VN frames (paved/dirt/mud/water) and fine-tune SegFormer-B2 for mud and floodwater.
5. Flood layer (PostGIS) from `water_share` across flood-season rides.
6. Discuss with OSM Vietnam community before any upload.

## Feature Map
- Pipeline > Frames - cut a ride video into GPS-tagged frames - `pipeline/frames/extract.py`
- Pipeline > Segmentation - surface label per frame - `pipeline/segmentation/segment.py`
- Pipeline > Width - road width per frame - `pipeline/width/estimate.py`
- Pipeline > Mapmatch - OSM way per frame - `pipeline/mapmatch/match.py`
- Pipeline > Fusion - one surface + width per OSM way - `pipeline/fusion/fuse.py`
- Pipeline > Export - OSM edit proposals + review map - `pipeline/export/export.py`
- Tools > KartaView - public street imagery as test rides - `tools/kartaview.py`
- Capture app - not started - `capture/`

## Key Files
- `README.md` - plan, pipeline, run commands.
- `HANDOFF.md` - original task list.
- `pipeline/*/README.md` - usage and output columns per stage.
- `docs/decisions/` - decision records.
- `docs/evaluation/` - results on real rides.
- `.github/workflows/test.yml` - CI.

## Commands
- Setup (as run 2026-11-20): `py -3.12 -m venv .venv`; `.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu`; `.venv/Scripts/python -m pip install transformers gpxpy pillow numpy pytest`. `scipy` and `osmium` are also in the local venv (probe and .osc check only). `pip install -r requirements.txt` was not run.
- Test: `.venv/Scripts/python -m pytest tests -q`. `RUN_MODEL_TESTS=1` adds the real model; `RUN_NETWORK_TESTS=1` adds Valhalla and OSM API calls.
- Run: see README "Run".

## Decisions
- 2026-11-20: SegFormer-B2 ADE20K instead of Vistas: no SegFormer-B2 Vistas checkpoint; Vistas labels dirt roads `Road`. `docs/decisions/2026-11-20-segmentation-model.md`.
- 2026-11-20: Width from flat-ground geometry with fitted horizon, not Depth Anything V2: needs only camera height; depth model looked biased near the camera. `docs/decisions/2026-11-20-width-method.md`.
- 2026-11-20: Valhalla `auto` costing: matched 36/36 test points vs 20/36 for `motor_scooter`.
- 2026-11-20: Export proposes only generic `paved`/`unpaved`, and only where OSM has no tag or the other family; never uploads.
- 2026-11-20: Frame time = video start + index / fps (measured with ffmpeg showinfo).
- 2026-11-20: `confidence` = pixel share of the winning class in the road box, not a model probability.

## Avoid
- Uploading `changes.osc` from test runs: the demo proposals come from photos of other roads.
- Sending real riders' GPS tracks to the public Valhalla server at scale; self-host for real data.
- Committing video (`*.mp4` ignored) or `output/` (ignored). Wikimedia probe photos stay out of the repo.
- Letterboxed frames: side bars changed 2 of 12 surface labels.
- Committing KartaView images: CC BY-SA 4.0; download them into `output/` only.
- Uploading the KartaView `add` proposals: 2021 imagery, not checked against current roads.

## Last Session
- Done: stages 1–6, CI, LICENSE; KartaView importer and real-ride evaluation; width fix.
- Pending: own real ride; `output/demo` is a stale broken run (delete by hand).
- Blocker: none.
