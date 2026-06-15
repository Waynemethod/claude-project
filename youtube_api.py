"""YouTube Data API v3 helpers for finding Roblox rant channels."""

import requests
from typing import List, Optional


def _fmt_count(n: int) -> str:
    """Format large numbers as 1.2M / 45.3K / 999."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _fmt_date(iso: str) -> str:
    """Format ISO 8601 date string to 'Jan 15, 2024'."""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %-d, %Y")
    except Exception:
        return iso[:10] if iso else ""


BASE = "https://www.googleapis.com/youtube/v3"


def search_channels(query: str, api_key: str) -> List[dict]:
    """Call YouTube search API and return raw channel items."""
    url = f"{BASE}/search"
    params = {
        "part": "snippet",
        "type": "channel",
        "q": query,
        "maxResults": 50,
        "key": api_key,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", [])


def get_channel_stats(channel_ids: List[str], api_key: str) -> List[dict]:
    """Get statistics and snippet for a list of channel IDs."""
    if not channel_ids:
        return []
    url = f"{BASE}/channels"
    params = {
        "part": "statistics,snippet",
        "id": ",".join(channel_ids),
        "key": api_key,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", [])


def get_recent_videos(channel_id: str, api_key: str) -> List[dict]:
    """Return up to 3 most recent videos with stats for a channel."""
    # Step 1: search for recent videos
    search_url = f"{BASE}/search"
    params = {
        "part": "snippet",
        "channelId": channel_id,
        "order": "date",
        "maxResults": 3,
        "type": "video",
        "key": api_key,
    }
    resp = requests.get(search_url, params=params, timeout=15)
    resp.raise_for_status()
    items = resp.json().get("items", [])

    if not items:
        return []

    video_ids = [item["id"]["videoId"] for item in items if item.get("id", {}).get("videoId")]
    if not video_ids:
        return []

    # Step 2: fetch stats for those video IDs
    stats_url = f"{BASE}/videos"
    stats_params = {
        "part": "statistics",
        "id": ",".join(video_ids),
        "key": api_key,
    }
    stats_resp = requests.get(stats_url, params=stats_params, timeout=15)
    stats_resp.raise_for_status()
    stats_items = stats_resp.json().get("items", [])
    stats_map = {s["id"]: s.get("statistics", {}) for s in stats_items}

    videos = []
    for item in items:
        vid_id = item.get("id", {}).get("videoId", "")
        snippet = item.get("snippet", {})
        published_raw = snippet.get("publishedAt", "")
        stats = stats_map.get(vid_id, {})
        view_count = int(stats.get("viewCount", 0))
        videos.append({
            "video_id": vid_id,
            "title": snippet.get("title", ""),
            "view_count": view_count,
            "view_count_fmt": _fmt_count(view_count),
            "published_at": _fmt_date(published_raw),
            "published_raw": published_raw,
            "video_url": f"https://www.youtube.com/watch?v={vid_id}",
        })

    return videos


def find_roblox_rant_channels(query: str, sort: str, api_key: str) -> List[dict]:
    """
    Orchestrate full search:
    1. Search for channels matching query
    2. Filter to channels with 5K+ subscribers
    3. Fetch recent videos for each qualifying channel
    4. Sort by subscribers (high to low) or recent upload date
    Returns list of channel dicts.
    """
    raw_items = search_channels(query, api_key)
    channel_ids = [
        item["id"]["channelId"]
        for item in raw_items
        if item.get("id", {}).get("channelId")
    ]

    if not channel_ids:
        return []

    stats_items = get_channel_stats(channel_ids, api_key)

    channels = []
    for item in stats_items:
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        sub_count = int(stats.get("subscriberCount", 0))

        # Filter: 5K+ subscribers only
        if sub_count < 5000:
            continue

        total_views = int(stats.get("viewCount", 0))
        video_count = int(stats.get("videoCount", 0))
        channel_id = item["id"]
        thumbnails = snippet.get("thumbnails", {})
        thumb = (
            thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
            or ""
        )

        channels.append({
            "channel_id": channel_id,
            "channel_name": snippet.get("title", ""),
            "subscriber_count": sub_count,
            "subscriber_count_fmt": _fmt_count(sub_count),
            "total_views": total_views,
            "total_views_fmt": _fmt_count(total_views),
            "video_count": video_count,
            "channel_url": f"https://www.youtube.com/channel/{channel_id}",
            "thumbnail_url": thumb,
            "recent_videos": [],
            "last_upload_date": "",
        })

    # Fetch recent videos for each channel
    for ch in channels:
        try:
            videos = get_recent_videos(ch["channel_id"], api_key)
            ch["recent_videos"] = videos
            if videos:
                ch["last_upload_date"] = videos[0].get("published_raw", "")
        except Exception:
            ch["recent_videos"] = []
            ch["last_upload_date"] = ""

    # Sort
    if sort == "recent":
        channels.sort(key=lambda c: c.get("last_upload_date", ""), reverse=True)
    else:
        # Default: subscribers high to low
        channels.sort(key=lambda c: c["subscriber_count"], reverse=True)

    return channels
