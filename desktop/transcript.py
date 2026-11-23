"""Dependency-free transcript representation and speaker turn reconstruction."""
from dataclasses import dataclass
import math
import re


@dataclass
class Turn:
    speaker: str
    start: float
    end: float
    text: str


def timestamp(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"


def _time(value, fallback):
    try:
        number = float(value)
        return number if math.isfinite(number) else fallback
    except (ValueError, TypeError):
        return fallback


def build_turns(segments: list[dict]) -> list[Turn]:
    """Respect word-level speakers; keep words lacking alignment instead of dropping them.

    Adjacent words from one voice merge, but long pauses and turns over 30 seconds
    start a new paragraph. Missing times inherit segment bounds (not fabricated
    word precision). Missing speaker labels remain explicitly unknown.
    """
    turns: list[Turn] = []
    for segment in segments:
        words = segment.get("words") or []
        if not words:
            words = [{"word": segment.get("text", ""), **{
                key: segment[key] for key in ("start", "end", "speaker") if key in segment
            }}]
        segment_start = max(0.0, _time(segment.get("start"), 0.0))
        segment_end = max(segment_start, _time(segment.get("end"), segment_start))
        for word in words:
            text = str(word.get("word", "")).strip()
            if not text:
                continue
            start = max(0.0, _time(word.get("start"), segment_start))
            end = max(start, _time(word.get("end"), segment_end))
            speaker = word.get("speaker") or segment.get("speaker") or "UNKNOWN"
            if (turns and turns[-1].speaker == speaker
                    and start - turns[-1].end <= 2.0
                    and end - turns[-1].start <= 30.0):
                previous = turns[-1]
                separator = "" if re.match(r"^[,.;:!?…%)\]}]", text) else " "
                previous.text += separator + text
                previous.end = max(previous.end, end)
            else:
                turns.append(Turn(speaker, start, end, text))
    return turns
