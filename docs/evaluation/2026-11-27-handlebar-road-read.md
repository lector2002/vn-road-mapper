# Handlebar occlusion road read (2026-11-27)

> Public data only: the already labelled public Panoramax, Mapillary and KartaView photos. No rides, no paid labelling, nothing posted to OSM.

The Panoramax delta set ([write-up](2026-11-22-panoramax-delta-dirt.md)) is filmed behind a phone and handlebars. SegFormer marks those bike parts `other`; they fill the fixed bottom-centre box, so most frames came out `other` or `vegetation` and did not vote. The first road check helped, but narrow concrete lanes in greenery were still often read as dirt.

## What changed

Frames whose bottom centre is mostly `other` (at least half the pixels in rows 85–100%, columns 35–65%) can use an occlusion-aware read in `pipeline/segmentation/probe.py`:

1. Read two zero-shot CLIP crops: the lane just above the bike parts (rows 58–88%, columns 22–78%) and the wider lower frame.
2. Use balanced narrow prompts: narrow concrete/asphalt/paved paths against narrow dirt lanes, grassy tracks and unpaved paths. The width words are balanced so a narrow concrete lane is not called dirt merely because it looks like a path.
3. A crop votes only when CLIP is at least 0.7 confident. Confident crops must not disagree; the surface label is then paved or dirt and confidence is the weaker confident crop. If neither crop is confident, or they disagree, the frame is forced not to vote.
4. When only one crop is confident, visible road pixels get a veto. The broad zero-shot road prompt reads the box around SegFormer's road pixels. If that read agrees with the road pixels and contradicts the crop, it vetoes the crop at 0.8 confidence, or at 0.7 confidence when the two occlusion crops already point in opposite directions. This keeps a grassy or dirt shoulder inside a wide crop from overriding corroborated visible road surface.
5. The read is layered behind SegFormer rather than ahead of it. The read never directly replaces SegFormer's own surface vote; it handles frames SegFormer cannot vote on. It can arbitrate a marginal dirt-probe flip, but a strong flip (P(unpaved) at least 0.8) is trusted because the Cần Thơ regression showed those flips are usually correct dirt roads. A confident water frame is also left alone. Cameras without bottom-centre occlusion use the existing SegFormer, dirt probe and road check path. On Panoramax, 172 of 189 photos cross the trigger.

The two crops are embedded in one CLIP batch. No surface labels are trained or fitted; this is still a zero-shot check.

## Panoramax delta result

Trusted set: 189 photos, owner agreement 42/43 clear photos (98%). Before is the shipped probe with the first road check; first read is the occlusion read without the visible-road veto; final is this branch.

| | before | first read | final |
|---|---|---|---|
| Clear frames that vote | 100 of 169 | 141 of 169 | 140 of 169 |
| Voting frames right | 71 of 100 | 129 of 141 | 129 of 140 |
| Unpaved called paved | 0 | 2 | 1 |
| Paved called unpaved | 29 | 10 | 10 |
| Collections right (eye majority) | 9 of 14 | 14 of 14 | 14 of 14 |

| model final | by eye paved | by eye unpaved |
|---|---|---|---|
| paved | 111 | 1 |
| dirt | 10 | 18 |

The remaining errors no longer dominate their collections: every collection with an eye majority is now called correctly. The visible-road veto costs one voting frame but removes one of the two severe unpaved-called-paved errors. 6 of the 10 paved-called-unpaved errors are direct SegFormer dirt votes, which the layering deliberately preserves rather than letting the occlusion read overrule every direct surface vote; 2 more are strong dirt-probe flips. 15 unpaved and 14 paved clear frames still do not vote, mostly grassy tracks or heavily occluded lanes where the evidence is uncertain or disagreeing.

## Regression check

| set | before | after |
|---|---|---|
| Mapillary test | 87 of 95 right | 87 of 95 right; same 1 unpaved-called-paved, same 7 paved-called-unpaved, ways 6/8 |
| VN KartaView test | 123 of 132 right | 123 of 132 right; same 7 unpaved-called-paved, same 2 paved-called-unpaved, ways 4/4 |
| Cần Thơ | 139 of 142 right | 139 of 142 right; same 1 unpaved-called-paved, same 2 paved-called-unpaved, ways 8/9 |
| Mekong dirt | 90 of 108 right | 92 of 110 right; same 13 unpaved-called-paved, same 5 paved-called-unpaved, ways 15/18 |

Mapillary, Cần Thơ and the KartaView test set keep exactly the same headline metrics. Mekong keeps the two correct voting frames gained by the occlusion read, while the visible-road veto removes the one paved-called-dirt regression without losing a correct voting frame; the severe unpaved-called-paved count does not rise. The layering is what avoids the earlier regression shape: an untargeted version overrode direct SegFormer dirt votes and lost correct unpaved frames, while this version only replaces non-votes or heuristic flips.

## Run

```bash
L=docs/evaluation/data
python -m tools.benchmark $L/2026-11-22-panoramax-delta-dirt-labels.csv \
  --prefer $L/2026-11-22-panoramax-delta-dirt-owner-spot-check.csv --out output/bench/panoramax-after
python -m pytest tests -q
```

The regression score uses cached SegFormer class maps and crop embeddings; the visible road-box crops affected by the veto were read again with the real CLIP model.

## Remaining gap

The read is conservative by design. It fixes the handlebar camera enough for collection-level surface calls, but unpaved recall is still low: grassy dirt tracks often have too little visible bare surface for either crop to reach 0.7 confidence. Rural partner footage is still needed before trusting unpaved frame-level recall.
