import re
from collections import defaultdict

# Patterns that signal a multi-part series
PART_PATTERNS = [
    r"\bpart\s*#?\s*(\d+)\b",
    r"\bpt\.?\s*#?\s*(\d+)\b",
    r"\bep(?:isode)?\s*#?\s*(\d+)\b",
    r"\b#part(\d+)\b",
    r"\b#pt(\d+)\b",
    r"\bchapter\s*#?\s*(\d+)\b",
    r"\bvol(?:ume)?\s*#?\s*(\d+)\b",
    r"\b(\d+)/(\d+)\b",  # e.g. "1/5"
]

CONTINUATION_COMMENTS = [
    "part 2", "part two", "pt 2", "what happened", "what happens next",
    "update", "more please", "need more", "continue", "sequel",
    "next part", "and then", "story time", "storytime", "what did",
    "did they", "did he", "did she", "did you", "omg no", "no way",
    "keep going", "i need more", "keep us updated",
]

SERIES_HASHTAGS = [
    "#part1", "#part2", "#part3", "#pt1", "#pt2", "#episode1",
    "#storytime", "#series", "#story", "#multipart", "#tiktokseries",
]


def extract_part_number(text: str) -> int | None:
    """Return the part number if found in text, else None."""
    lower = text.lower()
    for pattern in PART_PATTERNS:
        m = re.search(pattern, lower)
        if m:
            try:
                return int(m.group(1))
            except (IndexError, ValueError):
                pass
    return None


def has_series_hashtag(text: str) -> bool:
    lower = text.lower()
    return any(tag in lower for tag in SERIES_HASHTAGS)


def score_continuation_comments(comments: list[dict]) -> float:
    """
    Score 0-1 based on how many comments signal desire for continuation.
    """
    if not comments:
        return 0.0
    hits = 0
    for c in comments:
        body = (c.get("text", "") or "").lower()
        if any(phrase in body for phrase in CONTINUATION_COMMENTS):
            hits += 1
    return min(hits / max(len(comments), 1), 1.0)


def virality_score(video: dict) -> float:
    """Composite virality score (log-scaled to reduce outlier dominance)."""
    import math
    views = max(video.get("views", 0), 1)
    likes = max(video.get("likes", 0), 1)
    comments = max(video.get("comments_count", 0), 1)
    shares = max(video.get("shares", 0), 1)
    return math.log10(views) * 2 + math.log10(likes) + math.log10(comments) + math.log10(shares) * 1.5


def group_into_series(videos: list[dict]) -> list[dict]:
    """
    Group videos into series. Returns a list of series objects, each with:
      - title: inferred series name
      - author: creator info
      - parts: ordered list of video dicts
      - series_score: composite quality+virality score
      - escalation_score: how much views/likes grow across parts
    """
    # Group by author, then cluster by series name
    by_author = defaultdict(list)
    for v in videos:
        by_author[v["author_id"]].append(v)

    series_list = []

    for author_id, author_videos in by_author.items():
        # Try to cluster into named series within this creator's videos
        clusters: dict[str, list[dict]] = defaultdict(list)

        for v in author_videos:
            part_num = extract_part_number(v["desc"])
            has_tag = has_series_hashtag(v["desc"])

            if part_num is not None or has_tag:
                # Build a canonical series key: strip part numbers from desc
                key = re.sub(
                    r"\b(part|pt\.?|ep(?:isode)?|chapter|vol(?:ume)?)\s*#?\s*\d+",
                    "",
                    v["desc"].lower(),
                    flags=re.IGNORECASE,
                ).strip()[:60]
                key = re.sub(r"\s+", " ", key)
                clusters[key].append(v)

        for series_key, parts in clusters.items():
            if len(parts) < 2:
                continue  # Need at least 2 parts to be a series

            # Sort parts by their part number, then by create_time as fallback
            def sort_key(v):
                n = extract_part_number(v["desc"])
                return (n if n is not None else 999, v.get("create_time", 0))

            parts_sorted = sorted(parts, key=sort_key)

            escalation = _escalation_score(parts_sorted)
            avg_viral = sum(virality_score(v) for v in parts_sorted) / len(parts_sorted)

            author_name = parts_sorted[0].get("author_name", "unknown")
            author_display = parts_sorted[0].get("author_display", author_name)

            series_list.append({
                "title": _infer_title(series_key, parts_sorted),
                "author_name": author_name,
                "author_display": author_display,
                "author_id": author_id,
                "parts": parts_sorted,
                "part_count": len(parts_sorted),
                "total_views": sum(v.get("views", 0) for v in parts_sorted),
                "escalation_score": escalation,
                "avg_virality": avg_viral,
                "series_score": avg_viral * (1 + escalation) * (len(parts_sorted) ** 0.5),
            })

    # Sort best series first
    series_list.sort(key=lambda s: s["series_score"], reverse=True)
    return series_list


def _escalation_score(parts: list[dict]) -> float:
    """
    Measures whether views/likes escalate across parts (0 = flat, 1+ = strong growth).
    """
    if len(parts) < 2:
        return 0.0
    views = [max(v.get("views", 0), 1) for v in parts]
    # Ratio of last part views to first part views (capped at 10x)
    ratio = views[-1] / views[0]
    import math
    return min(math.log10(max(ratio, 1)), 1.0)


def _infer_title(series_key: str, parts: list[dict]) -> str:
    """Best-effort title: strip part numbers from the first video's desc."""
    desc = parts[0].get("desc", series_key)
    cleaned = re.sub(
        r"\b(part|pt\.?|ep(?:isode)?|chapter)\s*#?\s*\d+\b",
        "",
        desc,
        flags=re.IGNORECASE,
    )
    # Also remove hashtags for display
    cleaned = re.sub(r"#\w+", "", cleaned).strip(" |-_:,.")
    return cleaned[:80] or series_key[:80]
