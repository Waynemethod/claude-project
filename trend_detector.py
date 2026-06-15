import re
import math
import time
from collections import defaultdict
from typing import List, Dict

# Common words to ignore when extracting topics
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "this", "that", "these", "those",
    "i", "you", "he", "she", "we", "they", "it", "me", "him", "her", "us",
    "my", "your", "his", "its", "our", "their", "what", "who", "how", "when",
    "where", "why", "which", "if", "so", "just", "like", "get", "got",
    "not", "no", "yes", "up", "out", "about", "after", "before", "going",
    "went", "come", "came", "see", "saw", "say", "said", "go", "put",
    "know", "think", "make", "made", "take", "took", "want", "need",
    "pov", "pls", "plz", "omg", "lol", "lmao", "idk", "imo", "tbh",
    "im", "ive", "its", "dont", "cant", "wont", "didnt", "isnt",
    "fyp", "foryou", "foryoupage", "viral", "trending", "tiktok",
    "video", "watch", "new", "part", "day", "time", "way", "thing",
    "people", "person", "man", "woman", "girl", "boy", "guy", "one",
    "two", "first", "last", "more", "most", "all", "now", "here",
    "there", "then", "than", "too", "also", "very", "really", "so",
}


def extract_keywords(text: str) -> List[str]:
    """Extract meaningful words and named entities from text."""
    # Remove URLs
    text = re.sub(r"http\S+", "", text)
    # Remove hashtag symbol but keep the word
    text = re.sub(r"#(\w+)", r"\1", text)
    # Remove @mentions
    text = re.sub(r"@\w+", "", text)
    # Remove emojis and special chars
    text = re.sub(r"[^\w\s']", " ", text)

    words = text.lower().split()
    return [w for w in words if len(w) > 2 and w not in STOPWORDS]


def extract_named_entities(text: str) -> List[str]:
    """Extract capitalized multi-word phrases (likely names/places/events)."""
    # Remove hashtags and mentions first
    text = re.sub(r"[#@]\w+", "", text)
    # Find sequences of capitalized words (2+ in a row = likely a name)
    entities = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)
    # Also single capitalized words that aren't sentence-starters
    # (heuristic: if word appears mid-sentence)
    return entities


def ngrams(words: List[str], n: int) -> List[str]:
    """Generate n-grams from word list."""
    return [" ".join(words[i:i+n]) for i in range(len(words) - n + 1)]


def score_topic_cluster(videos: List[Dict]) -> float:
    """Score a topic cluster by unique creators, views, and recency."""
    unique_creators = len({v["author_id"] for v in videos})
    total_views = sum(v.get("views", 0) for v in videos)

    # Recency boost: videos from last 3 days get extra weight
    three_days_ago = int(time.time()) - (3 * 24 * 3600)
    recent_count = sum(1 for v in videos if v.get("create_time", 0) > three_days_ago)
    recency_boost = 1 + (recent_count / max(len(videos), 1))

    # Score: unique creators matter most, then views, then recency
    return (unique_creators ** 1.5) * math.log10(max(total_views, 1)) * recency_boost


def detect_trends(videos: List[Dict]) -> List[Dict]:
    """
    Group videos by shared topic and surface trending subjects.
    Returns list of trend objects sorted by score.
    """
    two_weeks_ago = int(time.time()) - (14 * 24 * 3600)

    # Filter to last 2 weeks only
    recent_videos = [v for v in videos if v.get("create_time", 0) > two_weeks_ago]

    # Build phrase -> video mapping
    phrase_to_videos: Dict[str, List[Dict]] = defaultdict(list)

    for v in recent_videos:
        desc = v.get("desc", "")

        # Extract named entities (highest signal)
        entities = extract_named_entities(desc)
        for entity in entities:
            entity_lower = entity.lower()
            if len(entity_lower) > 4:
                phrase_to_videos[entity_lower].append(v)

        # Extract 2-grams and 3-grams from keywords
        keywords = extract_keywords(desc)
        for phrase in ngrams(keywords, 2):
            phrase_to_videos[phrase].append(v)
        for phrase in ngrams(keywords, 3):
            phrase_to_videos[phrase].append(v)

    # Filter: only phrases mentioned by 3+ DIFFERENT creators
    trends = []
    seen_video_sets = []

    for phrase, vids in phrase_to_videos.items():
        # Dedupe videos within this phrase
        seen = set()
        unique_vids = []
        for v in vids:
            if v["id"] not in seen:
                seen.add(v["id"])
                unique_vids.append(v)

        unique_creators = len({v["author_id"] for v in unique_vids})
        if unique_creators < 2:
            continue

        # Skip if this phrase is basically the same set of videos as another trend
        vid_ids = frozenset(v["id"] for v in unique_vids)
        is_duplicate = False
        for seen_set in seen_video_sets:
            overlap = len(vid_ids & seen_set) / max(len(vid_ids), 1)
            if overlap > 0.8:
                is_duplicate = True
                break
        if is_duplicate:
            continue
        seen_video_sets.append(vid_ids)

        total_views = sum(v.get("views", 0) for v in unique_vids)
        score = score_topic_cluster(unique_vids)

        # Sort videos by views descending for display
        top_videos = sorted(unique_vids, key=lambda v: v.get("views", 0), reverse=True)

        trends.append({
            "topic": phrase.title(),
            "creator_count": unique_creators,
            "video_count": len(unique_vids),
            "total_views": total_views,
            "trend_score": score,
            "top_videos": top_videos[:5],
            "newest_post": max(v.get("create_time", 0) for v in unique_vids),
        })

    # Sort by trend score
    trends.sort(key=lambda t: t["trend_score"], reverse=True)

    # Dedupe by topic name similarity
    final = []
    seen_topics = []
    for t in trends:
        topic_words = set(t["topic"].lower().split())
        is_sub = False
        for st in seen_topics:
            if topic_words <= st or st <= topic_words:
                is_sub = True
                break
        if not is_sub:
            seen_topics.append(topic_words)
            final.append(t)

    return final[:30]
