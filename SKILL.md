---
name: subtitle-learning-lab
description: "Extract, translate, and analyze subtitles for language learning. Use for: (1) extracting subtitle tracks, (2) automated translation/alignment, (3) vocabulary extraction, and (4) creating study-ready subtitle files."
---

# Subtitle Learning Lab

A comprehensive suite for converting video subtitles into language-learning resources. This tool handles everything from raw extraction to advanced vocabulary analysis and translation.

## Workflow Decision Tree

When processing a video file, determine the subtitle steps based on the user's prompt and the available subtitle tracks in the video:

1. **Multiple Subtitles Available**:
   - Merge the relevant subtitle tracks based on the languages requested in the user's prompt (e.g., merge English and Chinese).

2. **Only One Subtitle Available**:
   - If the video has only one subtitle track (e.g., English), translate this subtitle to the target language specified by the user's prompt (e.g., Chinese).

3. **No Subtitles Available**:
   - If there are no existing subtitles in the video, use the Whisper ASR pipeline to transcribe the audio and generate the subtitles.

## Step 1: Inspect & Prepare

List available subtitle streams in a video file:

```bash
python skills/subtitle-learning-lab/scripts/learning_lab.py list movie.mkv
```

## Step 2: Extract & Convert

Extract a specific track and convert to SRT if needed:

```bash
# Auto-detect language and extract to SRT
python skills/subtitle-learning-lab/scripts/learning_lab.py extract movie.mkv --to-srt
```

## Step 3: Merge Subtitles (Bilingual)

Merge multiple subtitle tracks into a single SRT file (e.g., for immersion learning):

```bash
# Merge specific indices
python skills/subtitle-learning-lab/scripts/learning_lab.py merge movie.mkv --indices 0 1 --output movie.bilingual.srt

# Merge by language codes
python skills/subtitle-learning-lab/scripts/learning_lab.py merge movie.mkv --languages eng jpn
```

## Step 4: Vocabulary & Translation (Coming Soon)

Future features include:
- `analyze`: Generate vocabulary frequency lists and definitions.
- `translate`: Auto-translate tracks using LLM or Translate APIs.
- `learning-pack`: Package multiple tracks for immersion practice.

## Step 5: Generate Learning Markdown

In addition to generating the subtitle file, create a corresponding Markdown file to help the user learn from the content. This file marks the timing of the video and should have the following structure for each subtitle segment:
1. **Original Language**: The original language text.
2. **Target Language**: The translated target language text.
3. **Vocabulary Hint**: Explanations of difficult vocabulary, chosen specifically based on the user's documented language proficiency level.

## Packaging for Study

When preparing files for study, use the following naming convention:
- `movie.eng.srt` (Reference)
- `movie.jpn.srt` (Target Language)
- `movie.vocab.csv` (Study List)
- `movie.learning.md` (Learning Markdown File)

## Quality + Safety Guardrails

- **Zero Loss**: Prefer stream copy (`-c:s copy`) for extraction when possible.
- **I/O Efficiency**: Avoid re-encoding video streams; focus only on subtitle data.
- **Privacy**: Process transcripts locally or via secure API endpoints when translating.

## Reference

- `references/subtitle-notes.md`: Compatibility and technical specs.
