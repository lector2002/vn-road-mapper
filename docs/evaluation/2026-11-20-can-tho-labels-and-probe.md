# 2026-11-20: More Cần Thơ labels, and a dirt/paved probe on SegFormer features

The main surface error is dirt called `paved` (`2026-11-20-kartaview-can-tho.md`). That test had 32 voting frames, too few to judge a fix. This test labels more frames and checks whether the features SegFormer already computes can tell dirt from paving.

## Labels

117 more frames labelled by eye: every Cần Thơ frame that voted (confidence 0.5 or more) and had no label yet. Sequence 8308153 (the same ride as 8293273) and 8288905 (a camera that points at the ground) were left out. The frames were shown in random order with the surface box drawn and no model output.

All 177 labels: `data/2026-11-20-can-tho-hand-labels.csv` (KartaView sequence, photo index, OSM way, surface by eye): 70 paved, 87 unpaved, 20 unclear.

SegFormer on the 142 clear frames that voted:

| | by eye paved | by eye unpaved |
|---|---|---|
| SegFormer `paved` | 63 | 25 |
| SegFormer `dirt` | 3 | 51 |

114 of 142 right (80%). Dirt called `paved` stays the main error (25), and there are now 3 paved frames called `dirt`.

## Probe

For each frame: the SegFormer encoder features (stages 3 and 4) averaged over the ground pixels in the surface box, then a logistic regression for paved / unpaved. Tested by leaving one OSM way out at a time (8 ways), so the probe never sees the road it is tested on. The duplicate ride falls in the same ways, so it cannot leak.

Pass rule, set before the run: fix dirt-called-`paved` frames on unseen ways, keep the right `paved` frames right, change no Thanh Hóa way.

| check | SegFormer | probe |
|---|---|---|
| Clear Cần Thơ frames right | 114 of 142 | 122 of 142 |
| Dirt called `paved` | 25 | 5 |
| Right `paved` frames made wrong | – | 11 of 63 |
| Cần Thơ ways whose frame majority matches the eye | 6 of 8 | 6 of 8 |
| Thanh Hóa frames called unpaved (1,008 votes, all paved roads) | 4 | 6 |
| Thanh Hóa ways that change surface or `weak` status | – | 0 of 68 |

The regression weight (0.01, 0.1, 1) changed the result by 1–2 frames. The table uses 0.1.

Per way the probe fixes one way (167961113, mostly dirt, SegFormer said paved) and breaks another: 6 of the 11 broken frames are on way 806222638 (paved by eye, 6 of 8 frames), which the probe calls unpaved on all 8. With 8 ways from 3 rides, a road that looks unlike the others has nothing to learn from.

Result: the features do separate Vietnamese dirt from paving (20 of 25 errors fixed on roads the probe did not see, no false alarms on the paved Thanh Hóa rides), but the probe fails the pass rule and is not added to the pipeline. More training roads are the limit, not the model.

Imagery: KartaView, CC BY-SA 4.0, in `output/` only. The label file holds no images.
