from datetime import timedelta
import pprint

def _parse_srt_time(time_str: str) -> timedelta:
    h, m, s_ms = time_str.replace(",", ".").split(":")
    return timedelta(hours=int(h), minutes=int(m), seconds=float(s_ms))

contents = [
    [
        {"start": _parse_srt_time("00:00:13,304"), "end": _parse_srt_time("00:00:15,849"), "text": "You might not remember him, but..."},
        {"start": _parse_srt_time("00:00:16,474"), "end": _parse_srt_time("00:00:18,309"), "text": "Stay there. I'm coming back."},
    ],
    [
        {"start": _parse_srt_time("00:00:13,388"), "end": _parse_srt_time("00:00:15,849"), "text": "你们或许不记得他了，但是…"},
        {"start": _parse_srt_time("00:00:16,349"), "end": _parse_srt_time("00:00:17,517"), "text": "老实待着"},
    ]
]

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
                if o_len >= 0.2 or o_len > 0.5 * min(s_len, p_len):
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

for m in merged_entries:
    print(f"{m['start']} --> {m['end']}\n{m['text']}\n")
