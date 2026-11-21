# tools

## kartaview.py

Downloads a public [KartaView](https://kartaview.org) photo sequence and writes it in the frames stage's format (`frames/*.jpg` at 1280×720 + `frames.csv`). This lets the later stages run on real street imagery before you have your own rides.

```bash
python -m tools.kartaview 3846125 --out output/kv-3846125 --every 2
```

- `--every 2` keeps every 2nd photo.
- Portrait-shaped photos are turned 90° to landscape. The capture app saved some landscape shots as portrait with the scene on its side; the model labeled many of those `water`. On the Thanh Hóa rides this makes 64 of 76 such photos upright; 12 had the sky on the other side and end up upside down (they give no vote).
- It also writes `kartaview.csv` with KartaView's own matched OSM way per photo, as a cross-check for the mapmatch stage.
- Find sequences with `https://api.kartaview.org/2.0/sequence/?countryCode=VN&itemsPerPage=100&page=1`.

KartaView imagery is CC BY-SA 4.0. Keep downloaded frames out of the repo (`output/` is ignored).

## benchmark.py

Scores the segmentation stage against hand labels on public KartaView photos. It downloads only the labelled photos (into `output/`), runs SegFormer and prints frame accuracy, both error directions, per-way agreement and a confusion table. It also writes `benchmark.csv` (label and confidence per photo) and `benchmark.json`.

```bash
python -m tools.benchmark docs/evaluation/data/2026-11-20-can-tho-hand-labels.csv --out output/bench-can-tho
```

- The CSV needs `kartaview_sequence`, `photo` (KartaView `sequenceIndex`), `osm_way_id` and `surface_by_eye` (`paved`, `unpaved` or anything else for unclear).
- A frame votes when its label is `paved`, `dirt` or `mud` with confidence 0.5 or more, as in fusion.
- A way counts when the eye labels have a strict majority.
- On 2026-11-21: 109 of 142 frames right, 30 unpaved called paved, 3 paved called unpaved, 5 of 8 ways. The 2026-11-20 evaluation got 112 of 142 from the original storage-host photos; the CDN copies the importer now uses are sharpened.
