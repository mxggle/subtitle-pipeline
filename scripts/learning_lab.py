#!/usr/bin/env python3
"""Subtitle processing CLI for local media files.

Examples:
  python scripts/learning_lab.py list movie.mkv
  python scripts/learning_lab.py extract movie.mkv
  python scripts/learning_lab.py extract movie.mkv --index 0
  python scripts/learning_lab.py extract movie.mkv --language eng --to-srt
  python scripts/learning_lab.py transcribe movie.mkv --model turbo
  python scripts/learning_lab.py translate movie.eng.srt --target-language "Chinese"
  python scripts/learning_lab.py merge movie.mkv --languages eng chi --verbose
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None



# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Merge-overlap thresholds: a secondary subtitle entry is considered to
# overlap with a primary entry when the overlap duration meets *either*
# of these criteria.
MIN_OVERLAP_SECONDS = 0.2   # absolute minimum overlap (200 ms)
MIN_OVERLAP_RATIO = 0.5     # overlap must exceed 50 % of the shorter entry

CODEC_TO_EXT = {
    "subrip": "srt",
    "ass": "ass",
    "ssa": "ssa",
    "webvtt": "vtt",
    "mov_text": "srt",
    "hdmv_pgs_subtitle": "sup",
}

# Module-level verbosity flag, set by CLI --verbose / --quiet.
_verbose = False


def _parse_srt_time(time_str: str) -> timedelta:
    """Convert SRT time string (00:00:00,000) to timedelta."""
    h, m, s_ms = time_str.replace(",", ".").split(":")
    return timedelta(hours=int(h), minutes=int(m), seconds=float(s_ms))


def _format_srt_time(td: timedelta) -> str:
    """Convert timedelta to SRT time string (00:00:00,000)."""
    total_seconds = td.total_seconds()
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace(".", ",")


def _parse_srt(content: str) -> list[dict]:
    """Parse SRT content into a list of dictionaries.

    Handles both LF and CRLF line endings and ensures the last entry
    is always captured even when the file lacks a trailing blank line.
    """
    # Normalise line endings so the regex always works.
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    # Guarantee a trailing double-newline so the non-greedy text group
    # can always find its terminator.
    if not content.endswith("\n\n"):
        content += "\n\n"

    entries = []
    pattern = re.compile(
        r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\n\d+\n)",
        re.DOTALL,
    )
    for match in pattern.finditer(content):
        entries.append(
            {
                "start": _parse_srt_time(match.group(2)),
                "end": _parse_srt_time(match.group(3)),
                "text": match.group(4).strip(),
                "index": int(match.group(1)),
            }
        )
    return entries


def _require_bin(name: str) -> None:
    if shutil.which(name) is None:
        print(f"error: missing required binary '{name}'", file=sys.stderr)
        sys.exit(2)


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a subprocess, capturing output with explicit UTF-8 encoding.

    If the module-level ``_verbose`` flag is set, any stderr output is
    forwarded to the caller's stderr even when the command succeeds.
    """
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if _verbose and p.stderr:
        print(p.stderr, file=sys.stderr)
    return p


def probe_subtitle_streams(input_path: Path) -> list[dict]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "s",
        "-show_entries",
        "stream=index,codec_name:stream_tags=language,title",
        "-of",
        "json",
        str(input_path),
    ]
    p = _run(cmd)
    if p.returncode != 0:
        print(p.stderr.strip() or "ffprobe failed", file=sys.stderr)
        sys.exit(p.returncode)

    payload = json.loads(p.stdout or "{}")
    streams = payload.get("streams", [])
    out = []
    for i, s in enumerate(streams):
        tags = s.get("tags", {}) or {}
        out.append(
            {
                "subtitle_index": i,
                "global_index": s.get("index"),
                "codec": s.get("codec_name", "unknown"),
                "language": tags.get("language", "und"),
                "title": tags.get("title", ""),
            }
        )
    return out


def list_streams(input_path: Path) -> int:
    streams = probe_subtitle_streams(input_path)
    if not streams:
        print("No subtitle streams found.")
        return 1

    print("subtitle_index\tglobal_index\tlanguage\tcodec\ttitle")
    for s in streams:
        print(
            f"{s['subtitle_index']}\t{s['global_index']}\t{s['language']}\t{s['codec']}\t{s['title']}"
        )
    return 0


def pick_stream(streams: list[dict], index: int | None, language: str | None) -> dict:
    if index is not None:
        for s in streams:
            if s["subtitle_index"] == index:
                return s
        raise ValueError(f"No subtitle stream at index {index}")

    if language:
        language = language.lower()
        for s in streams:
            if str(s["language"]).lower() == language:
                return s
        raise ValueError(f"No subtitle stream with language={language}")

    if streams:
        return streams[0]
    raise ValueError("No subtitle streams found")


def extract_stream(
    input_path: Path,
    output_path: Path | None,
    index: int | None,
    language: str | None,
    to_srt: bool,
) -> int:
    streams = probe_subtitle_streams(input_path)
    if not streams:
        print("No subtitle streams found.", file=sys.stderr)
        return 1

    try:
        chosen = pick_stream(streams, index=index, language=language)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    codec = str(chosen["codec"])
    ext = "srt" if to_srt else CODEC_TO_EXT.get(codec, "subtitle")

    if output_path is None:
        output_path = input_path.with_suffix("")
        output_path = output_path.parent / f"{output_path.name}.{chosen['language']}.{ext}"

    map_spec = f"0:s:{chosen['subtitle_index']}"
    cmd = ["ffmpeg", "-y", "-i", str(input_path), "-map", map_spec]

    if to_srt:
        cmd += ["-c:s", "srt"]
    else:
        cmd += ["-c:s", "copy"]

    cmd += [str(output_path)]

    p = _run(cmd)
    if p.returncode != 0:
        print(p.stderr.strip() or "ffmpeg failed", file=sys.stderr)
        return p.returncode

    print(
        f"Extracted subtitle stream {chosen['subtitle_index']} ({chosen['language']}, {codec}) -> {output_path}"
    )
    return 0


def merge_streams(
    input_path: Path,
    output_path: Path | None,
    indices: list[int] | None,
    languages: list[str] | None,
) -> int:
    streams = probe_subtitle_streams(input_path)
    if not streams:
        print("No subtitle streams found.", file=sys.stderr)
        return 1

    chosen_streams = []
    if indices:
        for idx in indices:
            found = False
            for s in streams:
                if s["subtitle_index"] == idx:
                    chosen_streams.append(s)
                    found = True
                    break
            if not found:
                print(f"error: No subtitle stream at index {idx}", file=sys.stderr)
                return 1
    elif languages:
        for lang in languages:
            found = False
            for s in streams:
                if str(s["language"]).lower() == lang.lower():
                    chosen_streams.append(s)
                    found = True
                    break
            if not found:
                print(f"error: No subtitle stream with language={lang}", file=sys.stderr)
                return 1
    else:
        # Default to first two streams if available
        chosen_streams = streams[:2]

    if len(chosen_streams) < 2:
        print("error: Need at least 2 streams to merge.", file=sys.stderr)
        return 1

    # Extract all chosen streams to SRT format in-memory
    contents = []
    for s in chosen_streams:
        map_spec = f"0:s:{s['subtitle_index']}"
        cmd = ["ffmpeg", "-y", "-i", str(input_path), "-map", map_spec, "-c:s", "srt", "-f", "srt", "-"]
        p = _run(cmd)
        if p.returncode != 0:
            print(f"ffmpeg failed for stream {s['subtitle_index']}", file=sys.stderr)
            return p.returncode
        contents.append(_parse_srt(p.stdout))

    # Merge logic mapping secondary streams to the primary (first) stream
    primary_entries = []
    for entry in contents[0]:
        primary_entries.append({
            "start": entry["start"],
            "end": entry["end"],
            "texts": [entry["text"]]
        })

    standalone_entries = []
    for stream_idx in range(1, len(contents)):
        for s_entry in contents[stream_idx]:
            overlaps = []
            s_len = (s_entry["end"] - s_entry["start"]).total_seconds()

            for p_entry in primary_entries:
                overlap_start = max(p_entry["start"], s_entry["start"])
                overlap_end = min(p_entry["end"], s_entry["end"])
                o_len = (overlap_end - overlap_start).total_seconds()
                if o_len > 0:
                    p_len = (p_entry["end"] - p_entry["start"]).total_seconds()
                    if o_len >= MIN_OVERLAP_SECONDS or o_len > MIN_OVERLAP_RATIO * min(s_len, p_len):
                        overlaps.append(p_entry)

            if not overlaps:
                standalone_entries.append({
                    "start": s_entry["start"],
                    "end": s_entry["end"],
                    "texts": [s_entry["text"]]
                })
            else:
                for p in overlaps:
                    if s_entry["text"] not in p["texts"]:
                        p["texts"].append(s_entry["text"])

    merged_entries = []
    for p in primary_entries:
        merged_entries.append({
            "start": p["start"],
            "end": p["end"],
            "text": "\n".join(p["texts"])
        })
    for s in standalone_entries:
        merged_entries.append({
            "start": s["start"],
            "end": s["end"],
            "text": "\n".join(s["texts"])
        })

    merged_entries.sort(key=lambda x: x["start"])

    # Generate SRT output
    lines = []
    for i, entry in enumerate(merged_entries, 1):
        lines.append(str(i))
        lines.append(f"{_format_srt_time(entry['start'])} --> {_format_srt_time(entry['end'])}")
        lines.append(entry["text"])
        lines.append("")

    merged_srt = "\n".join(lines)

    if output_path is None:
        langs = "-".join([s["language"] for s in chosen_streams])
        output_path = input_path.with_suffix("")
        output_path = output_path.parent / f"{output_path.name}.{langs}.merged.srt"

    output_path.write_text(merged_srt, encoding="utf-8")
    print(f"Merged {len(chosen_streams)} streams into -> {output_path}")
    return 0


def _chunk_list(lst: list, chunk_size: int) -> list[list]:
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def translate_chunk(client, chunk: list[dict], target_language: str, model: str) -> list[str]:
    """Translate a chunk of subtitle dictionaries using the LLM.
    Returns a list of translated text strings corresponding to the input chunk.
    """
    if not OpenAI:
        raise RuntimeError("openai is not installed. Run: pip install openai")
        
    prompt = f"You are a professional movie translator. Translate the following {len(chunk)} subtitle lines to {target_language}.\n\n"
    prompt += "Respond ONLY with a valid JSON array of strings, where each string is the translated line. Do not include markdown formatting like ```json.\n"
    prompt += f"There are exactly {len(chunk)} lines. You MUST return exactly {len(chunk)} translated strings in the JSON array. Do not include original text, notes, or preambles.\n"
    prompt += "Look at the surrounding context to resolve ambiguities, but keep the translations vertically aligned to the original indices.\n\n"
    
    for entry in chunk:
        prompt += f"Line {entry['index']}: {entry['text']}\n"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional subtitle translator. You only output valid JSON arrays of strings."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        import json
        try:
            translated_texts = json.loads(content.strip())
            if not isinstance(translated_texts, list):
                raise ValueError("LLM did not return a JSON array")
        except json.JSONDecodeError:
            print(f"Warning: Failed to parse LLM output as JSON. Output was:\n{content}\nAttempting line-by-line fallback...", file=sys.stderr)
            translated_texts = [p.strip() for p in content.strip().split('\n') if p.strip()]
        
        # Fallback/Safety Check: Ensure strictly identical length
        if len(translated_texts) != len(chunk):
            print(f"Warning: LLM returned {len(translated_texts)} lines instead of {len(chunk)}.", file=sys.stderr)
            print(f"Warning: Fallback failed. Adding blank lines to match length. Expected {len(chunk)}, got {len(translated_texts)}.", file=sys.stderr)
            # Just take what we can and pad the rest with empty strings
            translated_texts = translated_texts[:len(chunk)]
            while len(translated_texts) < len(chunk):
                translated_texts.append("")
                
        return translated_texts
        
    except Exception as e:
        print(f"Error calling LLM: {e}", file=sys.stderr)
        raise

def translate_stream(
    input_path: Path,
    output_path: Path | None,
    target_language: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str = "gpt-4o-mini"
) -> int:
    """Extract a track (if video), and translate using LLM context chunking."""
    if not OpenAI:
        print("error: openai package is required. Run 'pip install openai'", file=sys.stderr)
        return 1
        
    if load_dotenv:
        load_dotenv()
        
    # Setup LLM Client
    client_api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not client_api_key:
        print("error: API key is required via --api-key or OPENAI_API_KEY env var in .env file.", file=sys.stderr)
        return 1
        
    client = OpenAI(api_key=client_api_key, base_url=base_url)

    # If it's not an srt, assume it's a video and try to extract the first track to a temporary file,
    # or fail if multiple tracks? For now assume it's already an SRT if it ends with .srt
    srt_content = ""
    is_temp_srt = False
    temp_srt_path = input_path.with_suffix(".tmp.srt")
    
    if input_path.suffix.lower() == ".srt":
        srt_content = input_path.read_text(encoding="utf-8")
    else:
        print(f"Extracting primary subtitle stream from {input_path.name} to translate...")
        ret = extract_stream(input_path, temp_srt_path, index=0, language=None, to_srt=True)
        if ret != 0:
            return ret
        srt_content = temp_srt_path.read_text(encoding="utf-8")
        is_temp_srt = True

    entries = _parse_srt(srt_content)
    if not entries:
        print("error: No subtitle entries found to translate.", file=sys.stderr)
        if is_temp_srt and temp_srt_path.exists(): temp_srt_path.unlink()
        return 1

    print(f"Translating {len(entries)} subtitle segments to {target_language}...")
    
    # Process in chunks of 50
    CHUNK_SIZE = 50
    translated_entries = []
    chunks = list(_chunk_list(entries, CHUNK_SIZE))
    
    try:
        for i, chunk in enumerate(chunks, 1):
            if _verbose:
                print(f"Translating chunk {i}/{len(chunks)}...", file=sys.stderr)
            texts = translate_chunk(client, chunk, target_language, model=model)
            for entry, trans_text in zip(chunk, texts):
                # Copy the entry and update the text
                translated_entries.append({
                    "start": entry["start"],
                    "end": entry["end"],
                    "text": trans_text
                })
    except Exception as e:
        print("Translation aborted due to an error.", file=sys.stderr)
        if is_temp_srt and temp_srt_path.exists(): temp_srt_path.unlink()
        return 1

    # Format back to SRT
    lines = []
    for i, entry in enumerate(translated_entries, 1):
        lines.append(str(i))
        lines.append(f"{_format_srt_time(entry['start'])} --> {_format_srt_time(entry['end'])}")
        lines.append(entry["text"])
        lines.append("")
        
    translated_srt_content = "\n".join(lines)
    
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}.{target_language.lower()}.srt"
        
    output_path.write_text(translated_srt_content, encoding="utf-8")
    print(f"Translation complete! Saved to {output_path}")
    
    if is_temp_srt and temp_srt_path.exists():
        temp_srt_path.unlink()
        
    return 0


def transcribe_stream(
    input_path: Path,
    output_path: Path | None,
    model: str = "turbo",
    language: str | None = None
) -> int:
    """Run Whisper ASR on a media file to generate subtitles."""
    if shutil.which("whisper") is None:
        print("error: 'whisper' command not found. Please install openai-whisper.", file=sys.stderr)
        return 1

    print(f"Transcribing {input_path.name} using Whisper ({model} model)...")
    
    cmd = [
        "whisper",
        str(input_path),
        "--model", model,
        "--output_format", "srt",
    ]
    
    if language:
        cmd.extend(["--language", language])
        
    out_dir = output_path.parent if output_path else input_path.parent
    cmd.extend(["--output_dir", str(out_dir)])
    
    p = _run(cmd)
    if p.returncode != 0:
        print(p.stderr.strip() or "whisper failed", file=sys.stderr)
        return p.returncode
        
    expected_out = out_dir / f"{input_path.stem}.srt"
    
    if output_path and expected_out.exists() and output_path.absolute() != expected_out.absolute():
        shutil.move(str(expected_out), str(output_path))
        print(f"Transcription complete! Saved to {output_path}")
    elif expected_out.exists():
        print(f"Transcription complete! Saved to {expected_out}")
    else:
        print(f"Warning: Expected whisper output {expected_out} not found.", file=sys.stderr)

    return 0


def main() -> int:
    _require_bin("ffprobe")
    _require_bin("ffmpeg")

    parser = argparse.ArgumentParser(description="Subtitle processing CLI (list/extract/transcribe/translate/merge)")
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="show ffmpeg/ffprobe stderr output for debugging",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="suppress informational output (errors are still printed)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List subtitle streams")
    p_list.add_argument("input", type=Path)

    p_extract = sub.add_parser("extract", help="Extract one subtitle stream")
    p_extract.add_argument("input", type=Path)
    p_extract.add_argument("--index", type=int, default=None, help="subtitle stream index (0-based)")
    p_extract.add_argument("--language", type=str, default=None, help="language code (e.g. eng, jpn)")
    p_extract.add_argument("--to-srt", action="store_true", help="convert subtitle stream to srt")
    p_extract.add_argument("--output", type=Path, default=None)

    p_merge = sub.add_parser("merge", help="Merge multiple subtitle streams into one")
    p_merge.add_argument("input", type=Path)
    p_merge.add_argument(
        "--indices", type=int, nargs="+", help="subtitle stream indices to merge"
    )
    p_merge.add_argument(
        "--languages", type=str, nargs="+", help="language codes to merge (e.g. eng jpn)"
    )
    p_merge.add_argument("--output", type=Path, default=None)
    
    p_translate = sub.add_parser("translate", help="Translate a subtitle file or stream to a target language using openai SDK")
    p_translate.add_argument("input", type=Path, help="input .srt file or video file")
    p_translate.add_argument("--target-language", type=str, required=True, help="target language to translate to (e.g. Chinese)")
    p_translate.add_argument("--api-key", type=str, help="API Key (or set OPENAI_API_KEY env var in .env)")
    p_translate.add_argument("--base-url", type=str, help="Custom Base URL for alternative providers (e.g. DeepSeek, vLLM)")
    p_translate.add_argument("--model", type=str, default="gpt-4o-mini", help="Model name to use (default: gpt-4o-mini)")
    p_translate.add_argument("--output", type=Path, default=None, help="output .srt file path")

    p_transcribe = sub.add_parser("transcribe", help="Transcribe video/audio to subtitle using Whisper ASR")
    p_transcribe.add_argument("input", type=Path, help="input video or audio file")
    p_transcribe.add_argument("--model", type=str, default="turbo", help="Whisper model to use (default: turbo)")
    p_transcribe.add_argument("--language", type=str, default=None, help="Language code for transcription (e.g. en, ja)")
    p_transcribe.add_argument("--output", type=Path, default=None, help="output .srt file path")

    args = parser.parse_args()

    # Set module-level verbosity.
    global _verbose
    _verbose = args.verbose

    if args.command == "list":
        return list_streams(args.input)

    if args.command == "extract":
        if args.index is not None and args.language:
            print("error: use either --index or --language, not both", file=sys.stderr)
            return 2
        return extract_stream(args.input, args.output, args.index, args.language, args.to_srt)

    if args.command == "merge":
        if args.indices and args.languages:
            print("error: use either --indices or --languages, not both", file=sys.stderr)
            return 2
        return merge_streams(args.input, args.output, args.indices, args.languages)

    if args.command == "translate":
        return translate_stream(args.input, args.output, args.target_language, args.api_key, args.base_url, args.model)

    if args.command == "transcribe":
        return transcribe_stream(args.input, args.output, args.model, args.language)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
