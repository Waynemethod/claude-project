import os
import time
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "scraptik.p.rapidapi.com",
}

BASE_URL = "https://scraptik.p.rapidapi.com"


def get_hashtag_id(hashtag: str) -> Optional[str]:
    """Look up the challenge ID (cid) for a hashtag name."""
    url = f"{BASE_URL}/search-hashtags"
    params = {"keyword": hashtag, "count": 5}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        data = resp.json()
        challenges = data.get("challenge_list") or []
        for item in challenges:
            info = item.get("challenge_info", {}) or {}
            name = (info.get("cha_name") or "").lower()
            if name == hashtag.lower().lstrip("#"):
                return str(info.get("cid", ""))
        # fallback: return first result's cid
        if challenges:
            return str(challenges[0].get("challenge_info", {}).get("cid", ""))
    except Exception as e:
        print(f"[get_hashtag_id] error: {e}")
    return None


def get_hashtag_videos(cid: str, count: int = 30) -> list[dict]:
    """Fetch videos from a hashtag using its challenge ID."""
    url = f"{BASE_URL}/hashtag-posts"
    params = {"cid": cid, "count": count, "cursor": 0, "compact": 0, "region": "US"}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        print(f"[get_hashtag_videos] cid={cid} status={resp.status_code}")
        data = resp.json()
        items = (
            data.get("aweme_list")
            or data.get("data", {}).get("aweme_list")
            or []
        )
        return items if isinstance(items, list) else []
    except Exception as e:
        print(f"[get_hashtag_videos] error: {e}")
        return []


def get_video_comments(video_id: str, count: int = 30) -> list[dict]:
    """Fetch top comments for a video."""
    url = f"{BASE_URL}/list-comments"
    params = {"aweme_id": video_id, "count": count, "cursor": 0, "region": "US", "compact": 0}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        data = resp.json()
        items = (
            data.get("comments")
            or data.get("data", {}).get("comments")
            or []
        )
        return items if isinstance(items, list) else []
    except Exception as e:
        print(f"[get_video_comments] error: {e}")
        return []


def fetch_trending_videos(count_per_tag: int = 50) -> list[dict]:
    """
    Fetch recent viral videos from broad trend-signal hashtags.
    Used for topic trend detection.
    """
    # Broad hashtags that capture viral/news content across topics
    trend_tags = [
        "viral", "news", "trending", "exposed", "drama",
        "storytime", "update", "breakingnews", "fyp", "omg"
    ]

    all_videos = {}
    for tag in trend_tags:
        cid = get_hashtag_id(tag)
        if not cid:
            print(f"[trend] no cid for #{tag}")
            continue
        videos = get_hashtag_videos(cid, count=count_per_tag)
        print(f"[trend] #{tag} cid={cid} → {len(videos)} videos")
        for v in videos:
            vid_id = v.get("aweme_id") or v.get("id", "")
            if vid_id:
                all_videos[vid_id] = v

    return list(all_videos.values())


def search_by_hashtags(query: str, count_per_tag: int = 50) -> list[dict]:
    """
    Search by user query terms as hashtags, plus broad trend tags.
    """
    query_tags = [w.strip("#").lower() for w in query.split() if w.strip()]
    broad_tags = ["viral", "news", "trending", "exposed", "drama", "storytime"]
    all_tags = list(dict.fromkeys(query_tags + broad_tags))

    all_videos = {}
    for tag in all_tags[:8]:
        cid = get_hashtag_id(tag)
        if not cid:
            print(f"[search] no cid for #{tag}")
            continue
        videos = get_hashtag_videos(cid, count=count_per_tag)
        print(f"[search] #{tag} cid={cid} → {len(videos)} videos")
        for v in videos:
            vid_id = v.get("aweme_id") or v.get("id", "")
            if vid_id:
                all_videos[vid_id] = v

    return list(all_videos.values())


def normalize_video(raw: dict) -> dict:
    """Flatten Scraptik aweme item into a consistent dict."""
    stats = raw.get("statistics", {}) or {}
    author = raw.get("author", {}) or {}
    video_info = raw.get("video", {}) or {}
    desc = raw.get("desc", "") or ""
    aweme_id = raw.get("aweme_id", "") or raw.get("id", "")
    username = author.get("unique_id", "") or author.get("uniqueId", "")

    cover = ""
    cover_data = video_info.get("cover") or video_info.get("origin_cover") or {}
    if isinstance(cover_data, dict):
        urls = cover_data.get("url_list", [])
        cover = urls[0] if urls else ""
    elif isinstance(cover_data, str):
        cover = cover_data

    duration = video_info.get("duration", 0) or 0

    return {
        "id": aweme_id,
        "desc": desc,
        "author_id": author.get("uid", "") or author.get("id", ""),
        "author_name": username,
        "author_display": author.get("nickname", username),
        "views": stats.get("play_count", 0) or stats.get("playCount", 0),
        "likes": stats.get("digg_count", 0) or stats.get("diggCount", 0),
        "comments_count": stats.get("comment_count", 0) or stats.get("commentCount", 0),
        "shares": stats.get("share_count", 0) or stats.get("shareCount", 0),
        "cover": cover,
        "create_time": raw.get("create_time", 0) or raw.get("createTime", 0),
        "duration": duration,
        "url": f"https://www.tiktok.com/@{username}/video/{aweme_id}",
    }


AI_SLOP_KEYWORDS = [
    "ai generated", "made with ai", "ai video", "midjourney", "sora ",
    "chatgpt", "dall-e", "stable diffusion", "ai art", "ai filter",
    "deepfake", "this is ai", "generated by ai",
]

BORING_SIGNALS = [
    "just talking", "sit down talk", "green screen only", "podcast clip",
]

def is_quality_video(v: dict) -> bool:
    """Filter for US-viral, recent, high-engagement, non-AI, non-boring videos."""
    # Must be recent (last 4 months)
    four_months_ago = int(time.time()) - (120 * 24 * 3600)
    if v.get("create_time", 0) < four_months_ago:
        return False

    views = v.get("views", 0)
    likes = v.get("likes", 0)
    comments = v.get("comments_count", 0)

    # Must be viral enough (100K+ views for trend detection)
    if views < 100_000:
        return False

    # Must have strong engagement (not bot-inflated) — at least 2% like rate
    if views > 0 and (likes / views) < 0.02:
        return False

    # Must have meaningful comment activity
    if views > 0 and (comments / views) < 0.001:
        return False

    desc_lower = v.get("desc", "").lower()

    # Reject AI slop
    if any(kw in desc_lower for kw in AI_SLOP_KEYWORDS):
        return False

    # Reject obviously boring formats
    if any(kw in desc_lower for kw in BORING_SIGNALS):
        return False

    # Skip very short clips (under 15s) — usually reaction clips or memes, not narrative
    duration = v.get("duration", 0)
    if duration > 0 and duration < 15:
        return False

    return True


def normalize_comment(raw: dict) -> dict:
    """Flatten a Scraptik comment item."""
    user = raw.get("user", {}) or {}
    return {
        "text": raw.get("text", ""),
        "likes": raw.get("digg_count", 0) or raw.get("diggCount", 0),
        "author": user.get("unique_id", "") or user.get("uniqueId", ""),
    }
