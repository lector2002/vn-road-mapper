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

Imagery: KartaView, CC BY-SA 4.0, in `output/` only. The label file holds no images.
