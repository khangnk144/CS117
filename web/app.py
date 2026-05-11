"""
Flask web application for the Smart Parking System.
Serves annotated video, 2D parking map, and navigation info.
Click-to-set start position on the video feed.

Updated for direct slot image analysis (no YOLO required).
"""

import os
import sys
import json
import time
import cv2
import base64
import numpy as np
import threading
from flask import Flask, render_template, jsonify, request, Response, redirect
from flask_socketio import SocketIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pipeline import ParkingPipeline
from prepare_data import find_pklot_sequences

app = Flask(__name__,
            template_folder="templates",
            static_folder="static")
app.config["SECRET_KEY"] = "parking-secret-key"
app.config["USER_POSITION"] = None
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Global state
pipeline = None
frame_pairs = []
video_cap = None
video_path = None
total_video_frames = 0
current_frame_idx = 0
current_start_node = "E1"
config = None
is_playing = False
video_lock = threading.Lock()


def load_system():
    global pipeline, frame_pairs, config, video_cap, video_path, total_video_frames

    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "parking_lot.json"))
    if not os.path.exists(config_path):
        print(f"WARNING: Config not found at {config_path}")
        print("Please visit /annotate to setup a new parking lot.")
        return False

    with open(config_path) as f:
        config = json.load(f)

    # No GPU needed for direct image analysis
    device = "cpu"
    print(f"Initializing pipeline (direct image analysis, device: {device})")
    pipeline = ParkingPipeline(config, device=device)

    if "video_path" in config and config["video_path"]:
        v_path = config["video_path"]
        if not os.path.isabs(v_path):
            proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            v_path = os.path.join(proj_root, v_path)
        print(f"Attempting to load video from: {v_path}")
        if os.path.exists(v_path):
            video_cap = cv2.VideoCapture(v_path)
            total_video_frames = int(video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_video_frames <= 0:
                total_video_frames = 300
            video_path = v_path
            frame_pairs = []
            print(f"Loaded custom video: {video_path} ({total_video_frames} frames)")
            return True
        else:
            print(f"WARNING: Video file not found at {v_path}")

    pklot_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dataset", "PKLot", "PKLot"))
    lot = config.get("parking_lot", "PUCPR")
    weather = config.get("weather", "Sunny")
    try:
        frame_pairs = find_pklot_sequences(pklot_root, lot, weather, max_images=300)
        print(f"Loaded {len(frame_pairs)} frames for demo from PKLot")
    except Exception as e:
        print(f"Warning: Could not load PKLot frames: {e}")
        frame_pairs = []

    return True


@app.route("/")
def index():
    if pipeline is None:
        return redirect("/annotate")
    return render_template("index.html")

@app.route("/annotate")
def annotate():
    return render_template("annotate.html")

@app.route("/api/extract_frame", methods=["POST"])
def extract_frame():
    data = request.get_json()
    path = data.get("path")
    if not path:
        return jsonify({"error": "Path is required"}), 400
    if not os.path.exists(path):
        proj_root = os.path.join(os.path.dirname(__file__), "..")
        path = os.path.join(proj_root, path)
        if not os.path.exists(path):
            return jsonify({"error": "File not found"}), 404
    if path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
        cap = cv2.VideoCapture(path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 100)
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
        cap.release()
        if not ret:
            return jsonify({"error": "Could not read frame from video"}), 500
    else:
        frame = cv2.imread(path)
        if frame is None:
            return jsonify({"error": "Could not read image"}), 500
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    frame_b64 = base64.b64encode(buffer).decode("utf-8")
    return jsonify({"frame": frame_b64})

@app.route("/api/save_config", methods=["POST"])
def save_config():
    data = request.get_json()
    slots = data.get("slots", [])
    img_size = data.get("image_size", {"width": 1280, "height": 720})
    video_path = data.get("video_path", "")
    w, h = img_size["width"], img_size["height"]

    nodes = [{"id": "E1", "type": "entrance", "x": w // 2, "y": 30}]
    num_waypoints = min(len(slots), 10)
    wp_y = h // 2
    edges = []
    for i in range(num_waypoints):
        wp_x = int(w * (i + 1) / (num_waypoints + 1))
        wp_id = f"W{i + 1}"
        nodes.append({"id": wp_id, "type": "waypoint", "x": wp_x, "y": wp_y})
        if i > 0:
            prev_wp = f"W{i}"
            dist = abs(wp_x - int(w * i / (num_waypoints + 1)))
            edges.append({"from": prev_wp, "to": wp_id, "weight": round(dist * 0.05, 1)})
    if num_waypoints > 0:
        edges.append({"from": "E1", "to": "W1", "weight": round(abs(wp_y - 30) * 0.05, 1)})

    for slot in slots:
        polygon = slot["polygon"]
        cx = int(sum(p[0] for p in polygon) / 4)
        cy = int(sum(p[1] for p in polygon) / 4)
        nodes.append({"id": slot["id"], "type": "slot", "x": cx, "y": cy})
        min_dist = float("inf")
        nearest_wp = "W1"
        for i in range(num_waypoints):
            wp_x = int(w * (i + 1) / (num_waypoints + 1))
            dist = ((cx - wp_x) ** 2 + (cy - wp_y) ** 2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                nearest_wp = f"W{i + 1}"
        edges.append({
            "from": slot["id"], "to": nearest_wp,
            "weight": round(min_dist * 0.05, 1)
        })

    config_data = {
        "parking_lot": "CustomLot",
        "weather": "Unknown",
        "video_path": video_path,
        "image_size": img_size,
        "slots": slots,
        "graph": {"nodes": nodes, "edges": edges},
        "model": {
            "edge_threshold": 0.08,
            "variance_threshold": 25.0,
            "texture_threshold": 50.0,
            "combined_score_threshold": 0.45,
        },
    }
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "parking_lot.json")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)
    load_system()
    return jsonify({"success": True, "message": "Config saved successfully"})

@app.route("/api/list_videos")
def list_videos():
    proj_root = os.path.join(os.path.dirname(__file__), "..")
    dataset_dir = os.path.join(proj_root, "dataset")
    videos = []
    if os.path.exists(dataset_dir):
        for file in os.listdir(dataset_dir):
            if file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                videos.append(os.path.join("dataset", file))
    return jsonify({"videos": videos})

@app.route("/api/set_video", methods=["POST"])
def set_video():
    global video_cap, video_path, total_video_frames, current_frame_idx, is_playing, frame_pairs
    data = request.get_json()
    new_video_path = data.get("video_path")
    if not new_video_path:
        return jsonify({"error": "Video path is required"}), 400
    proj_root = os.path.join(os.path.dirname(__file__), "..")
    full_path = os.path.join(proj_root, new_video_path)
    if not os.path.exists(full_path):
        return jsonify({"error": "Video file not found"}), 404
    is_playing = False
    with video_lock:
        if video_cap is not None:
            video_cap.release()
        video_cap = cv2.VideoCapture(full_path)
        total_video_frames = int(video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_video_frames <= 0:
            total_video_frames = 300
        video_path = full_path
        current_frame_idx = 0
        frame_pairs = []
    config_path = os.path.join(proj_root, "config", "parking_lot.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            cfg = json.load(f)
        cfg["video_path"] = new_video_path
        with open(config_path, "w") as f:
            json.dump(cfg, f, indent=2)
    return jsonify({"success": True, "message": f"Video set to {new_video_path}", "total_frames": total_video_frames})

@app.route("/api/config")
def get_config():
    if config is None:
        return jsonify({"error": "System not initialized"}), 500
    return jsonify({
        "slots": config["slots"],
        "graph": config["graph"],
        "image_size": config.get("image_size", {"width": 1280, "height": 720}),
        "parking_lot": config.get("parking_lot", "Unknown"),
        "weather": config.get("weather", "Unknown"),
        "video_path": config.get("video_path", ""),
    })

@app.route("/api/status")
def get_status():
    return jsonify({
        "initialized": pipeline is not None,
        "total_frames": total_video_frames if video_cap else len(frame_pairs),
        "current_frame": current_frame_idx,
        "start_node": current_start_node,
        "is_playing": is_playing,
    })

@app.route("/api/process_frame", methods=["POST"])
def process_single_frame():
    global current_frame_idx, current_start_node
    if pipeline is None:
        return jsonify({"error": "System not initialized"}), 500
    data = request.get_json(silent=True) or {}
    if "start_node" in data:
        current_start_node = data["start_node"]
    # Lấy vị trí click từ app config
    user_pos = app.config.get("USER_POSITION")
    total_frames_count = 1
    frame = None
    if video_cap is not None:
        with video_lock:
            if "frame_index" in data:
                current_frame_idx = max(0, min(data["frame_index"], total_video_frames - 1))
            video_cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)
            ret, frame = video_cap.read()
        if not ret:
            return jsonify({"error": f"Cannot read frame {current_frame_idx} from video"}), 500
        total_frames_count = total_video_frames
    elif frame_pairs:
        if "frame_index" in data:
            current_frame_idx = max(0, min(data["frame_index"], len(frame_pairs) - 1))
        img_path, _ = frame_pairs[current_frame_idx]
        frame = cv2.imread(img_path)
        if frame is None:
            return jsonify({"error": f"Cannot read frame: {img_path}"}), 500
        total_frames_count = len(frame_pairs)
    else:
        return jsonify({"error": "No video source available"}), 500

    result = pipeline.process_frame(frame, start_node=current_start_node,
                                    user_position=user_pos)
    _, buffer = cv2.imencode(".jpg", result["annotated_frame"],
                             [cv2.IMWRITE_JPEG_QUALITY, 85])
    frame_b64 = base64.b64encode(buffer).decode("utf-8")
    return jsonify({
        "frame_index": current_frame_idx,
        "total_frames": total_frames_count,
        "annotated_frame": frame_b64,
        "slot_statuses": result["slot_statuses"],
        "navigation": result["navigation"],
        "summary": result["summary"],
        "processing_time_ms": result["processing_time_ms"],
    })

@app.route("/api/next_frame", methods=["POST"])
def next_frame():
    global current_frame_idx
    total = total_video_frames if video_cap else len(frame_pairs)
    if total > 0:
        current_frame_idx = (current_frame_idx + 1) % total
    return process_single_frame()

@app.route("/api/set_start", methods=["POST"])
def set_start_node():
    global current_start_node
    data = request.get_json()
    current_start_node = data.get("start_node", "E1")
    return jsonify({"start_node": current_start_node})

@app.route("/api/set_user_position", methods=["POST"])
def set_user_position():
    data = request.get_json()
    x = data.get("x")
    y = data.get("y")
    if x is None or y is None:
        return jsonify({"error": "x and y required"}), 400
    app.config["USER_POSITION"] = (x, y)
    print(f"User clicked at ({x}, {y})")
    return jsonify({"status": "ok", "message": f"User position set to ({x},{y})"})

@app.route("/api/calibrate", methods=["POST"])
def calibrate_analyzer():
    """Calibrate the analyzer using the current frame as empty reference."""
    if pipeline is None:
        return jsonify({"error": "System not initialized"}), 500

    frame = None
    if video_cap is not None:
        with video_lock:
            video_cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)
            ret, frame = video_cap.read()
        if not ret:
            return jsonify({"error": "Cannot read current frame"}), 500
    elif frame_pairs:
        img_path, _ = frame_pairs[current_frame_idx]
        frame = cv2.imread(img_path)
    else:
        return jsonify({"error": "No video source available"}), 500

    if frame is None:
        return jsonify({"error": "Cannot read frame"}), 500

    pipeline.analyzer.auto_calibrate(frame)
    return jsonify({"success": True, "message": "Calibrated using current frame as empty baseline"})

@socketio.on("connect")
def handle_connect():
    print("Client connected")

@socketio.on("start_stream")
def handle_start_stream():
    global is_playing, current_frame_idx
    is_playing = True
    while is_playing:
        frame = None
        total_frames_count = 1
        if video_cap is not None:
            with video_lock:
                video_cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)
                ret, frame = video_cap.read()
            if not ret:
                current_frame_idx = 0
                continue
            total_frames_count = total_video_frames
        elif frame_pairs:
            img_path, _ = frame_pairs[current_frame_idx]
            frame = cv2.imread(img_path)
            if frame is None:
                current_frame_idx = (current_frame_idx + 1) % len(frame_pairs)
                continue
            total_frames_count = len(frame_pairs)
        else:
            break

        user_pos = app.config.get("USER_POSITION")
        result = pipeline.process_frame(frame, start_node=current_start_node,
                                        user_position=user_pos)
        _, buffer = cv2.imencode(".jpg", result["annotated_frame"],
                                  [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_b64 = base64.b64encode(buffer).decode("utf-8")
        socketio.emit("frame_update", {
            "frame_index": current_frame_idx,
            "total_frames": total_frames_count,
            "annotated_frame": frame_b64,
            "slot_statuses": result["slot_statuses"],
            "navigation": result["navigation"],
            "summary": result["summary"],
            "processing_time_ms": result["processing_time_ms"],
        })
        if total_frames_count > 0:
            current_frame_idx = (current_frame_idx + 1) % total_frames_count
        socketio.sleep(0.5)

@socketio.on("stop_stream")
def handle_stop_stream():
    global is_playing
    is_playing = False

if __name__ == "__main__":
    print("=" * 60)
    print("Smart Parking System — Web Interface")
    print("(Direct Image Analysis — No YOLO Required)")
    print("=" * 60)
    if not load_system():
        print("Started in Setup Mode. Visit http://localhost:5005/annotate to configure.")
    port = int(os.environ.get("PORT", 5005))
    print(f"\nStarting server on http://0.0.0.0:{port}")
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)