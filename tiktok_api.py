import os
import requests
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "tiktok-api23.p.rapidapi.com",
}

BASE_URL = "https://tiktok-api23.p.rapidapi.com"


def search_videos(keyword: str, count: int = 30) -> list[dict]:
    """Search TikTok videos by keyword/hashtag."""
    url = f"{BASE_URL}/api/search/video/"
    params = {"keywords": keyword, "count": count, "cursor": 0}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("videos", []) or []
    except Exception as e:
        print(f"[search_videos] error: {e}")
        return []


def get_user_videos(user_id: str, count: int = 35) -> list[dict]:
    """Fetch recent videos from a specific creator."""
    url = f"{BASE_URL}/api/user/posts/"
    params = {"user_id": user_id, "count": count, "cursor": 0}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("videos", []) or []
    except Exception as e:
        print(f"[get_user_videos] error: {e}")
        return []


def get_video_comments(video_id: str, count: int = 30) -> list[dict]:
    """Fetch top comments for a video."""
    url = f"{BASE_URL}/api/comment/list/"
    params = {"video_id": video_id, "count": count, "cursor": 0}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("comments", []) or []
    except Exception as e:
        print(f"[get_video_comments] error: {e}")
        return []


def normalize_video(raw: dict) -> dict:
    """Flatten raw API response into a consistent dict."""
    stats = raw.get("stats", {}) or {}
    author = raw.get("author", {}) or {}
    video_info = raw.get("video", {}) or {}
    desc = raw.get("desc", "") or ""

    return {
        "id": raw.get("id", ""),
        "desc": desc,
        "author_id": author.get("id", ""),
        "author_name": author.get("uniqueId", ""),
        "author_display": author.get("nickname", ""),
        "views": stats.get("playCount", 0),
        "likes": stats.get("diggCount", 0),
        "comments_count": stats.get("commentCount", 0),
        "shares": stats.get("shareCount", 0),
        "cover": video_info.get("cover", ""),
        "play_url": video_info.get("playAddr", ""),
        "create_time": raw.get("createTime", 0),
        "url": f"https://www.tiktok.com/@{author.get('uniqueId', '')}/video/{raw.get('id', '')}",
    }
