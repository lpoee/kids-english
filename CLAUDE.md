## What this is
This is a static kids English flashcard app with one-page playback UI, local audio, and generated image assets for vocabulary, adjectives, and phrases.

## Setup
Run image generation through `scripts/generate_ai_flashcards.py`; generation uses local ComfyUI at `http://127.0.0.1:8188` and now defaults to `Flux.2 Klein 4B` (`flux-2-klein-4b.safetensors`), while still allowing an SDXL fallback via `--model sd_xl_base_1.0.safetensors`. Review targets the local Nemotron-compatible endpoint from `OMINI_REVIEW_URL` / `OMINI_REVIEW_MODEL` (default `http://127.0.0.1:18090/v1/chat/completions`). Review requests explicitly disable thinking mode and omit reasoning content so Nemotron returns parseable JSON in `message.content`. The default full pipeline remains `--only words,adjs,phrases,review,manifests,audit`.

## How it works
`index.html` defines the teaching catalog, the generator script derives the expected asset list from that catalog, renders PNGs through ComfyUI into `images/generated/{vocab,adjectives,phrases}`, stores review manifests under `images/generated/manifests`, and the audit step fails when any expected asset is missing, unreviewed, failed, or below the review score threshold. Prompt construction is layered as shared base + category module + word-specific patch + retry patch so fixes like `grape` or `run` stay scoped instead of polluting every card. `Flux.2 Klein 4B` uses a separate ComfyUI workflow branch (`UNETLoader` + `CLIPLoader` + `Flux2Scheduler`) rather than the SDXL checkpoint loader path.

## Lessons / gotchas
Do not reintroduce Openverse or manual download flow into the main pipeline: downloaded web images caused text, branding, and watermark contamination, so the supported path is local generate-only assets plus omni review and catalog-vs-output audit. Current known issue: if the local Nemotron/vLLM multimodal server crashes during review, the pipeline records `review_error` in the manifest instead of aborting the whole batch.
