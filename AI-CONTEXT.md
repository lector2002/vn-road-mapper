# AI Context

> Updated: 2026-11-21
> Level: Medium
> Status: active

## Project
vn-road-mapper: phone video from a motorbike → AI tags rural Vietnamese roads (surface, width, flood passability) → OpenStreetMap. For riders, ambulances and commune health stations. Public repo: github.com/lector2002/vn-road-mapper.

## Current State
Prototype. All six pipeline stages run end to end on test data and on two public KartaView motorbike rides (Thanh Hóa, 2021). On those rides paved roads come out right (47/48 hand sample right, 1 no vote; 28/28 OSM-tagged ways agree). On public helmet-camera footage of unpaved roads (Cần Thơ), 112 of 142 surface votes labelled by eye are right; 27 of the 30 errors are dirt called paved. Width works only on narrow roads with both edges in view and is unconfirmed. Mud and flood are untested on real footage. No own rides: the user will not record video, so test data comes from public imagery. CI runs the tests on every push.

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
- [x] KartaView importer turns portrait photos (scene on its side) 90°; these caused 7 of 8 false `water` frames. 64 of 76 come out upright, 12 upside down (no vote).
- [x] Surface label from ground pixels only (`other` left out of the box). Unpaved and OSM-width test: `docs/evaluation/2026-11-20-kartaview-can-tho.md`.
- [x] 177 Cần Thơ frames labelled by eye (`docs/evaluation/data/`). A linear probe on SegFormer features gets 122 of 142 right on unseen rides (SegFormer 112) and 7 of 7 ways (SegFormer 5), but calls 11 paved frames unpaved; not adopted. `docs/evaluation/2026-11-20-can-tho-labels-and-probe.md`.

## Now
- Nothing in progress.

## Next
Plan and expectations per phase: `docs/roadmap.md` (public imagery first, nothing that needs paid riders or labellers). Next is Phase 1, a trusted Vietnamese test set.
1. Dirt called `paved`: more Vietnamese training rides. StreetSurfaceVis (German photos) made 238 of 1,008 paved Thanh Hóa frames unpaved. Mapillary images on OSM unpaved-tagged roads: only 84 usable from 11 rides; with Cần Thơ labels 125 of 142 right, still 8 paved called unpaved. Next option: hand labels on Mapillary images of untagged rural roads (user decision). RSCD 2022 (6.0 GB) is untried: its download link returned 502 on 2026-11-20. Test with the same pass rule and the Cần Thơ labels.
2. Find public phone footage of mud and flooded roads on Mapillary (token in the user env var `MAPILLARY_TOKEN`, read-only app).
3. Width: needs footage on a road of known width with a known camera height; not available from public data so far.
4. Flood layer (PostGIS) from `water_share` across flood-season rides.
5. Discuss with OSM Vietnam community before any upload.

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
- `docs/roadmap.md` - phased plan with expected results.
- `pipeline/run.py` - all stages in one command.
- `tools/benchmark.py` - surface benchmark on the hand-labelled KartaView photos.
- `.github/workflows/test.yml` - CI; `.github/workflows/model.yml` - weekly real-model tests.

## Commands
- Setup (as run 2026-11-20): `py -3.12 -m venv .venv`; `.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu`; `.venv/Scripts/python -m pip install transformers gpxpy pillow numpy pytest`. `scipy` and `osmium` are also in the local venv (probe and .osc check only). `pip install -r requirements.txt` was not run.
- Test: `.venv/Scripts/python -m pytest tests -q`. `RUN_MODEL_TESTS=1` adds the real model; `RUN_NETWORK_TESTS=1` adds Valhalla and OSM API calls.
- Setup now: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu`, then `pip install -r requirements-model.txt -r requirements-dev.txt`. transformers 5.x needs torchvision for the SegFormer image processor.
- Run: `python -m pipeline.run --kartaview 3846125 --every 20 --camera-height 1.1 --out output/kv` (about 2 min on CPU, 26 ways); see README "Run".
- Benchmark: `python -m tools.benchmark docs/evaluation/data/2026-11-20-can-tho-hand-labels.csv --out output/bench-can-tho` (about 15 min, mostly downloads). On 2026-11-21 (CDN photos, transformers 5.20): 109 of 142 frames right, 30 unpaved called paved, 3 paved called unpaved, 5 of 8 ways. The 2026-11-20 numbers (112 of 142, 5 of 7 ways) came from the storage-host photos and an older transformers; the CDN serves `pr:sharp` (sharpened) copies.

## Decisions
- 2026-11-20: SegFormer-B2 ADE20K instead of Vistas: no SegFormer-B2 Vistas checkpoint; Vistas labels dirt roads `Road`. `docs/decisions/2026-11-20-segmentation-model.md`.
- 2026-11-20: Width from flat-ground geometry with fitted horizon, not Depth Anything V2: needs only camera height; depth model looked biased near the camera. `docs/decisions/2026-11-20-width-method.md`.
- 2026-11-20: Valhalla `auto` costing: matched 36/36 test points vs 20/36 for `motor_scooter`.
- 2026-11-20: Export proposes only generic `paved`/`unpaved`, and only where OSM has no tag or the other family; never uploads.
- 2026-11-20: Frame time = video start + index / fps (measured with ffmpeg showinfo).
- 2026-11-20: `confidence` = share of the ground pixels in the road box that the winning class covers (`other` left out, at least 40% ground), not a model probability.
- 2026-11-20: No 20 m piece vote and no 10 m distance cut in fusion (from SurfaceAI): on KartaView runs they changed no way for the better, and the cut emptied ways on a wide road. Re-check on phone video with stops. HeiGIT Mapillary predictions cover none of our ways. `docs/evaluation/2026-11-20-heigit-and-piece-vote.md`.
- 2026-11-20: No blur filter and no tilt filter: the false `water` frames were portrait photos with the scene on its side, fixed in the importer. A tilt check in fusion was tried and removed (only false hits left after the importer fix).

## Avoid
- Uploading `changes.osc` from test runs: the demo proposals come from photos of other roads.
- Sending real riders' GPS tracks to the public Valhalla server at scale; self-host for real data.
- Committing video (`*.mp4` ignored) or `output/` (ignored). Wikimedia probe photos stay out of the repo.
- Letterboxed frames: side bars changed 2 of 12 surface labels.
- Committing KartaView images: CC BY-SA 4.0; download them into `output/` only.
- Uploading the KartaView `add` proposals: 2021 imagery, not checked against current roads.

## Last Session
- 2026-11-21: roadmap (`docs/roadmap.md`), one-command run, benchmark script, requirements split, model CI, KartaView CDN fix.
- Before: stages 1–6, CI, LICENSE; KartaView importer and real-ride evaluation; width fix; portrait-photo fix in the importer; ground-only surface label; unpaved and OSM-width test; HeiGIT comparison and 20 m piece-vote probe (no code change); 177 Cần Thơ hand labels and a SegFormer-feature probe, with and without StreetSurfaceVis and Mapillary (not adopted).
- Pending: `output/demo` is a stale broken run (delete by hand).
- Blocker: none.
