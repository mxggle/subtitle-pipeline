---
name: subtitle-learning-lab
description: "Subtitle processing engine: list/extract/transcribe/translate/merge subtitle tracks from local media files."
---

# Subtitle Learning Lab (Engine Scope)

This skill is now focused on **subtitle processing only**.

It handles:
1. Listing subtitle streams
2. Extracting subtitle tracks
3. Transcribing audio/video to SRT (Whisper)
4. Translating subtitle tracks (OpenAI-compatible APIs)
5. Merging multilingual tracks into bilingual/multilingual SRT

It does **not** generate learning markdown/vocabulary packs anymore.

## Workflow Decision Tree

When processing a video file, choose the path based on available subtitles:

1. **Multiple subtitles available** → merge selected tracks.
2. **Only one subtitle available** → translate to target language if needed.
3. **No subtitles available** → transcribe with Whisper, then optionally translate/merge.

## Commands

### 1) List streams
```bash
python skills/subtitle-learning-lab/scripts/learning_lab.py list movie.mkv
```

### 2) Extract track
```bash
python skills/subtitle-learning-lab/scripts/learning_lab.py extract movie.mkv --to-srt
python skills/subtitle-learning-lab/scripts/learning_lab.py extract movie.mkv --language eng --to-srt
```

### 3) Transcribe (Whisper)
```bash
python skills/subtitle-learning-lab/scripts/learning_lab.py transcribe movie.mkv
python skills/subtitle-learning-lab/scripts/learning_lab.py transcribe movie.mkv --language en --model small
```

### 4) Translate
```bash
# Requires OPENAI_API_KEY (or --api-key)
python skills/subtitle-learning-lab/scripts/learning_lab.py translate movie.eng.srt --target-language "Chinese"
```

### 5) Merge
```bash
python skills/subtitle-learning-lab/scripts/learning_lab.py merge movie.mkv --indices 0 1 --output movie.bilingual.srt
python skills/subtitle-learning-lab/scripts/learning_lab.py --verbose merge movie.mkv --languages eng chi
```

## Output Naming (Engine)

- `movie.eng.srt` (source/reference)
- `movie.zho.srt` (translated output)
- `movie.eng-chi.merged.srt` (merged bilingual output)

## Guardrails

- Prefer subtitle-only operations; avoid video re-encoding.
- Use `-c:s copy` where possible for lossless extraction.
- Keep translation alignment stable with source timestamps.
- Treat long local ASR jobs as expensive; split/chunk if needed.

## Reference

- `references/subtitle-notes.md`
