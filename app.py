import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from youtube_api import find_roblox_rant_channels
from shorts_analyzer import analyze_short

load_dotenv()

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/shorts")
def shorts_page():
    return render_template("shorts.html")


@app.route("/api/analyze-short", methods=["POST"])
def analyze_short_route():
    data = request.get_json() or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Please provide a YouTube Shorts URL."}), 400

    try:
        result = analyze_short(url)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Failed to analyze video: {e}"}), 500


@app.route("/api/search", methods=["POST"])
def search():
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        return jsonify({
            "error": "YouTube API key not configured. Please add YOUTUBE_API_KEY to your .env file."
        }), 400

    data = request.get_json() or {}
    query = (data.get("query") or "roblox rant").strip()
    sort = (data.get("sort") or "subscribers").strip()

    try:
        channels = find_roblox_rant_channels(query, sort, api_key)
        return jsonify({"channels": channels})
    except Exception as e:
        msg = str(e)
        if "quotaExceeded" in msg or "403" in msg:
            return jsonify({"error": "YouTube API quota exceeded or API key invalid. Check your key and quota."}), 429
        if "400" in msg:
            return jsonify({"error": f"Bad request to YouTube API: {msg}"}), 400
        return jsonify({"error": f"API error: {msg}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
