# 2026-11-20: Road width from flat-ground geometry, not Depth Anything V2

## Context

The plan said "Depth Anything V2 → road width per segment". The metric outdoor checkpoint `depth-anything/Depth-Anything-V2-Metric-Outdoor-Small-hf` (Apache-2.0; the Base and Large ones are non-commercial) was tried on the 12 test photos.

## Probe

Width from depth needs the lens focal length (assumed: 70° horizontal view). Width from flat-ground geometry needs the camera height (assumed: 1.6 m, a standing photographer). None of the photos has a known road width, camera height or lens, so neither number can be called right.

The one photo where the road mask gave clean edges in all sampled rows (`quangnam`, a village path):

| method | width over 10 rows |
|---|---|
| depth model | 5.1–6.1 m |
| geometry, fitted horizon | 3.0–3.1 m (fit residual 0.04) |

Depth at the bottom of the frames was 5–8 m, while plain geometry for a standing person gives 3–4 m there. The model was trained on car-mounted driving scenes (Virtual KITTI). Inferred, not measured: the depth model overestimates near-field distance for a low phone camera, and so the width.

## Decision

Use flat-ground geometry with a fitted horizon (`pipeline/width/estimate.py`). It needs one input the rider can measure once (camera height). Lens focal length and camera tilt cancel out. It also runs without a second model, at the speed of segmentation alone.

## Consequences

- Rough terrain, hills and bends give a blank width. Straight stretches carry the estimate, and fusion takes the median per OSM way.
- The width is unchecked until a ride passes a road of measured width (tape measure, 3 spots).
