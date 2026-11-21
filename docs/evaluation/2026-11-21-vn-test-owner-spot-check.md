# Owner spot check of the test split labels (2026-11-21)

File: `data/2026-11-21-vn-test-owner-spot-check.csv`, the owner's blind answers on 50 photos from the 4 test rides of `data/2026-11-21-vn-labels.csv`.

## Agreement

`python -m tools.agreement docs/evaluation/data/2026-11-21-vn-labels.csv docs/evaluation/data/2026-11-21-vn-test-owner-spot-check.csv`

- 38 of the 50 photos are clear to both; 37 agree (97%), over the 90% bar. **The test labels pass** and stay as test data.
- The one disagreement: 11696959/00263, labels say paved, the owner says unpaved.
- The other 12 are all Hà Tĩnh (725845) photos the labels call `unclear` and the owner calls clear: 11 unpaved, 1 paved. The two-pass labels are right when they commit, but they hold back on grassy dirt tracks, so the test split undercounts dirt.

The owner's answers replace the labels where they overlap (`tools.benchmark --prefer`), as with the Cần Thơ spot check.

## Test numbers with the owner's answers

`python -m tools.benchmark docs/evaluation/data/2026-11-21-vn-labels.csv --split test --prefer docs/evaluation/data/2026-11-21-vn-test-owner-spot-check.csv --out output/vn-test` (add `--no-probe` for SegFormer alone). Each ride counts as one way.

| | SegFormer alone | With the dirt probe | Phase 2 figure (labels only) |
|---|---|---|---|
| Clear frames right | 109 of 129 (84%) | 119 of 129 (92%) | 120 of 128 |
| Unpaved called paved | 19 of 36 | 8 of 36 | 6 of 34 |
| Paved called unpaved | 1 of 93 | 2 of 93 | 2 of 94 |
| Rides right | 2 of 4 | 3 of 4 | 4 of 4 |

Hà Tĩnh 725845 now has an unpaved majority by eye (11 unpaved, 7 paved), and the model calls it paved. Of the 11 owner-unpaved frames, 10 come out `vegetation` or `other` (SegFormer sees the grass, not the track) and do not vote; the one that votes is called paved with 0.95 confidence and the probe keeps it. Only its 6 paved frames vote. The probe only rechecks frames called paved, so grassy dirt tracks called vegetation are a second dirt failure it cannot fix.

## Limits

- 12 of the 50 answers are on photos the labels left out, so the dirt counts grow by only 2 voting frames; Hà Tĩnh dirt is mostly measured as "no vote".
- The other 128 test photos are still the two-pass labels alone, now checked by the 97% sample.
