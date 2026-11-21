# Phase 2: a CLIP dirt probe for frames SegFormer calls paved (2026-11-21)

## Result on the test split

Test split: 178 labelled photos from 4 rides (2 Gia Lai, 1 Ninh Bình, 1 Hà Tĩnh), 137 clear, 128 voting. Each ride counts as one way.

| | SegFormer alone | With the dirt probe |
|---|---|---|
| Clear frames right | 110 of 128 (86%) | 120 of 128 (94%) |
| Unpaved called paved | 17 of 34 | 6 of 34 |
| Paved called unpaved | 1 of 94 | 2 of 94 |
| Rides right | 3 of 4 | 4 of 4 |
| Thanh Hóa ride 3846189: paved frames switched to dirt | – | 0 of 465 |

The Ninh Bình dirt ride now comes out unpaved instead of having no majority. One more paved frame is called dirt (1% of paved frames); no paved ride changes.

## What it does

`pipeline/segmentation/probe.py`: for each frame SegFormer calls paved, CLIP (`openai/clip-vit-base-patch16`) embeds the road crop (bottom 55%, middle 70%) and a logistic regression gives `p_unpaved`. At or above the threshold (0.4) the frame becomes dirt. It never switches dirt to paved, and other labels are untouched. The weights are in `pipeline/segmentation/surface_probe.json`. `segment`, `pipeline.run` and `tools.benchmark` use it by default; `--no-probe` turns it off. CLIP is another 600 MB download and one more forward pass for each paved frame.

## Training data (public only)

- The dev split of `data/2026-11-21-vn-labels.csv` (two-pass labels, 9 rides).
- The 177 Cần Thơ hand labels, for training only, because they failed the owner spot check (38 of 44, under the 90% bar). The owner's 50 answers (`data/2026-11-21-can-tho-owner-spot-check.csv`) replace the old labels where they overlap.
- Frames SegFormer calls paved or dirt with a clear label: 433 frames, 88 unpaved, from 15 rides.

Threshold: each ride is held out in turn. The threshold is the lowest value at which at most 3% of held-out paved frames flip to dirt, counting only checked labels (the two-pass dev labels and the owner's answers). The test split was not used to pick anything.

## Split change

All Cần Thơ photos come from one rider (KartaView user 44, shot 2023-05-12 to 05-17). The hand-labelled rides were shot on the same days as the 3 Cần Thơ test rides, so training on them would leak into test. All Cần Thơ moved to dev, and the Hà Tĩnh ride went back to test. Test now has 180 candidates and dev 405. Before the move, SegFormer got 208 of 228 test frames right; on the new test split it gets 110 of 128.

## What did not work

The SegFormer-feature probe from 2026-11-20, rebuilt on stage 3–4 encoder features over the road pixels, ranked test frames almost perfectly. Its probabilities did not carry over from Mekong dirt to Ninh Bình dirt, though. With the threshold picked the same way, it got 113 of 128, with 14 unpaved frames called paved. CLIP features carry over better.

## Limits

- Test dirt comes from one ride: 34 of 34 voting unpaved frames are Ninh Bình. The 6-of-34 figure is a single-ride result.
- The test labels are Claude's two passes; no person has checked them. A 50-photo blind sample of the test split would settle this.
- Thanh Hóa 3846189 is the same rider as two dev rides, one day apart. It is a regression check, not an independent test.
- No mud class: mud is still part of unpaved.

## Reproduce

```bash
python -m tools.benchmark docs/evaluation/data/2026-11-21-vn-labels.csv --out output/vn --no-probe   # fetches frames
python -m tools.benchmark docs/evaluation/data/2026-11-20-can-tho-hand-labels.csv --out output/can-tho --no-probe
python -m tools.kartaview 3846189 --out output/kv-3846189 --every 3
for d in vn can-tho kv-3846189; do python -m tools.probe features output/$d/frames --out output/probe-$d.npz; done
L=docs/evaluation/data
python -m tools.probe train --train $L/2026-11-21-vn-labels.csv output/probe-vn.npz dev \
  --extra $L/2026-11-20-can-tho-hand-labels.csv output/probe-can-tho.npz all \
  --prefer $L/2026-11-21-can-tho-owner-spot-check.csv \
  --test $L/2026-11-21-vn-labels.csv output/probe-vn.npz test \
  --check output/probe-kv-3846189.npz --out pipeline/segmentation/surface_probe.json
```
