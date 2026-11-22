# Phase 4: width classes on public imagery

> 2026-11-21. Public data only: Geofabrik's OSM Vietnam extract and Mapillary photos. No rides, no paid labelling.

## Result

No method gives a usable width class on public imagery yet. On the 22 test ways, calling every road `two_cars` gets 15 right. No method from the image beats that: the best, scaling from vehicles, classes 14 ways and gets 9 right, the same as calling those 14 `two_cars`.

| Method (test split, 22 ways) | Ways with a class | Right | Right of those classed |
|---|---|---|---|
| Shipped flat-ground fit, camera height 1.2–1.6 m | 1 | 1 | 1 of 1 |
| Fixed horizon, carriageway only (horizon and height fitted on dev) | 21 | 10 | 10 of 21 |
| Scale from detected cars and motorbikes | 14 | 9 | 9 of 14 |
| Every road `two_cars` (baseline) | 22 | 15 | 15 of 22 |

Dev split (23 ways): shipped fit 1 of 4 classed, fixed horizon 12 of 23, vehicle scale 10 of 16, baseline 15 of 23.

What ships in this PR is the class itself: `widths.csv`, fused ways and `proposals.csv` now carry `width_class` (`motorbike` under 2.5 m, `one_car` 2.5–4 m, `two_cars` over 4 m) next to `width_m`, blank whenever the width is blank. It is meant for own rides with a measured camera height, where the flat-ground fit works (`docs/decisions/2026-11-20-width-method.md`). It never becomes an OSM tag.

## Data

**Reference widths.** The Geofabrik extract of 2026-11-21 has 1,501 minor roads (`residential`, `service`, `path`, `tertiary`, `unclassified`, `track`, `living_street`, `road`) with a plain-number `width` (1,395) or `est_width` (106); 1,434 of them are 0.5–20 m. By class: 676 under 2.5 m, 485 from 2.5 to 4 m, 340 over 4 m. The roadmap's "about 1,400" was an earlier count of `width` alone.

**Photos.** Mapillary has photos along 118 of those ways. Most first matches were at junctions or on the bigger road next to an alley, so `tools/widthcheck.py` keeps only photos within 5 m of the way, at least 15 m from either end, looking along it (within 20°), with no other highway within 3 m of being as close, and at most 12 per way and 3 per Mapillary sequence. That leaves 216 photos on 45 ways from 79 sequences: 28 ways in the north, 7 in the centre, 10 in the south. They are listed in [data/2026-11-21-width-photos.csv](data/2026-11-21-width-photos.csv).

**Split.** Each way is in `dev` or `test` by a hash of its id, fixed before any scoring: dev 23 ways (2 motorbike, 6 one-car, 15 two-car), test 22 ways (5, 2, 15). Settings were picked on dev only. Scores are per way: a way gets the class of the median width over its frames, and a way with no frame width gets no class.

**Caveats on the reference.**
- Photos and tags have no shared date. Photos are from 2015 to 2025, mostly 2025; when a tag was surveyed is unknown.
- Nobody checked these OSM widths. Some are guesses, and some may measure the paved part and others the whole space between walls.
- Two-car roads are two thirds of the sample. Narrow lanes are where public imagery is thinnest: most Mapillary photos come from cars, which cannot drive a motorbike-only lane. Only 7 motorbike-only ways had usable photos.

## Methods and why each fails

1. **Shipped flat-ground fit** (`pipeline.width.estimate`). It gives a width on 5 of 216 frames, whatever the camera height. City dashcam photos almost always show the road running into the frame edge, parked cars and motorbikes on it, and sidewalks the model calls `sidewalk`, which the pipeline counts as `paved`. The fit rejects those rows and leaves the frame blank, as designed. Its 5 widths put 3 one-car ways in `two_cars`.
2. **Fixed horizon, carriageway only.** It counts only ADE20K `road`, `earth`, `sand`, `path`, `dirt track`, `land` and `water` (no sidewalk), counts vehicles standing on the road as road, assumes the horizon at a fixed height in the frame, and keeps rows where the road touches the frame edge as a lower bound. The horizon (0.6 of frame height) and camera height (1.8 m) were the best of 65 pairs on dev. It classes nearly every way but gets 10 of 21 on test: it calls 3 of 5 motorbike lanes `one_car`, and 4 of 15 two-car roads `one_car`. Unknown lens, pitch and camera height move the whole scale, and one setting cannot fit cars, scooters and helmets together.
3. **Scale from vehicles.** A torchvision Faster R-CNN finds cars (1.75 m wide) and motorbikes (0.75 m) standing on the road, and the road width at the vehicle's wheel row is scaled from its box. Only ways with a whole car or motorbike in view get a class (14 of 22 on test). It finds 2 of the 4 motorbike lanes it classes, but box widths change with viewing angle and it calls 2 of 9 two-car roads `one_car`; overall it ties the `two_cars` baseline on the same ways, on dev (10 of 16) and test (9 of 14). It is the only method that finds narrow lanes at all, so it is the one to retry on KartaView motorbike footage.

## What would change this

- **Own rides with a measured camera height.** The flat-ground fit was built for that case; it still has no known-width check (see `docs/evaluation/2026-11-20-kartaview-can-tho.md`).
- **KartaView motorbike footage of narrow lanes.** KartaView's photo search allows a radius up to 500 m and 150 results per page and rate-limits quickly; a slow crawl of the 676 motorbike-only ways would show whether there is enough of it.
- **A road-only segmentation model** that does not mix sidewalk and carriageway, so the road edge is the kerb.

Until one of these lands, the pipeline should leave width blank on public imagery, which it does.

## Reproduce

```bash
python -m tools.widthcheck ways vietnam-latest.osm.pbf --out output/width
python -m tools.widthcheck photos output/width --frames output/width/frames   # MAPILLARY_ACCESS_TOKEN
python -m pipeline.width.estimate output/width/frames --out output/width --camera-height 1.4
python -m tools.widthcheck score output/width/photos.csv output/width/widths.csv
```

New Mapillary uploads change which photos are found, so a rerun may pick a slightly different set. Methods 2 and 3 were one-off experiments and are not in the pipeline.
