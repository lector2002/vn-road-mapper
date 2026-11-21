# Labels for the 585 Vietnamese candidate photos (2026-11-21)

File: `data/2026-11-21-vn-labels.csv` (`kartaview_sequence, photo, region, split, surface_by_eye`).

## How they were made

Claude labelled every photo in `data/2026-11-21-vn-candidates.csv` twice, from contact sheets of the road part of each frame (bottom 45%, middle 70%), in two different random orders. Only photos where both passes gave the same label are kept.

- Labelled twice: 585. Same label both times: 568. All 17 differences were a clear label in one pass and `unclear` in the other; no photo was called paved once and unpaved once.
- Kept: 422 paved, 51 unpaved, 95 unclear. No mud or water was seen.
- Both passes come from the same labeller, so this measures consistency, not accuracy. The owner checked 50 test photos on the label page: 37 of 38 agree, so the file passes ([spot check](2026-11-21-vn-test-owner-spot-check.md)).

## Split change

41 of the 51 unpaved photos are in one Ninh Bình ride (2879114), which was in dev, leaving test with 7 unpaved photos. That ride moved to test and the Hà Tĩnh ride (725845, mostly unclear) moved to dev. The split is still per rider and day, 270 test and 315 dev. Dev now has 3 unpaved photos; Phase 2 tunes on the Cần Thơ hand labels instead.

Later in Phase 2 all Cần Thơ moved to dev (their rides share days with the hand-labelled Cần Thơ rides) and Hà Tĩnh went back to test: 180 test, 405 dev. The table below is from before that move; the current test numbers are in [the Phase 2 write-up](2026-11-21-phase2-dirt-probe.md).

## Benchmark on these labels

`python -m tools.benchmark docs/evaluation/data/2026-11-21-vn-labels.csv --out output/vn`, each ride counted as one way, current model (`nvidia/segformer-b2-finetuned-ade-512-512`):

| set | frames right | unpaved called paved | paved called unpaved | rides right |
|---|---|---|---|---|
| test | 208 of 228 (91%) | 18 of 37 | 2 of 191 | 5 of 6 |
| dev | 177 of 181 (98%) | 2 of 2 | 2 of 179 | 7 of 7 |
| all | 385 of 409 (94%) | 20 of 39 | 4 of 370 | 12 of 13 |

Paved roads are almost always right in every region. Dirt is the problem, as in Cần Thơ: about half of the unpaved photos are called paved (17 of 34 in the Red River delta, 3 of 5 in the Mekong). The overall 91% is high only because most public photos are paved town roads; the dirt recall of about 50% is the number Phase 2 has to move.
