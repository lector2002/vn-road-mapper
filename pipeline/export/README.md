# export stage

Turns fused way surfaces into OSM edit proposals for a person to review. It never uploads.

## Usage

```bash
python -m pipeline.export.export output/fused/ways.csv --out output/fused
```

It reads each way's current tags from the OSM API, then writes:

- `proposals.csv` — one row per way with a status:
  - `add`: OSM has no `surface` tag; propose one.
  - `change`: the OSM tag is in the other family (paved vs unpaved); propose the model's value.
  - `agree`: OSM already says the same family (for example model `dirt`, OSM `gravel`).
  - `weak`: fewer than `--min-votes` (5) votes, or agreement below `--min-agreement` (0.7).
  - `unknown`: an OSM value the script does not sort into paved or unpaved.
- `changes.osc` — an osmChange file with the `add` and `change` ways. Open it in JOSM to check and upload.
- `review.html` — a map of every way, colored by status. Click a way for the vote and its current tag.

The model writes only the generic values `paved` and `unpaved`, so it never overwrites a more exact tag such as `asphalt` or `gravel` in the same family.

## Before you upload

Automated or bulk edits to OSM must follow the [Automated Edits code of conduct](https://wiki.openstreetmap.org/wiki/Automated_Edits_code_of_conduct): discuss with the OSM Vietnam community first, check each way by eye, and say in the changeset that the source is AI from street-level video.
