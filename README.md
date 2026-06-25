# Smart Parking Slot Occupancy Detection & Shortest-Path Navigation

A system for parking slot occupancy detection and shortest-path navigation using **direct image analysis** (edge detection, texture analysis, color variance) on overhead parking lot camera feeds, with optional **CNN classifier** trained on the PKLot dataset.

## Architecture

```
Camera Frame → [Stabilizer] → Crop each slot polygon → Classify (CV / CNN / Hybrid) → Occupied/Vacant
                                                                                           ↓
                                                                               Dijkstra shortest path
                                                                                           ↓
                                                                                Navigate to nearest
                                                                                  vacant slot
```

### Detection Approaches

The system supports **three classification backends**:

#### 1. Classical CV Features (Default — No GPU Required)

- **Edge Density**: Occupied slots contain vehicles with many edges (body lines, windows, wheels). Empty slots have few edges (just pavement). Computed using Canny edge detection.
- **Color Variance**: Cars have higher color variance (different paint colors, shadows). Empty pavement is more uniform in color.
- **Texture Energy**: Laplacian variance measures texture complexity — vehicles have complex textures.

These features are combined with tunable thresholds to classify each slot.

#### 2. CNN Classifier (Trained on PKLot)

A lightweight CNN (~550K parameters) trained on **PKLotSegmented** data:
- 3 conv blocks (Conv2D → BatchNorm → ReLU → MaxPool) + FC head
- Input: 64×64 cropped slot image
- Output: binary classification (occupied/empty)
- Trained across multiple weather conditions (Sunny, Cloudy, Rainy) and parking lots (PUC, UFPR04, UFPR05)

#### 3. Hybrid Mode

Uses CNN as the primary classifier with classical CV as fallback:
- CNN predictions with confidence ≥ 0.7 are accepted
- Low-confidence predictions fall back to classical CV features
- Best of both worlds: CNN generalization + CV robustness

### Video Stabilization

Optional stabilization module to handle camera shake/vibration:
- **ECC alignment**: Sub-pixel accurate affine/euclidean transform (best for small jitter)
- **Feature-based alignment**: ORB keypoints + homography (for larger shifts)
- **Hybrid**: Tries ECC first, falls back to feature matching
- **Temporal smoothing**: Rolling average of transforms to avoid jitter

### Navigation

Uses **Dijkstra's algorithm** on a parking lot walkway graph to find the nearest vacant slot from the user's position. Supports **click-to-navigate** — click anywhere on the video feed, image, or frame to set your starting position and instantly get the shortest route to the nearest vacant slot.

## Project Structure

```
CS117/
├── config/
│   └── parking_lot.json     # Parking lot config (slots, graph, thresholds)
├── dataset/
│   ├── PKLot/               # PKLot dataset
│   │   ├── PKLot/           # Full scene images + XML annotations
│   │   │   ├── PUCPR/       # 3 lots × 3 weather conditions
│   │   │   ├── UFPR04/
│   │   │   └── UFPR05/
│   │   └── PKLotSegmented/  # Pre-cropped slot images (Occupied/Empty)
│   │       ├── PUC/
│   │       ├── UFPR04/
│   │       └── UFPR05/
│   ├── demo_video.mp4       # Demo video
│   ├── test.mp4             # Test video
│   └── ground_truth.json    # Ground truth labels for evaluation
├── models/
│   └── slot_classifier.pth  # Trained CNN weights (after training)
├── src/
│   ├── __init__.py
│   ├── slot_analyzer.py     # Classical CV per-slot image analysis
│   ├── cnn_classifier.py    # CNN-based slot classifier (PyTorch)
│   ├── stabilizer.py        # Video frame stabilization module
│   ├── pathfinder.py        # Dijkstra shortest-path navigation
│   └── pipeline.py          # End-to-end processing pipeline
├── web/
│   ├── app.py               # Flask web application
│   ├── templates/           # HTML templates
│   └── static/              # CSS + JS
├── evaluate.py              # Evaluation script (M1-M4 metrics)
├── prepare_data.py          # PKLot data preparation
├── train_cnn.py             # CNN training script
├── requirements.txt         # Python dependencies
├── srs.md                   # Software Requirements Specification
└── README.md                # This file
```

## PKLot Dataset

The [PKLot dataset](https://web.inf.ufpr.br/vri/databases/parking-lot-database/) is used for both **training** and **evaluation**:

### Full Scene Images (`PKLot/PKLot/`)
- **12,417 images** with XML annotations (per-slot occupancy labels)
- 3 parking lots: PUCPR, UFPR04, UFPR05
- 3 weather conditions: Sunny, Cloudy, Rainy
- Used for: demo video generation, ground truth, full-pipeline evaluation

### Segmented Slot Images (`PKLot/PKLotSegmented/`)
- **695,851 pre-cropped slot images** organized as `Occupied/` and `Empty/`
- Used for: training the CNN classifier
- Distribution:

| Lot    | Sunny   | Cloudy  | Rainy  | Total   |
|--------|---------|---------|--------|---------|
| PUC    | 208,387 | 132,780 | 83,056 | 424,223 |
| UFPR04 | 58,500  | 39,385  | 7,958  | 105,843 |
| UFPR05 | 99,890  | 56,966  | 8,929  | 165,785 |

PKLot is especially valuable because it contains **multiple weather conditions**, **different lighting**, and **many camera viewpoints**, making models trained on it generalize much better than handcrafted CV pipelines.

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

For CNN training/inference, also install PyTorch:
```bash
./venv/bin/python -m pip install torch torchvision
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

### 4. Train CNN Classifier (Optional)

```bash
# Train on all PKLot lots and weather conditions
./venv/bin/python train_cnn.py --pklot-root dataset/PKLot/PKLotSegmented

# Train on specific lot/weather
./venv/bin/python train_cnn.py --pklot-root dataset/PKLot/PKLotSegmented \
    --lots PUC --weathers Sunny Cloudy

# Quick test run (small sample)
./venv/bin/python train_cnn.py --pklot-root dataset/PKLot/PKLotSegmented \
    --max-per-class 500 --epochs 5

# Train with GPU
./venv/bin/python train_cnn.py --pklot-root dataset/PKLot/PKLotSegmented \
    --device cuda --batch-size 128
```

The trained model is saved to `models/slot_classifier.pth`.

### 5. Run Web Application

```bash
./venv/bin/python web/app.py
# Visit http://localhost:5005
```

### 6. Set Starting Position

Once the web interface is running, you can set your starting position by **clicking directly on the video feed / frame / image**:

1. Open the web UI at `http://localhost:5005`
2. Click anywhere on the **video feed** to set your current position
3. A 📍 marker will appear on the video where you clicked
4. The system will immediately calculate the shortest route from that point to the nearest vacant slot
5. The navigation panel on the right will update with the route and distance

You can also select a predefined starting node (Entrance, Waypoint) from the dropdown, but clicking on the video gives you full freedom to choose any position.

### 7. Run Evaluation

```bash
# Basic evaluation (classical CV)
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
  - `cnn_model_path` (optional) — path to trained CNN weights
  - `cnn_confidence_threshold` (default: 0.6) — CNN confidence cutoff

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

## Limitations & Future Work

### Current Limitations

> **Camera Stability Requirement**: Currently, the application performs well only when the surveillance camera is **fixed and stable**. Camera vibration or viewpoint shifts significantly reduce detection accuracy. Although a video stabilization module is included (`src/stabilizer.py`), it handles only small jitter — large camera movements or viewpoint changes will still degrade performance.

> **Fixed Slot Coordinates**: Parking slot polygons are defined using fixed pixel coordinates that are configured once during setup. If the camera shifts position, all slot definitions become invalid and must be reconfigured.

> **Weather Sensitivity (Classical CV)**: The classical CV pipeline's handcrafted thresholds may need re-tuning across different weather and lighting conditions. The CNN classifier addresses this by learning weather-invariant features from PKLot.

### Improvement Roadmap

1. **CNN Fine-Tuning on PKLot** ✅ (implemented)
   - Train a lightweight CNN on PKLotSegmented data
   - Generalizes across weather/lighting conditions
   - Supports hybrid mode with classical CV fallback

2. **Video Stabilization** ✅ (implemented)
   - ECC alignment for sub-pixel jitter correction
   - Feature-based alignment for larger shifts
   - Temporal smoothing across frames

3. **Future: Adaptive Slot Mapping**
   - Feature matching / homography alignment to dynamically update slot polygons
   - Track parking slots relative to scene features instead of absolute pixel coordinates
   - Would allow the system to handle camera repositioning without manual reconfiguration

4. **Future: Deep Learning Detection Pipeline**
   - YOLOv8 / YOLO-NAS for vehicle detection
   - DeepSORT or ByteTrack for multi-object tracking
   - Slot occupancy classifier on cropped regions
   - Would enable detection of irregular parking, multi-vehicle scenarios

5. **Future: Temporal Tracking**
   - Object tracking across frames for smooth status transitions
   - Reduce false positives from transient occlusions
   - Handle vehicles in transit (entering/leaving slots)

## Requirements

- Python 3.10 (via local venv)
- OpenCV
- Flask + Flask-SocketIO
- NumPy
- Shapely
- **Optional**: PyTorch (for CNN classifier training/inference)
- **No GPU required** for classical CV mode — runs on CPU
