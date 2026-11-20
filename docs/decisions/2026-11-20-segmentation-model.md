# 2026-11-20: Baseline segmentation model is SegFormer-B2 on ADE20K, not Mapillary Vistas

## Context

The plan said "SegFormer-B2 pretrained on Mapillary Vistas". A Hugging Face search on 2026-11-20 found no such checkpoint. The Vistas checkpoints that exist are `facebook/maskformer-resnet50-vistas` (165 MB) and `facebook/mask2former-swin-large-mapillary-vistas-semantic` (866 MB).

## Probe

Both CPU-sized candidates ran on 12 Wikimedia Commons photos of Vietnamese and muddy roads. The table shows the top classes in the bottom-center road box.

| photo (what it shows) | SegFormer-B2 ADE20K | MaskFormer-R50 Vistas |
|---|---|---|
| eahu (dirt road) | dirt track 53%, earth 12% | Road 52% |
| mud2 (mud road) | dirt track 100% | Road 100% |
| mud1 (mud + puddles) | water 58%, earth 32% | Road 100% |
| quangnam (village path) | dirt track 42%, path 20% | Road 68% |
| flood1 (flooded street) | water 68% | Road 78%, Water 12% |
| flood2 (flooded street) | water 90% | Road 98% |
| flood3 (flooded street) | road 71% | Water 54% |
| tiengiang2 (asphalt) | road 96% | Road 95% |

Speed: 1.1–1.6 s per photo for SegFormer, 1.7–2.1 s for MaskFormer, CPU.

## Decision

Use `nvidia/segformer-b2-finetuned-ade-512-512`. The Vistas label set has one `Road` class for paved and unpaved roads, so it cannot answer the main question (paved or not). ADE20K separates `road`, `dirt track`, `earth` and `path`.

## Consequences

- `mud` has no source class. It stays in the output schema and is always 0 until fine-tuning.
- Floodwater on a road is not reliable (flood3 above). With black side bars added to the frame, flood2 also became `paved`, so the result depends on the frame shape.
- Fine-tuning on labeled VN frames is the next step for both gaps. The model id is a CLI flag, so a fine-tuned checkpoint drops in.
