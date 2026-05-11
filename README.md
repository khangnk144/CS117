# Smart Parking Slot Occupancy Detection & Shortest-Path Navigation

CS117 project using **YOLOv8s** (COCO pretrained) for vehicle detection and **Dijkstra's algorithm** for shortest-path navigation to the nearest vacant parking slot.

## Architecture

```
Frame → YOLOv8s (detect vehicles) → IoU with slot polygons → Slot status
                                                              ↓
                                            Dijkstra → Nearest vacant slot
                                                              ↓
                                             Web UI (annotated video + 2D map)
```

## Project Structure

```
CS117/
├── config/                    # Parking lot configuration (auto-generated)
│   └── parking_lot.json       # Slot polygons + walkway graph
├── dataset/                   # PKLot dataset (demo video source + ground truth)
│   └── PKLot/                 # Extracted PKLot dataset
├── src/                       # Core modules
│   ├── detector.py            # YOLOv8 vehicle detection
│   ├── slot_classifier.py     # IoU-based slot occupancy classification
│   ├── pathfinder.py          # Dijkstra shortest-path algorithm
│   └── pipeline.py            # End-to-end processing pipeline
├── web/                       # Web application
│   ├── app.py                 # Flask + SocketIO server
│   ├── templates/index.html   # Main web page
│   └── static/                # CSS + JS
├── prepare_data.py            # Parse PKLot → config + demo video + ground truth
├── evaluate.py                # Evaluation metrics (M1–M4)
├── requirements.txt           # Python dependencies
└── srs.md                     # Software Requirements Specification
```

## Quick Start

### 1. Setup Environment

```bash
# Create conda env (already done if following setup)
conda create -p ./venv python=3.10 -y
uv pip install --python ./venv/bin/python -r requirements.txt
```

### 2. Download & Extract PKLot Dataset

```bash
# Download (4.6GB)
wget -c http://www.inf.ufpr.br/vri/databases/PKLot.tar.gz -O dataset/PKLot.tar.gz
tar -xzf dataset/PKLot.tar.gz -C dataset/
```

### 3. Prepare Data

```bash
./venv/bin/python prepare_data.py --pklot-root dataset/PKLot --lot PUCPR --weather Sunny
```

This generates:
- `config/parking_lot.json` — slot polygons + walkway graph
- `dataset/demo_video.mp4` — stitched demo video
- `dataset/ground_truth.json` — per-frame slot labels for evaluation

### 4. Run Web Demo

**Start the Web Server:**
```bash
./venv/bin/python web/app.py
```

*(To stop the server at any time, press `Ctrl+C` in the terminal, or run `pkill -f "python web/app.py"` in a new terminal).*

**Access the Web Interface:**
If you are running this on a remote server, you must use SSH Port Forwarding to access the web app:
```bash
ssh -L 5005:localhost:5005 your_username@your_server_ip
```

Then open your local browser:

1. **Custom Parking Lot Setup:** Go to `http://localhost:5005/annotate`
   - Enter your video path (e.g., `dataset/test.mp4`)
   - Manually draw parking slots on the image
   - Click "Save & Generate Graph"
2. **Main Dashboard:** Go to `http://localhost:5005/`
   - Click **Play** to start the detection feed
   - Select a **Starting Position** to see the shortest path to the nearest vacant slot

### 5. Run Evaluation

```bash
./venv/bin/python evaluate.py --device cuda
```

## SRS Metrics

| Metric | Description | Threshold |
|--------|-------------|-----------|
| M1 | Slot-level F1-score | ≥ 0.90 |
| M2 | Navigation accuracy | ≥ 95% |
| M3 | Avg response time | ≤ 2s |
| M4 | Status update latency | ≤ 3s |
| M5 | Web UI test cases | 5/5 PASS |

## Dataset

Uses [PKLot dataset](https://web.inf.ufpr.br/vri/databases/parking-lot-database/) as demo video source and evaluation ground truth. Citation:

> Almeida, P., Oliveira, L. S., Silva Jr, E., Britto Jr, A., Koerich, A.,
> PKLot – A robust dataset for parking lot classification,
> Expert Systems with Applications, 42(11):4937-4949, 2015.
