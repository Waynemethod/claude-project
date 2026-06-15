import os
import requests
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

# Using Scraptik — search "scraptik" on rapidapi.com to subscribe
HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "scraptik.p.rapidapi.com",
}

BASE_URL = "https://scraptik.p.rapidapi.com"


def search_videos(keyword: str, count: int = 30) -> list[dict]:
    """Search TikTok videos by keyword/hashtag."""
    url = f"{BASE_URL}/search-videos"
    params = {"keyword": keyword, "count": count, "offset": 0}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # Scraptik wraps results in data.aweme_list
        items = (
            data.get("data", {}).get("aweme_list")
            or data.get("aweme_list")
            or data.get("data", [])
            or []
        )
        return items if isinstance(items, list) else []
    except Exception as e:
        print(f"[search_videos] error: {e}")
        return []


def get_user_videos(user_id: str, count: int = 35) -> list[dict]:
    """Fetch recent videos from a specific creator."""
    url = f"{BASE_URL}/user-posts"
    params = {"user_id": user_id, "count": count, "max_cursor": 0}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        items = (
            data.get("aweme_list")
            or data.get("data", {}).get("aweme_list")
            or []
        )
        return items if isinstance(items, list) else []
    except Exception as e:
        print(f"[get_user_videos] error: {e}")
        return []


def get_video_comments(video_id: str, count: int = 30) -> list[dict]:
    """Fetch top comments for a video."""
    url = f"{BASE_URL}/comments"
    params = {"aweme_id": video_id, "count": count, "cursor": 0}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
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


def normalize_video(raw: dict) -> dict:
    """Flatten Scraptik aweme_list item into a consistent dict."""
    # Scraptik uses aweme-style response (same as TikTok internal API)
    stats = raw.get("statistics", {}) or {}
    author = raw.get("author", {}) or {}
    video_info = raw.get("video", {}) or {}
    desc = raw.get("desc", "") or ""
    aweme_id = raw.get("aweme_id", "") or raw.get("id", "")
    username = author.get("unique_id", "") or author.get("uniqueId", "")

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
        "cover": (video_info.get("cover", {}) or {}).get("url_list", [""])[0] if isinstance(video_info.get("cover"), dict) else video_info.get("cover", ""),
        "play_url": (video_info.get("play_addr", {}) or {}).get("url_list", [""])[0] if isinstance(video_info.get("play_addr"), dict) else "",
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
