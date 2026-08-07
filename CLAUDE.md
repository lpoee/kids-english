## What this is
This is the original static Kids English site: a one-page vocabulary/phrase player plus an 18-story branching Social mode with local child-voice audio and deterministic text-free animations.

## Setup
Serve locally with `python3 -m http.server`; use `scripts/generate_ai_flashcards.py` for flashcard images and `scripts/render_social_animations.py --force` for Social videos. Validate Social data/media with `python3 scripts/validate_social_dialogues.py`, then run `pytest tests/ -q`, `python3 scripts/test_ipad_audio.py`, and `python3 scripts/test_render_color_shape_cards.py`.

## How it works
`index.html` retains the original catalog and adds a Social entry; `assets/social-player.js` runs each branching story from `data/social_dialogues.json`. `scripts/render_social_animations.py` converts explicit per-turn semantic state—ownership, requests, transfer, waiting, seating, boundaries, alternatives, repair, and outcomes—into unique H.264 clips under `videos/social-dialogues/`, with posters and separate child-voice MP3s.

## Lessons / gotchas
Do not equate successful rendering or pytest output with visual approval: review every Social turn at start/middle/end and keep branch outcomes visibly distinct. Requests must not move the prop; fixed equipment must stay fixed; seated children need hips on the seat and feet below it; equivalent dialogue still needs the correct visible context. Mobile audio must continue using the persistent player and removable one-shot `ended` handlers so iOS does not lose the tap or duplicate playback.
