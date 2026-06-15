from flask import Flask, render_template, request, jsonify
from tiktok_api import search_videos, get_user_videos, get_video_comments, normalize_video, normalize_comment
from series_detector import group_into_series, score_continuation_comments

app = Flask(__name__)

DEFAULT_KEYWORDS = [
    "#part1 #part2",
    "storytime part 1",
    "episode 1 series",
    "drama series tiktok",
]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json()
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "Query is required"}), 400

    raw_videos = search_videos(query, count=50)
    videos = [normalize_video(v) for v in raw_videos]

    # Also pull more videos from creators who appear in results
    author_ids_seen = set()
    extra = []
    for v in videos:
        aid = v["author_id"]
        if aid and aid not in author_ids_seen:
            author_ids_seen.add(aid)
            if len(author_ids_seen) <= 5:  # limit extra API calls
                user_vids = get_user_videos(aid, count=30)
                extra.extend([normalize_video(uv) for uv in user_vids])

    all_videos = {v["id"]: v for v in videos + extra}
    series = group_into_series(list(all_videos.values()))

    return jsonify({"series": series[:20], "total_videos_scanned": len(all_videos)})


@app.route("/api/comments/<video_id>")
def comments(video_id: str):
    raw = get_video_comments(video_id, count=50)
    result = []
    for c in raw:
        result.append(normalize_comment(c))
    result.sort(key=lambda c: c["likes"], reverse=True)
    continuation_score = score_continuation_comments(raw)
    return jsonify({"comments": result[:30], "continuation_score": continuation_score})


@app.route("/api/series-comments", methods=["POST"])
def series_comments():
    """Pull top comments for every part in a series."""
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
    """Test the raw API response so we can see what Scraptik returns."""
    import requests, os
    key = os.getenv("RAPIDAPI_KEY")
    headers = {
        "x-rapidapi-key": key,
        "x-rapidapi-host": "scraptik.p.rapidapi.com",
    }
    # Try a few possible endpoint names
    results = {}
    for path in ["/search-posts", "/search-hashtags", "/user-posts", "/get-post-comments"]:
        try:
            r = requests.get(
                f"https://scraptik.p.rapidapi.com{path}",
                headers=headers,
                params={"keyword": "storytime", "count": 5},
                timeout=10,
            )
            results[path] = {"status": r.status_code, "body": r.json()}
        except Exception as e:
            results[path] = {"error": str(e)}
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
