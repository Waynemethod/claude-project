import os
import requests
from flask import Flask, render_template, request, jsonify
from tiktok_api import search_by_hashtags, get_video_comments, normalize_video, normalize_comment
from series_detector import group_into_series, score_continuation_comments

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json()
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "Query is required"}), 400

    raw_videos = search_by_hashtags(query, count_per_tag=30)
    videos = [normalize_video(v) for v in raw_videos]
    all_videos = {v["id"]: v for v in videos if v["id"]}
    series = group_into_series(list(all_videos.values()))

    return jsonify({"series": series[:20], "total_videos_scanned": len(all_videos)})


@app.route("/api/comments/<video_id>")
def comments(video_id: str):
    raw = get_video_comments(video_id, count=50)
    result = [normalize_comment(c) for c in raw]
    result.sort(key=lambda c: c["likes"], reverse=True)
    continuation_score = score_continuation_comments(raw)
    return jsonify({"comments": result[:30], "continuation_score": continuation_score})


@app.route("/api/series-comments", methods=["POST"])
def series_comments():
    data = request.get_json()
    parts = data.get("parts", [])
    all_comments = {}
    for part in parts:
        vid_id = part.get("id")
        if not vid_id:
            continue
        raw = get_video_comments(vid_id, count=30)
        formatted = [normalize_comment(c) for c in raw]
        formatted.sort(key=lambda c: c["likes"], reverse=True)
        all_comments[vid_id] = {
            "comments": formatted[:20],
            "continuation_score": score_continuation_comments(raw),
            "desc": part.get("desc", ""),
        }
    return jsonify({"by_video": all_comments})


@app.route("/api/debug")
def debug():
    """Test raw API responses."""
    key = os.getenv("RAPIDAPI_KEY")
    headers = {
        "x-rapidapi-key": key,
        "x-rapidapi-host": "scraptik.p.rapidapi.com",
    }
    results = {}

    # Step 1: get hashtag CID for "part1"
    try:
        r = requests.get(
            "https://scraptik.p.rapidapi.com/search-hashtags",
            headers=headers, params={"keyword": "part1", "count": 3}, timeout=10
        )
        results["search-hashtags"] = {"status": r.status_code, "body": r.json()}
        challenges = r.json().get("challenge_list", [])
        if challenges:
            cid = challenges[0].get("challenge_info", {}).get("cid")
            # Step 2: get videos from that hashtag
            r2 = requests.get(
                "https://scraptik.p.rapidapi.com/hashtag-posts",
                headers=headers, params={"cid": cid, "count": 5, "cursor": 0, "compact": 0}, timeout=10
            )
            results["hashtag-posts"] = {"status": r2.status_code, "cid_used": cid, "body": r2.json()}
    except Exception as e:
        results["error"] = str(e)

    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
