# Road check for frames SegFormer calls vegetation (2026-11-22)

> Public data only: Mapillary and KartaView photos already in the label files. No rides, no paid labelling, nothing posted to OSM.

On the trusted Mekong set ([write-up](2026-11-22-mekong-dirt.md)), 56 of the 85 photos the owner calls paved gave no vote: SegFormer labels most of the bottom-centre box of a narrow concrete lane in greenery `vegetation`. It still marks a strip of `road` (or `path`/`earth`) pixels on the lane itself. Running the dirt probe on those frames failed ([grassy recheck](2026-11-22-grassy-dirt-recheck.md)), because its fixed crop is mostly greenery and grass scores as unpaved.

## What changed

Frames that would not vote (`vegetation`, `other`, or confidence under 0.5) now get a **road check** (`pipeline/segmentation/probe.py`):

1. Take the `paved` and `dirt` pixels in the bottom 55% of the frame. If they cover less than 2% of it, stop (no road in view).
2. Crop the image to the box around them, so the crop is the lane, not the verge.
3. Score the crop zero-shot with the same CLIP model: "a photo of a concrete / an asphalt / a paved road" against "a photo of a dirt road / a gravel road / a muddy track". No training, so no labels were fitted to the test sets.
4. If CLIP's answer and the majority of those pixels agree, that is the label, with CLIP's probability as `confidence`. If they disagree the frame keeps its label and still does not vote.

Frames SegFormer already calls `paved` (confidence 0.5 or more) or `dirt` are not touched; the paved dirt probe runs as before. The shipped `surface_probe.json` turns the check on (`"road_check": true`); `tools.benchmark --no-road-check` scores without it and `--no-probe` turns off both checks.

The rule was picked on the dev sets (VN and Mapillary dev, Cần Thơ) from five candidates: pixel majority alone, CLIP alone, CLIP with a margin, either restricted to paved, and the agreement rule. On those sets pixel majority alone added 8 paved-called-unpaved and 7 unpaved-called-paved errors, CLIP alone 5 and 7; requiring both to agree adds 2 and 3.

## Result

All runs use the owner's spot-check answers (`--prefer`). Before = the shipped probe without the road check.

| Set | Frames right, before | Frames right, after | Unpaved called paved | Paved called unpaved | Rides right |
|---|---|---|---|---|---|
| **Mekong dirt (test)** | 42 of 55 | 90 of 108 | 11 → 13 | 2 → 5 | 9 → 15 of 18 |
| VN KartaView test | 118 of 127 | 123 of 132 | 7 → 7 | 2 → 2 | 4 → 4 of 4 |
| Mapillary test | 72 of 80 | 87 of 95 | 1 → 1 | 7 → 7 | 6 → 6 of 8 |
| VN KartaView dev | 278 of 281 | 322 of 327 | 0 → 0 | 3 → 5 | 9 → 9 of 9 |
| Mapillary dev | 53 of 57 | 70 of 76 | 1 → 3 | 3 → 3 | 6 → 7 of 8 |
| Cần Thơ (training) | 133 of 135 | 139 of 142 | 0 → 1 | 2 → 2 | 7 → 8 of 9 |

- Mekong paved photos with no vote: 56 → 11 of 85. Of the 53 Mekong frames whose label changes, 45 become right votes (41 lanes now paved, 3 dirt frames now dirt, one low-confidence paved frame now dirt), 5 become wrong (3 paved lanes called dirt, 2 dirt frames called paved) and 3 are unclear by eye.
- Thanh Hóa paved ride (KartaView 3846189): 1 of 475 frames switched to dirt, a blurred, upside-down frame; the ride is still paved (465 paved votes).
- The 11 Đức Hòa dirt frames called paved before are still called paved; that is the probe's problem on sand-coloured fill, not this one.

## Run

```bash
L=docs/evaluation/data
python -m tools.benchmark $L/2026-11-22-mekong-dirt-labels.csv --prefer $L/2026-11-22-mekong-dirt-owner-spot-check.csv \
  --out output/bench/mekong            # add --no-road-check for "before"
python -m tools.benchmark $L/2026-11-21-vn-labels.csv --prefer $L/2026-11-21-vn-test-owner-spot-check.csv --out output/bench/vn
python -m tools.benchmark $L/2026-11-21-vn-mapillary-labels.csv --prefer $L/2026-11-21-mapillary-owner-spot-check.csv --out output/bench/mly
python -m tools.benchmark $L/2026-11-20-can-tho-hand-labels.csv --prefer $L/2026-11-21-can-tho-owner-spot-check.csv --out output/bench/cantho
```

Dev and test numbers are the `split` column of each `benchmark.csv`. The road check adds one CLIP pass to the frames that would not vote, 266 of the 1,090 on these sets.

## Next

- Dirt on the Mekong set is still one place (Đức Hòa fill); more delta dirt photos (in progress separately) are needed before trusting the road check's dirt calls there.
