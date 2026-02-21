# Subtitle Notes

## Quick compatibility rules

- Prefer **MKV** when keeping multiple subtitle tracks (ASS/SRT/VobSub/PGS).
- Use **MP4** only when target devices require it. MP4 subtitle support is narrower.
- If remux fails, keep original subtitle codec and switch container to MKV.

## Subtitle types and extraction strategy

1. **Soft subtitles (muxed stream)**
   - Extract with stream copy (`-c:s copy`)
   - Fast and lossless

2. **Hardcoded subtitles (burned into video pixels)**
   - No direct extraction
   - Run OCR on frames, then clean timing/text

3. **Streaming captions with DRM**
   - Respect platform terms and local law
   - Prefer legal exports, official caption files, or personal notes

## Language-learning packaging ideas

- Keep one subtitle track per purpose:
  - Track 1: original language
  - Track 2: translation
  - Track 3: vocab hints / annotations
- Keep annotation tracks concise (1 short hint per line).
- Save generated word lists to CSV for Anki import.
