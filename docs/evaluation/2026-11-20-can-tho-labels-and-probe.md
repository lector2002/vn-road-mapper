# 2026-11-20: More Cần Thơ labels, and a dirt/paved probe on SegFormer features

The main surface error is dirt called `paved` (`2026-11-20-kartaview-can-tho.md`). That test had 32 voting frames, too few to judge a fix. This test labels more frames and checks whether the features SegFormer already computes can tell dirt from paving.

## Labels

117 more frames labelled: every Cần Thơ frame that voted (confidence 0.5 or more) and had no label yet. Sequence 8308153 (the same ride as 8293273) and 8288905 (a camera that points at the ground) were left out. The frames were shown in random order, with the surface box drawn and no model output.

All 177 labels: `data/2026-11-20-can-tho-hand-labels.csv` (KartaView sequence, photo index, OSM way, surface by eye): 70 paved, 87 unpaved, 20 unclear.

The labels were made by Claude, by eye, in one pass on 480 px contact sheets. No person checked them. A full-size recheck of one way (806222638) changed 3 of 9 labels, so expect some label noise. Check a sample before you use the file as ground truth for training.

SegFormer on the 142 clear frames that voted:

| | by eye paved | by eye unpaved |
|---|---|---|
| SegFormer `paved` | 61 | 27 |
| SegFormer `dirt` | 3 | 51 |

112 of 142 right (79%). Dirt called `paved` stays the main error (27). There are now also 3 paved frames called `dirt`, which the 32-frame test did not show.

## Probe

For each frame: the SegFormer encoder features (stages 3 and 4) averaged over the ground pixels in the surface box, then a logistic regression for paved / unpaved. Tested two ways, so the probe never sees what it is tested on:

- leave one OSM way out (8 ways);
- leave one ride out (5 rides; 8293273 and 8308153 count as one ride). This is the stricter test: the same camera and day cannot help.

Pass rule, set before the run: fix dirt-called-`paved` frames on unseen roads, keep the right `paved` frames right, change no Thanh Hóa way.

| check | SegFormer | probe, one way out | probe, one ride out |
|---|---|---|---|
| Clear Cần Thơ frames right | 112 of 142 | 126 of 142 | 122 of 142 |
| Unpaved frames called paved | 27 | 5 | 9 |
| Paved frames called unpaved | 3 | 11 | 11 |
| Thanh Hóa frames called unpaved (1,008 votes, all paved roads) | 4 | 9 | 9 |
| Thanh Hóa ways that change surface or `weak` status | – | 0 of 68 | 0 of 68 |

The regression weight (0.01, 0.1, 1) changed the result by 1–4 frames. The table uses 0.1.

Per way (one way out), where the labels have a clear majority: SegFormer's frame majority matches the eye on 5 of 7 ways, the probe's on 7 of 7. The eighth way (806222638) is a tie by eye. Its 4 "paved" frames show the asphalt main road at the junction, not the gravel track that KartaView matched them to. The probe calls them unpaved, and they make 4 of its paved-called-unpaved errors.

Result: the features separate Vietnamese dirt from paving on rides the probe did not see. But the probe makes 11 paved frames unpaved, so it fails the pass rule and is not in the pipeline. Inferred, not measured: more training rides would reduce those errors. Only 5 rides are available.

## More training roads from StreetSurfaceVis

StreetSurfaceVis (Zenodo 11449977, CC BY-SA 4.0) has 9,122 Mapillary street photos from Germany, each labelled with a surface type. 1,000 photos from its training split were used at 256 × 192 px: 500 `unpaved`, and 500 paved (200 asphalt, 150 concrete, 100 paving stones, 50 sett). Same features and regression as above.

| check | SegFormer | Cần Thơ only (one ride out) | StreetSurfaceVis only | StreetSurfaceVis + Cần Thơ (one ride out) |
|---|---|---|---|---|
| Clear Cần Thơ frames right | 112 of 142 | 122 | 115 | 120 |
| Unpaved called paved | 27 | 9 | 15 | 5 |
| Paved called unpaved | 3 | 11 | 12 | 17 |
| Cần Thơ ways right | 5 of 7 | 7 of 7 | 7 of 7 | 7 of 7 |
| Thanh Hóa frames called unpaved (of 1,008) | 4 | 9 | 300 | 238 |
| Thanh Hóa ways that change | – | 0 of 68 | 29 of 68 | 26 of 68 |

The German photos make the result worse. On the paved Thanh Hóa rides the probe calls about a quarter of the frames unpaved. A look at 9 of these frames showed asphalt and concrete in every one: blurred, grey phone frames. Inferred: the probe learns how the German photos look (camera, light, size), not only the surface. The small 256 px size may add to this; the 1024 px set was not tried.

Result: StreetSurfaceVis is not used. Data from Vietnamese roads, taken with similar cameras, is what helps.

## More training roads from Mapillary (Vietnam)

Labels come from OSM: an image is `unpaved` or `paved` when it is within 8 m of a road with that `surface` tag, heads along it (30° or less), and no other road is within 5 m more. Roads that the Cần Thơ and Thanh Hóa test frames use are left out. Images are at most 40 per sequence, 20 m apart.

- Search by area (Cần Thơ, Thanh Hóa, Bến Tre; 18,895 images): 0 images on unpaved-tagged roads, also with 20 m and any heading. Mapillary riders in these areas do not use the roads that OSM tags unpaved. The OSM server timed out for Đắk Lắk and Lào Cai.
- Search from the roads: 6,000 of Vietnam's 132,803 unpaved-tagged OSM roads, picked at random. 396 have Mapillary images within about 300 m; 489 images match an unpaved road. After the per-sequence limit and spacing: 148 unpaved images from 29 sequences, and 121 paved images with the same camera makes.
- An eye check of 2 images per unpaved sequence: 42 images come from trains (the railway runs next to an unpaved-tagged road), and others show night, people or a paved road. 84 unpaved images from 11 sequences remain; 61 of them come from 2 dashcam rides.

| check | SegFormer | Cần Thơ only (one ride out) | Mapillary only | Mapillary + Cần Thơ (one ride out) |
|---|---|---|---|---|
| Clear Cần Thơ frames right | 112 of 142 | 122 | 108 | 125 |
| Unpaved called paved | 27 | 9 | 31 | 9 |
| Paved called unpaved | 3 | 11 | 3 | 8 |
| Cần Thơ ways right | 5 of 7 | 7 of 7 | 5 of 7 | 6 of 7 |
| Thanh Hóa frames called unpaved (of 1,008) | 4 | 9 | 5 | 3 |
| Thanh Hóa ways that change | – | 0 of 68 | 0 of 68 | 0 of 68 |

Mapillary alone does not fix dirt called `paved`. Added to the Cần Thơ labels, it keeps the Thanh Hóa rides unchanged and has 3 fewer paved frames called unpaved. With 84 unpaved images from few rides, a difference of 3 frames can be noise (inferred). The probe still calls 8 paved frames unpaved, so it fails the pass rule and is not in the pipeline.

Result: OSM tags give few usable unpaved images, because Mapillary images on unpaved-tagged roads are rare and many come from trains. More data needs hand labels on untagged Vietnamese roads, not OSM tags.

Imagery: KartaView, CC BY-SA 4.0, StreetSurfaceVis, CC BY-SA 4.0, and Mapillary, CC BY-SA 4.0, in `output/` only. OSM data, ODbL. The label file holds no images.
