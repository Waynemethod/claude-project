import os
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
    params = {"cid": cid, "count": count, "cursor": 0, "compact": 0}
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


def search_by_hashtags(query: str, count_per_tag: int = 30) -> list[dict]:
    """
    Main search: resolve hashtags from user query + fixed series hashtags,
    then pull videos from each. Returns combined flat list of raw videos.
    """
    # Core series-signal hashtags plus query-derived ones
    base_tags = ["part1", "part2", "storytime", "series", "episode1", "pt1", "pt2"]

    # Add words from user query as hashtags
    query_tags = [w.strip("#").lower() for w in query.split() if w.strip()]

    all_tags = list(dict.fromkeys(query_tags + base_tags))  # dedupe, query first

    all_videos = {}
    for tag in all_tags[:6]:  # limit API calls
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
        "url": f"https://www.tiktok.com/@{username}/video/{aweme_id}",
    }


def normalize_comment(raw: dict) -> dict:
    """Flatten a Scraptik comment item."""
    user = raw.get("user", {}) or {}
    return {
        "text": raw.get("text", ""),
        "likes": raw.get("digg_count", 0) or raw.get("diggCount", 0),
        "author": user.get("unique_id", "") or user.get("uniqueId", ""),
    }
