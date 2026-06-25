"""
Auto-setup script: Extracts a frame from the video and opens the
web annotator for manual slot drawing.

Note: Automatic slot detection from a single frame is unreliable.
Use the web-based annotator (http://localhost:5005/annotate) to
draw slot polygons manually on your video frame.
"""
import cv2
import json
import os
import webbrowser

# Read first frame from video
video_path = "dataset/test.mp4"
cap = cv2.VideoCapture(video_path)
ret, frame = cap.read()
cap.release()

if not ret:
    print("Error: Cannot read video!")
    exit(1)

h, w = frame.shape[:2]
print(f"Video resolution: {w}x{h}")

# Save a reference frame for the annotator
cv2.imwrite("frame100.jpg", frame)
print("Saved reference frame to frame100.jpg")

# Create a minimal config that the web annotator can work with
if not os.path.exists("config/parking_lot.json"):
    config = {
        "parking_lot": "CustomLot",
        "weather": "Unknown",
        "video_path": video_path,
        "image_size": {"width": w, "height": h},
        "slots": [],
        "graph": {"nodes": [{"id": "E1", "type": "entrance", "x": w // 2, "y": 30}], "edges": []},
        "model": {
            "edge_threshold": 0.08,
            "variance_threshold": 25.0,
            "texture_threshold": 50.0,
            "combined_score_threshold": 0.45,
        },
    }
    os.makedirs("config", exist_ok=True)
    with open("config/parking_lot.json", "w") as f:
        json.dump(config, f, indent=2)
    print("Created initial config/parking_lot.json")

print("\nTo annotate parking slots:")
print("  1. Run: python web/app.py")
print("  2. Visit: http://localhost:5005/annotate")
print("  3. Draw slot polygons on the video frame")
print("  4. Click 'Save & Generate Graph'")
