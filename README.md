# Smart Parking Slot Occupancy Detection & Shortest-Path Navigation

A system for parking slot occupancy detection and shortest-path navigation using **direct image analysis** (edge detection, texture analysis, color variance) on overhead parking lot camera feeds.

## Architecture

```
Camera Frame → Crop each slot polygon → Analyze features (edges, texture, color) → Occupied/Vacant
                                                                                         ↓
                                                                             Dijkstra shortest path
                                                                                         ↓
                                                                              Navigate to nearest
                                                                                vacant slot
```

### Detection Approach

Instead of using an object detector (like YOLO), this system uses a **direct per-slot image analysis** approach:

1. **Edge Density**: Occupied slots contain vehicles with many edges (body lines, windows, wheels). Empty slots have few edges (just pavement). Computed using Canny edge detection.
2. **Color Variance**: Cars have higher color variance (different paint colors, shadows). Empty pavement is more uniform in color.
3. **Texture Energy**: Laplacian variance measures texture complexity — vehicles have complex textures.

These features are combined with tunable thresholds to classify each slot as occupied or vacant.

**Why not YOLO?**
- YOLO was trained on ground-level car images (COCO dataset), not overhead/bird's-eye views
- Cars at 50-100px in overhead views don't match YOLO's training distribution
- Indirect approach (detect car → match to slot) adds unnecessary complexity
- Direct slot analysis is faster, simpler, and more accurate for fixed-camera parking

### Navigation

Uses **Dijkstra's algorithm** on a parking lot walkway graph to find the nearest vacant slot from the user's position. Supports **click-to-navigate** — click anywhere on the video feed, image, or frame to set your starting position and instantly get the shortest route to the nearest vacant slot.

## Project Structure

```
CS117/
├── config/
│   └── parking_lot.json     # Parking lot config (slots, graph, thresholds)
├── dataset/
│   ├── PKLot/               # PKLot dataset (optional)
│   ├── demo_video.mp4       # Demo video
│   ├── test.mp4             # Test video
│   └── ground_truth.json    # Ground truth labels for evaluation
├── src/
│   ├── __init__.py
│   ├── slot_analyzer.py     # Core: per-slot image analysis classifier
│   ├── pathfinder.py        # Dijkstra shortest-path navigation
│   └── pipeline.py          # End-to-end processing pipeline
├── web/
│   ├── app.py               # Flask web application
│   ├── templates/            # HTML templates
│   └── static/               # CSS + JS
├── evaluate.py              # Evaluation script (M1-M4 metrics)
├── prepare_data.py          # PKLot data preparation
├── requirements.txt         # Python dependencies
├── srs.md                   # Software Requirements Specification
└── README.md                # This file
```

## Setup

### 1. Python Environment

The project uses a local virtual environment located at `./venv`. **Do not use `conda activate`** — instead, run all commands by prefixing with `./venv/bin/python`:

```bash
cd /AIClub_NAS/core_baotg/khang/CS117
./venv/bin/python --version   # Verify the environment works
```

> **Note:** All commands below use `./venv/bin/python` to invoke the correct interpreter. If you see `ModuleNotFoundError`, make sure you are running from the `CS117/` directory.

### 2. Install Dependencies

```bash
./venv/bin/python -m pip install -r requirements.txt
```

### 3. Configure Parking Lot

**Option A: Use the web annotator (recommended)**
```bash
./venv/bin/python web/app.py
# Visit http://localhost:5005/annotate
# Load your video → draw slot polygons → save config
```

**Option B: Use PKLot dataset**
```bash
./venv/bin/python prepare_data.py --pklot-root dataset/PKLot --lot PUCPR --weather Sunny
```

### 4. Run Web Application

```bash
./venv/bin/python web/app.py
# Visit http://localhost:5005
```

### 5. Set Starting Position

Once the web interface is running, you can set your starting position by **clicking directly on the video feed / frame / image**:

1. Open the web UI at `http://localhost:5005`
2. Click anywhere on the **video feed** to set your current position
3. A 📍 marker will appear on the video where you clicked
4. The system will immediately calculate the shortest route from that point to the nearest vacant slot
5. The navigation panel on the right will update with the route and distance

You can also select a predefined starting node (Entrance, Waypoint) from the dropdown, but clicking on the video gives you full freedom to choose any position.

### 6. Run Evaluation

```bash
# Basic evaluation
./venv/bin/python evaluate.py --config config/parking_lot.json --ground-truth dataset/ground_truth.json

# With calibration (uses first 5 GT frames for per-slot baselines)
./venv/bin/python evaluate.py --config config/parking_lot.json --ground-truth dataset/ground_truth.json --calibrate
```

## Configuration

The `config/parking_lot.json` file contains:

- **slots**: List of parking slot definitions with polygon coordinates
- **graph**: Walkway graph (nodes + edges) for Dijkstra navigation
- **model**: Analysis thresholds:
  - `edge_threshold` (default: 0.08) — minimum edge pixel ratio
  - `variance_threshold` (default: 25.0) — minimum color std deviation
  - `texture_threshold` (default: 50.0) — minimum Laplacian variance
  - `combined_score_threshold` (default: 0.45) — occupancy decision threshold

## Evaluation Metrics

| Metric | Description | Threshold |
|--------|-------------|-----------|
| M1 | Slot classification F1-score | ≥ 0.90 |
| M2 | Navigation accuracy | ≥ 95% |
| M3 | Response time per frame | ≤ 2 seconds |
| M4 | Status update latency | ≤ 3 seconds |

## Web Interface Features

- **Live Detection Feed**: Annotated video with slot status overlays
- **Parking Map**: 2D diagram showing all slot statuses
- **Click-to-Navigate**: Click anywhere on the video/frame/image to set your starting position — the system shows the shortest route to the nearest vacant slot with a visible marker
- **Start Node Dropdown**: Alternatively, select a predefined entrance or waypoint
- **Video Selection**: Switch between multiple video sources
- **Setup Mode**: Draw slot polygons on any video frame

## Requirements

- Python 3.10 (via local venv)
- OpenCV
- Flask + Flask-SocketIO
- NumPy
- Shapely
- **No GPU required** — runs on CPU
