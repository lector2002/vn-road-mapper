# 2026-11-20: First run on a real motorbike ride (KartaView, Thanh Hóa)

## Data

KartaView sequence 3846125: a phone on a motorbike, 15.9 km, Hoằng Hóa district and Thanh Hóa city, September 2021. Every 2nd photo was used: 559 frames, about 6 s apart. The phone points down at the road, so the horizon is often above the frame. All sampled roads are paved (asphalt or concrete); one stretch is wet dirt.

Commands:

```bash
python -m tools.kartaview 3846125 --out output/kv-3846125 --every 2
python -m pipeline.mapmatch.match output/kv-3846125/frames.csv --out output/kv-3846125
python -m pipeline.segmentation.segment output/kv-3846125/frames --out output/kv-3846125 --overlays 12
python -m pipeline.width.estimate output/kv-3846125/frames --out output/kv-3846125 --camera-height 1.1
python -m pipeline.fusion.fuse output/kv-3846125 --out output/kv-3846125
python -m pipeline.export.export output/kv-3846125/ways.csv --out output/kv-3846125
```

## Results

| check | result |
|---|---|
| Surface, 48 frames labeled by hand (47 paved, 1 wet dirt) | 48 of 48 right |
| Surface, all frames | 528 of 559 `paved`, 6 `dirt`, 4 `water`, 21 `vegetation`/`other` |
| Surface per OSM way, where OSM has a `surface` tag | 10 of 10 agree (all `asphalt`) |
| Mapmatch vs KartaView's own matcher, same OSM way | 454 of 534 frames (85%); median distance from road 1.9 m |
| Export | 39 ways: 19 `add` (untagged residential roads, proposed `paved`), 7 `agree`, 13 `weak` |
| Width, first version | 69 frames got a width; those on main roads about 10 m wide said 0.6–3.9 m, so they were wrong |
| Width, after the fix below | 21 of those 69 kept a width. Most sit on narrow village roads with both edges in view (2.3–3.0 m). At least one is still wrong: 1.38 m at a junction (frame 340) |
| Speed | 1.3 s per frame for segmentation, the same again for width (CPU) |

## Second ride

KartaView sequence 3846189 (Thanh Hóa, 22 km, every 3rd photo: 475 frames, about 9 s apart), surface and mapmatch only:

| check | result |
|---|---|
| Surface, all frames | 463 of 475 `paved`, 4 `water`, 1 `dirt`, 7 `other` |
| Surface per OSM way with a `surface` tag | 18 of 18 agree (all `asphalt`) |
| Mapmatch vs KartaView, same OSM way | 309 of 435 frames (71%) |

All 4 `water` frames are false. 3 are portrait photos with the road on its side (see below), 1 is a level shot of pale asphalt (frame 266). The `dirt` frame shows a dusty, loose patch. The lower mapmatch agreement may come from the wider frame spacing and divided main roads; which matcher is right was not checked.

## What this changed

- Width: on a wide road the road fills the frame in most rows, and the few rows that fit a line were cut short by vehicles or walls. A new check rejects a fit when it predicts a road narrower than the frame in rows where the road actually fills the frame (`pipeline/width/estimate.py`).
- Width only works where both road edges are in view: narrow rural roads, which are the target. Main roads get no width.
- False `water`: 76 of the 1,034 photos on both rides are portrait images (2160×3840) with the scene turned 90°, sky on the right. The capture app saved landscape shots as portrait. 7 of the 8 false `water` frames were among them. `tools/kartaview.py` now turns portrait photos 90° to the left. 64 of the 76 came out upright. The other 12 had the sky on the left and came out upside down; after the re-run 11 of them give `other` (no vote) and 1 gives `paved`. The photos carry no orientation tag that could tell the two cases apart. After the re-run only 1 false `water` frame is left (ride 2, frame 266). No way changed its surface; 6 ways lost a false `water_share`.
- A sharpness score (variance of the Laplacian) did not explain the false `water`: those frames scored 7.0–103.6, around the ride median of 8.3–12.6, and the blurriest frames were labeled `paved` correctly. So there is no blur filter.
- A tilt check (skip frames where the road is not at the bottom) was tried first. It caught 51 of the sideways frames but also skipped 3 good ones, and with the importer fix it only had false hits, so it was removed.
- The tables above are from the first run. After the re-run (turned photos, and the surface label from ground pixels only, see `2026-11-20-kartaview-can-tho.md`): ride 1 is 539 `paved`, 3 `dirt`, 0 `water`, 17 `vegetation`/`other`; ride 2 is 465 `paved`, 1 `dirt`, 1 `water`, 8 `other`. The 48-frame hand sample is 47 right and 1 `other` (no vote; frame 132, one of the turned photos). Width: 22 frames instead of 21. Export on ride 1: 20 `add`, 7 `agree`, 12 `weak`.

## What this does not show

- Unpaved, muddy or flooded roads: almost none in this ride. The surface model's weak spots from the photo test are still untested on real rides.
- Width accuracy: no road here has a measured width, and the camera height (1.1 m) is a guess.
- The 19 `add` proposals are from 2021 imagery and were not checked against current conditions. Do not upload them.
