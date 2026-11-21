# tools

## kartaview.py

Downloads a public [KartaView](https://kartaview.org) photo sequence and writes it in the frames stage's format (`frames/*.jpg` at 1280×720 + `frames.csv`). This lets the later stages run on real street imagery before you have your own rides.

```bash
python -m tools.kartaview 3846125 --out output/kv-3846125 --every 2
```

- `--every 2` keeps every 2nd photo.
- Portrait-shaped photos are turned 90° to landscape. The capture app saved some landscape shots as portrait with the scene on its side; the model labeled many of those `water`. On the Thanh Hóa rides this makes 64 of 76 such photos upright; 12 had the sky on the other side and end up upside down (they give no vote).
- It also writes `kartaview.csv` with KartaView's own matched OSM way per photo, as a cross-check for the mapmatch stage, plus each photo's sequence and index so later stages can link to it.
- Find sequences with `https://api.kartaview.org/2.0/sequence/?countryCode=VN&itemsPerPage=100&page=1`.

KartaView imagery is CC BY-SA 4.0. Keep downloaded frames out of the repo (`output/` is ignored).

## benchmark.py

Scores the segmentation stage against hand labels on public KartaView and Mapillary photos. It downloads only the labelled photos (into `output/`), runs SegFormer (plus the dirt probe; `--no-probe` for SegFormer alone) and prints frame accuracy, both error directions, per-way agreement and a confusion table. It also writes `benchmark.csv` (label and confidence per photo) and `benchmark.json`.

```bash
python -m tools.benchmark docs/evaluation/data/2026-11-20-can-tho-hand-labels.csv --out output/bench-can-tho
# Test split only, with the owner's spot check answers winning where they overlap
python -m tools.benchmark docs/evaluation/data/2026-11-21-vn-labels.csv --split test \
    --prefer docs/evaluation/data/2026-11-21-vn-test-owner-spot-check.csv --out output/vn-test
```

- Pass one or more CSVs. Each needs `kartaview_sequence` or `mapillary_sequence`, `photo` (KartaView `sequenceIndex` or Mapillary image id) and `surface_by_eye` (`paved`, `unpaved` or anything else for unclear). `osm_way_id` is optional; without it each ride counts as one way. Other columns, such as `split`, are copied into `benchmark.csv`.
- A frame votes when its label is `paved`, `dirt` or `mud` with confidence 0.5 or more, as in fusion.
- A way counts when the eye labels have a strict majority.
- Mapillary photos need a free client token in `MAPILLARY_ACCESS_TOKEN` (mapillary.com/dashboard/developers).
- On 2026-11-21: 109 of 142 frames right, 30 unpaved called paved, 3 paved called unpaved, 5 of 8 ways. The 2026-11-20 evaluation got 112 of 142 from the original storage-host photos; the CDN copies the importer now uses are sharpened.

## labelpage.py

Builds one self-contained HTML page for labelling road surface by eye on KartaView or Mapillary photos. It shows one photo at a time with the box the surface stage reads, never the existing label, in shuffled order. Answers (paved / unpaved / mud / water / unclear, keys 1–5) stay in the browser; at the end the page gives a CSV in the hand-label format to send back. Works on a phone.

```bash
# Owner spot check: 50 of the 177 Cần Thơ labels, in proportion to the existing labels (fixed seed)
python -m tools.labelpage docs/evaluation/data/2026-11-20-can-tho-hand-labels.csv --sample 50 \
    --title "Spot check: Cần Thơ road surfaces (50 photos)" --out output/spot-check/can-tho-spot-check.html
# Volunteer page for new frames; --link points at KartaView's CDN so hundreds of photos stay a small file
python -m tools.labelpage docs/evaluation/data/2026-11-21-vn-candidates.csv --link --out output/vn-candidates.html
# Owner spot check of the Mapillary labels (needs MAPILLARY_ACCESS_TOKEN)
python -m tools.labelpage docs/evaluation/data/2026-11-21-vn-mapillary-labels.csv --sample 50 --out output/vn-mapillary-check.html
```

Photos are embedded (about 130 KB each), so a page can be shared as one file; keep it out of the repo.

## agreement.py

Compares a second person's labels with an existing file on photos both call clear (mud counts as unpaved) and lists the disagreements. Exit code 0 when they agree on 90% or more.

```bash
python -m tools.agreement docs/evaluation/data/2026-11-20-can-tho-hand-labels.csv can-tho-spot-check-labels.csv
```

## candidates.py

Picks evenly spaced photos (45 per sequence by default) from a list of KartaView or Mapillary sequences (`kartaview_sequence` or `mapillary_sequence` column) with a region and a split each. `docs/evaluation/data/2026-11-21-vn-sequences.csv` lists 13 sequences in 4 regions; the split is fixed per rider and day, so no ride has photos in both the test and dev splits. `2026-11-21-vn-mapillary-sequences.csv` adds 17 Mapillary sequences for the Southeast, the northern mountains and dirt roads; see `docs/evaluation/2026-11-21-vn-mapillary.md`.

```bash
python -m tools.candidates docs/evaluation/data/2026-11-21-vn-sequences.csv --out docs/evaluation/data/2026-11-21-vn-candidates.csv
```

## probe.py

Builds features for, trains and scores the dirt probe (`pipeline/segmentation/probe.py`): a logistic regression on CLIP features of the road crop that switches frames SegFormer calls paved to dirt. `features` runs SegFormer and CLIP once per frame folder; `train` picks the threshold by holding out one ride at a time and prints the test split before and after. Full commands are in `docs/evaluation/2026-11-21-phase2-dirt-probe.md`.

```bash
python -m tools.probe features output/vn/frames --out output/probe-vn.npz
python -m tools.probe train --train docs/evaluation/data/2026-11-21-vn-labels.csv output/probe-vn.npz dev \
  --test docs/evaluation/data/2026-11-21-vn-labels.csv output/probe-vn.npz test
```

## pilot.py

Builds and scores the Phase 3 OSM pilot ([kit](../docs/pilot/README.md)). Nothing here uploads to OSM or MapRoulette.

```bash
# Pick up to 100 untagged small roads from export proposals and write the pilot
python -m tools.pilot build output/pilot/fused/proposals.csv output/pilot/kv-8293225 output/pilot/kv-8308169 --out docs/pilot/data
# Score the reviewers' answers (a MapRoulette CSV export, or pilot.csv with its decision column filled)
python -m tools.pilot score export.csv
```

- `build` keeps only `add` proposals on rural highway types with photos for the proposed surface, puts unpaved first, then re-fetches every way from the OSM API and drops any that has a `surface` tag by now.
- It writes `pilot.csv` (one row per way with 3 KartaView photo links and an empty `decision` column), `challenge.geojson` (MapRoulette line-by-line GeoJSON; each task is a cooperative tag fix that only sets `surface`) and `review.html` (the export review map for just these ways).
- `score` counts Fixed/accept as accepted and Not an issue/reject as rejected, ignores skipped or too-hard tasks, and passes at 90% accepted.
