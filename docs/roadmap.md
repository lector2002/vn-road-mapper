# Roadmap

> Written 2026-11-21. Public imagery first; nothing depends on hiring or paying riders or labellers.
> Effort is in Devin sessions (one session is about one engineer-week). Calendar time is mostly waiting on volunteers and the OSM community.

## Where it stands

| Area | State | Evidence |
|---|---|---|
| Pipeline (frames → export) | All 6 stages run end to end | KartaView rides, Thanh Hóa and Cần Thơ |
| Surface on paved roads | Good | 47 of 48 hand sample, 28 of 28 OSM-tagged ways agree |
| Surface on dirt roads | Main weakness | 112 of 142 right; 27 of the 30 errors are dirt called `paved` |
| Mud | Not possible yet | ADE20K has no mud class |
| Flood / water | Untested on real footage | Only false `water` hits so far |
| Width | Unconfirmed | 8 of 235 frames got a width on helmet-camera footage; no ground truth |
| OSM upload | None, on purpose | Community not contacted yet |

Labelled Vietnamese frames are the bottleneck, not code: every accuracy test so far ends with "needs more Vietnamese rides". The 177 Cần Thơ labels were made by Claude in one pass and no person has checked them.

## Phase 0: one-command run and benchmark (done)

- `python -m pipeline.run` runs every stage on a video + GPX or a KartaView sequence.
- `python -m tools.benchmark` downloads the labelled KartaView photos and prints the surface confusion table, frame accuracy and per-way agreement.
- `requirements.txt` holds only what the code imports; model and test extras are separate files.
- A weekly CI job runs the real SegFormer model.
- The KartaView importer loads photos from the CDN: on 2026-11-21 the `storage*.openstreetcam.org` photo hosts resolved to a private address and every download timed out.

**Expect:** no accuracy change. Every later change is measured with the same command.

## Phase 1: a trusted Vietnamese test set (1–2 sessions)

No paid labellers, so:
- **Owner spot check (about 30 min):** check 50 of the 177 Cần Thơ labels on the label page. If 45 or more agree, keep the file as test data.
- **Label page:** a static HTML page like `review_template.html` that shows the road box and saves paved / unpaved / mud / water / unclear to CSV. Shareable with OSM Vietnam volunteers.
- **Model-assisted labels:** Claude labels Mapillary frames of untagged rural roads at full size, twice in random order; only frames where both passes agree go in, and the owner spot-checks a sample. Target about 800 frames from 20 or more sequences in 5 or more provinces (Mekong delta, central coast, northern mountains, Central Highlands), phone and dashcam. Freeze about 300 as a test set split by ride.

**Expect:** the real dirt-versus-paved error rate across Vietnam. It is probably worse than Cần Thơ's 79%, which is one region and one camera (inferred). Without a person checking a sample, label noise limits how far later numbers can be trusted.

## Phase 2: fix dirt called `paved` (1–2 sessions)

In order of cost:
1. The linear probe on SegFormer features (122–126 of 142 with 5 rides), retrained on Phase 1 data.
2. A stronger frozen backbone on the road crop (DINOv2 or CLIP features) as a second opinion.
3. Fine-tune the SegFormer decoder, with a real `mud` class once there are mud labels.

Pass rule stays: no new paved roads called unpaved, no Thanh Hóa way changes.

**Expect:** frame accuracy on clear frames from about 79% to about 88–92%, with paved called unpaved at 3% or less (inferred from the probe trend, not measured). Way-level accuracy is higher because fusion votes. If it stalls in the mid-80s, export `unpaved` only where two or more rides agree.

## Phase 3: OSM community and a small pilot (1 session, then 2–6 weeks of community time)

- Post the method, benchmark numbers and sample proposals on the OSM Vietnam forum and Telegram before any edit. Follow the OSM Automated Edits code of conduct and write an organised-editing wiki page.
- Pilot: 50–100 untagged ways in one district, from imagery from 2023 or later. People make the edits from the review map or a MapRoulette challenge; no script upload.

**Expect:** the main risk is social, not technical. The community may narrow which roads and tags are welcome. Reviewers accepting 90% or more of proposals is the bar for going further.

## Phase 4: width as classes (1 session)

Public imagery has unknown camera height and lens, so metric width within 0.5 m is out of reach. Riders and ambulances need a class: **motorbike only (under 2.5 m) / one car (2.5–4 m) / two cars (over 4 m)**.

- Scale each sequence from objects of known size (motorbikes, lane markings), or classify from the road-mask shape without a camera height.
- Check against the about 1,400 width-tagged minor roads in OSM Vietnam.

**Expect:** a usable 3-class width on straight narrow roads; most frames still get none (bends, wide roads).

## Phase 5: flood-risk layer (2–4 sessions)

Public imagery is rarely taken during floods, and water depth is not visible in a frame, so video alone cannot say "passable in flood season". Build it from layers instead:
1. Flood history from satellite flood maps (Sentinel-1 radar, Copernicus EMS, Global Flood Database) on OSM ways, in PostGIS.
2. Road height against its surroundings from a public elevation model (raised roads in the Mekong delta).
3. Water seen on the road in dated imagery, once Phase 1 has water labels.
4. Later, with partners: which roads closed in the last flood, from commune health stations or the Red Cross.

**Expect:** layers 1 and 2 give a district "likely cut off in floods" map without new footage. Layer 3 stays sparse. Checking the map needs partner reports.

## Phase 6: one province (2–3 sessions)

- Self-hosted Valhalla with a Vietnam extract (the public server is not for bulk use).
- Batch run over all KartaView and Mapillary sequences in one province; a GPU instead of 1.3 s per frame on CPU.
- PostGIS for ways, votes and flood layers; re-run when new imagery appears.

**Expect:** coverage only where public imagery exists, which favours main roads; HeiGIT's model covers 5.3% of Vietnam's road length for the same reason. Rural lanes, the project's target, stay thin until a partner offers footage.

## Summary

| Phase | Effort | Needs a person | What changes |
|---|---|---|---|
| 0 Run + benchmark | done | No | Same command measures every change |
| 1 Trusted test set | 1–2 sessions | Owner, 30 min | Real error rate across regions |
| 2 Dirt vs paved | 1–2 sessions | No | About 79% → about 90% (target) |
| 3 OSM pilot | 1 session | OSM volunteers | First accepted edits |
| 4 Width classes | 1 session | No | 3-class width on narrow roads |
| 5 Flood layer | 2–4 sessions | Partners to check | District flood-risk map |
| 6 One province | 2–3 sessions | No | Province coverage where imagery exists |
