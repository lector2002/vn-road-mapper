# width stage

Estimates the road width in each frame from the road mask and the height of the phone above the road.

## Usage

```bash
python -m pipeline.width.estimate output/ride1/frames --out output/ride1 --camera-height 1.1
```

Measure `--camera-height` once: the height of the phone lens above the road, in metres, on the mounted bike. There is no default, because the width scales directly with it.

Output:

- `widths.csv` with the columns `filename,width_m,horizon,rows,residual`.
- `width_overlays/*.jpg`: yellow lines for the rows used, red lines for the rows left out, and a blue line for the fitted horizon.

The fusion stage adds the median width of each OSM way when it finds `widths.csv` in the run folder.

## How

1. The segmentation model marks road pixels (`paved`, `dirt`, `mud`, `water`).
2. Sample rows from 30% to 97% of the frame height. In each row, take the road run nearest the image center. Leave out rows where the road touches the frame edge.
3. On flat, straight ground the road's pixel width grows in a straight line with the row: `span = width × (row − horizon) / camera_height`.
4. Fit that line. The slope × camera height gives the width. The line crosses zero at the horizon, so the phone's tilt and lens focal length are not needed.

`width_m` is blank when fewer than 4 rows are usable, when the fit is poor (`residual` above 0.1), or when the fitted horizon falls below the road. A blank is better than a wrong number.

## Limits

- It assumes flat, straight road and a phone without sideways tilt. Hills and bends give no width or a wrong one.
- The road mask includes dirt shoulders, so a paved road with dirt edges measures as the full width.
- Not yet checked against a road of known width. See `docs/decisions/2026-11-20-width-method.md`.
