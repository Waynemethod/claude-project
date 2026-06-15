import os
import requests
from flask import Flask, render_template, request, jsonify
from tiktok_api import fetch_trending_videos, search_by_hashtags, normalize_video, is_quality_video
from trend_detector import detect_trends

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/trends", methods=["POST"])
def trends():
    """Scan TikTok and surface trending topics (multiple creators, same subject)."""
    data = request.get_json() or {}
    query = (data.get("query") or "").strip()

    if query:
        raw_videos = search_by_hashtags(query, count_per_tag=50)
    else:
        raw_videos = fetch_trending_videos(count_per_tag=50)

    videos = [normalize_video(v) for v in raw_videos]
    filtered = [v for v in videos if v["id"] and is_quality_video(v)]

    print(f"[trends] {len(raw_videos)} raw → {len(filtered)} after quality filter")

    trend_list = detect_trends(filtered)
    return jsonify({
        "trends": trend_list,
        "videos_scanned": len(filtered),
    })


@app.route("/api/debug")
def debug():
    """Test raw API responses."""
    key = os.getenv("RAPIDAPI_KEY")
    headers = {
        "x-rapidapi-key": key,
        "x-rapidapi-host": "scraptik.p.rapidapi.com",
    }
    results = {}
    try:
        r = requests.get(
            "https://scraptik.p.rapidapi.com/search-hashtags",
            headers=headers, params={"keyword": "viral", "count": 3}, timeout=10
        )
        results["search-hashtags"] = {"status": r.status_code, "body": r.json()}
        challenges = r.json().get("challenge_list", [])
        if challenges:
            cid = challenges[0].get("challenge_info", {}).get("cid")
            r2 = requests.get(
                "https://scraptik.p.rapidapi.com/hashtag-posts",
                headers=headers,
                params={"cid": cid, "count": 5, "cursor": 0, "compact": 0, "region": "US"},
                timeout=10
            )
            results["hashtag-posts"] = {"status": r2.status_code, "cid_used": cid, "body": r2.json()}
    except Exception as e:
        results["error"] = str(e)
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
