# Rechecking frames SegFormer calls vegetation (2026-11-22)

> Public data only: KartaView and Mapillary photos already in the label files. No rides, no paid labelling, nothing posted to OSM.

The owner's test spot check found that 10 of the 11 Hà Tĩnh (KartaView 725845) frames he calls unpaved come out `vegetation` or `other` and do not vote, while the dirt probe only rechecks `paved` frames ([spot check](2026-11-21-vn-test-owner-spot-check.md)). This tries the obvious fix: run the same CLIP probe on `vegetation` and `other` frames too, with its own threshold.

## Result: no gain, so it ships turned off

| Owner-checked test split | Now (probe on paved only) | Probe also on vegetation/other (grass threshold 0.875) |
|---|---|---|
| Clear frames right | 119 of 129 | 120 of 130 |
| Unpaved called paved | 8 of 36 | 8 of 36 |
| Paved called unpaved | 2 of 93 | 2 of 93 |
| Rides right | 3 of 4 | 3 of 4 |
| Hà Tĩnh 725845 frames switched to dirt | – | 0 of 10 |

The one extra right frame is a Ninh Bình frame (2879114_00026), not Hà Tĩnh. On the other sets the recheck does harm:

| | Now | Grass threshold 0.875 | Grass threshold 0.5 |
|---|---|---|---|
| Mekong dirt test set (not owner-checked yet): frames right | 47 of 55 | 47 of 66 | 48 of 78 |
| Mekong: paved called unpaved | 2 of 88 | 13 of 88 | 24 of 88 |
| Mekong: rides right | 9 of 18 | 8 of 18 | 7 of 18 |
| Mapillary test: paved called unpaved | 7 | 8 | – |
| Thanh Hóa paved ride (3846189): frames switched | 0 of 475 | 0 of 475 | – |

The code to run the recheck is in, but the shipped probe keeps `grass_threshold` at 1.0 (off), so the pipeline's output does not change.

## Why it does not work

- **The Hà Tĩnh frames are not a road.** Frames 00000–00057 of 725845 face sideways onto a lakeside park: lawns, brick paving, bare earth under trees, a balustrade over the water. The street (00059 on) is paved. Of the owner's 11 unpaved answers, the probe scores 9 at 0.000, one at 0.013 and one at 0.224, so no threshold that is safe elsewhere catches them. SegFormer's `vegetation` is a fair reading of these photos, and no vote is the right outcome for a ride that is not looking at its road.
- **Paved roads with grass score high.** Of the frames SegFormer calls vegetation or other, paved roads with grass verges and concrete lanes in greenery often score high: 4 of 12 paved on the Mapillary test score 0.75–0.91, and 12 of 56 paved on the Mekong set score 0.82–0.998, against 1 of 9 unpaved there (0.84). That is the opposite of what a recheck needs.
- **A probe trained only on grass frames does not help either.** Fit on the 84 clear vegetation/other frames in the dev rides (VN dev, Cần Thơ, Mapillary dev), held out one ride at a time and set so no held-out paved frame flips, it catches 0 to 3 of 18 held-out unpaved frames and 0 to 1 of 14 on the test split.

## What changed

- `pipeline/segmentation/probe.py`: `Probe` takes a `grass_threshold`. At 1.0 (the default and the shipped value) nothing changes. Below 1.0, `vegetation` and `other` frames are rechecked and switch to dirt at that threshold, with `p_unpaved` as their confidence (so with the default 0.5 vote cut, a threshold below 0.5 acts like 0.5).
- `tools/probe.py train` picks the grass threshold with the same rule as the paved one (the lowest threshold at which at most `--max-paved-error` of held-out paved calibration frames flip), on frames SegFormer calls vegetation or other. `--no-grass` keeps it at 1.0. `--check` also counts vegetation/other frames switched.

## Run

The before/after numbers use the shipped probe with `grass_threshold` set to 0.875, the value `train` picks with the Phase 2 command ([Phase 2](2026-11-21-phase2-dirt-probe.md)):

```bash
L=docs/evaluation/data
python -m tools.probe train --train $L/2026-11-21-vn-labels.csv output/probe-vn.npz dev \
  --extra $L/2026-11-20-can-tho-hand-labels.csv output/probe-can-tho.npz all \
  --prefer $L/2026-11-21-can-tho-owner-spot-check.csv \
  --test $L/2026-11-21-vn-labels.csv output/probe-vn.npz test --check output/probe-kv-3846189.npz \
  --out output/probe-grass.json
python -m tools.benchmark $L/2026-11-21-vn-labels.csv --split test --prefer $L/2026-11-21-vn-test-owner-spot-check.csv
```

The retrain does not reproduce the shipped probe exactly: with feature caches built today it trains on 431 frames, not 433, and picks a paved threshold of 0.45, not 0.40, with or without this change. The shipped paved probe is kept as is.

## Next

- **Owner:** the Hà Tĩnh park frames (725845 00000–00057) could be relabelled `unclear` (not the road), since they are what makes that ride count as dirt called paved. The spot check answers are the owner's, so they are left as they are here.
- Grassy dirt that a camera faces along is still worth catching, but needs test photos of it first; the Mekong set's unpaved photos are sand and gravel fill, not grassy tracks.
