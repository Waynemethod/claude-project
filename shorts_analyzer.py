"""Download a YouTube Short and analyze its transcript + visual/audio pacing."""

import os
import tempfile

import cv2
import numpy as np

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")

_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
    return _whisper_model


def download_short(url: str, dest_dir: str) -> str:
    """Download a YouTube video to dest_dir and return the local file path."""
    import yt_dlp

    out_template = os.path.join(dest_dir, "video.%(ext)s")
    ydl_opts = {
        "format": "mp4/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
        "outtmpl": out_template,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    for fname in os.listdir(dest_dir):
        if fname.startswith("video."):
            return os.path.join(dest_dir, fname)
    raise RuntimeError("Download failed: no output file produced")


def transcribe(video_path: str) -> dict:
    """Run Whisper speech-to-text and return text + timestamped segments."""
    model = _get_whisper_model()
    result = model.transcribe(video_path, verbose=False)
    segments = [
        {
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip(),
        }
        for seg in result.get("segments", [])
    ]
    return {"text": result.get("text", "").strip(), "segments": segments}


def analyze_visual_pacing(video_path: str, sample_fps: float = 10.0) -> dict:
    """Detect scene cuts and motion spikes by sampling frames at sample_fps."""
    cap = cv2.VideoCapture(video_path)
    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / native_fps if native_fps else 0.0

    step = max(1, round(native_fps / sample_fps))

    cuts = []
    motion = []

    prev_gray = None
    prev_small = None
    frame_idx = 0

    diffs = []
    flow_mags = []
    timestamps = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % step != 0:
            frame_idx += 1
            continue

        t = frame_idx / native_fps
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (64, 64))

        if prev_gray is not None:
            hist_a = cv2.calcHist([prev_gray], [0], None, [64], [0, 256])
            hist_b = cv2.calcHist([gray], [0], None, [64], [0, 256])
            cv2.normalize(hist_a, hist_a)
            cv2.normalize(hist_b, hist_b)
            correl = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
            diff_score = max(0.0, 1.0 - correl)
            diffs.append(diff_score)

            flow = cv2.calcOpticalFlowFarneback(
                prev_small, small, None, 0.5, 2, 15, 3, 5, 1.2, 0
            )
            mag = float(np.mean(np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)))
            flow_mags.append(mag)
            timestamps.append(round(t, 2))

        prev_gray = gray
        prev_small = small
        frame_idx += 1

    cap.release()

    if diffs:
        diffs_arr = np.array(diffs)
        cut_threshold = float(np.mean(diffs_arr) + 2.0 * np.std(diffs_arr))
        cut_threshold = max(cut_threshold, 0.25)
        for ts, score in zip(timestamps, diffs):
            if score >= cut_threshold:
                cuts.append({"time": ts, "intensity": round(float(score), 3)})

    if flow_mags:
        flow_arr = np.array(flow_mags)
        motion_threshold = float(np.mean(flow_arr) + 1.5 * np.std(flow_arr))
        for ts, mag in zip(timestamps, flow_mags):
            if mag >= motion_threshold and mag > 0.5:
                motion.append({"time": ts, "intensity": round(float(mag), 3)})

    return {
        "duration": round(duration, 2),
        "cuts": cuts,
        "motion_spikes": motion,
    }


def analyze_audio_pacing(video_path: str) -> dict:
    """Detect sudden audio energy spikes (RMS) over time."""
    import librosa

    y, sr = librosa.load(video_path, sr=None, mono=True)
    if y.size == 0:
        return {"spikes": []}

    hop_length = 512
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)

    if len(rms) < 2:
        return {"spikes": []}

    delta = np.diff(rms, prepend=rms[0])
    threshold = float(np.mean(delta) + 2.0 * np.std(delta))
    threshold = max(threshold, 0.02)

    spikes = []
    for t, d in zip(times, delta):
        if d >= threshold:
            spikes.append({"time": round(float(t), 2), "intensity": round(float(d), 4)})

    return {"spikes": spikes}


def analyze_short(url: str) -> dict:
    """Full pipeline: download, transcribe, analyze visual + audio pacing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = download_short(url, tmp_dir)

        transcript = transcribe(video_path)
        visual = analyze_visual_pacing(video_path)
        audio = analyze_audio_pacing(video_path)

        events = []
        for c in visual["cuts"]:
            events.append({"time": c["time"], "type": "cut", "intensity": c["intensity"]})
        for m in visual["motion_spikes"]:
            events.append({"time": m["time"], "type": "motion", "intensity": m["intensity"]})
        for a in audio["spikes"]:
            events.append({"time": a["time"], "type": "audio", "intensity": a["intensity"]})
        events.sort(key=lambda e: e["time"])

        return {
            "duration": visual["duration"],
            "transcript": transcript,
            "events": events,
        }
