# fusion stage

Combines the frame labels of one or more rides into one surface per OSM way.

## Usage

```bash
python -m pipeline.fusion.fuse output/ride1 output/ride2 --out output/fused
```

Each run folder needs `matches.csv` (mapmatch) and `segmentation.csv` (segmentation). Output `ways.csv`:

| column | meaning |
|---|---|
| `surface` | majority vote among `paved` / `dirt` / `mud` frames |
| `agreement` | share of the votes that went to the winner (0–1) |
| `votes` | frames that voted |
| `frames` | all frames matched to the way |
| `passes` | number of rides that covered the way |
| `water_share` | share of confident frames labeled `water`: a flood signal, not a surface |

Frames below `--min-confidence` (default 0.5), and frames labeled `vegetation`, `water` or `other`, do not vote. Foliage over the road is skipped this way, not counted as a surface.

Frames tilted more than `--max-tilt` degrees (default 60, from the `tilt` column of `segmentation.csv`) are skipped entirely: they do not vote, do not count for `water_share` and give no width. They still count in `frames`. On two KartaView rides, phones that swung sideways in the mount caused 7 of the 8 false `water` labels. Frames with a blank `tilt` are kept.
