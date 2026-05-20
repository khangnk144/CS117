# Smart Parking Slot Occupancy Detection and Shortest-Path Navigation

# Context description and motivation (no more than 5 sentences)
In indoor parking lots (shopping malls), drivers often spend 5–15 minutes cruising for a vacant space because real-time occupancy information is unavailable. Unnecessary cruising wastes time, increases internal congestion, and degrades the user experience. The proposed system analyzes overhead camera feeds using a YOLOv8 object detection model (running on a CUDA-enabled GPU) to detect vehicles. It computes the Intersection over Area (IoA) between vehicle bounding boxes and pre-defined parking slot polygons to classify the occupancy status of each slot, applying temporal smoothing to prevent flickering. It then uses a shortest-path algorithm (Dijkstra) on a mapped graph to guide the driver to the nearest vacant slot.

# Input
1. **Surveillance camera video**: Pre-recorded video or a video stream (RTSP/USB), minimum resolution 720p (1080p recommended), frame rate ≥ 15 FPS. The camera observes an area of ≤ 20 parking slots. The input video is processed frame by frame.
2. **Parking Lot Map**: A JSON configuration file describing:
   - **Slot list**: Each slot has a unique ID and polygon coordinates on the video frame (manually annotated once by the operator before operation).
   - **Walkway graph (adjacency graph)**: Nodes (slot, turning point, entrance gate) and edges with weights (distance in meters or grid cells).
3. **Current vehicle position**: The user sets their position by clicking directly on the video feed/frame in the web interface (click-to-navigate), which dynamically creates a temporary node on the graph, or by selecting a predefined starting node from a dropdown menu.

# Output
1. **Annotated Video**: The original video stream is overlaid with:
   - Vehicle bounding boxes and YOLOv8 confidence scores.
   - Each parking slot marked with an overlay polygon: **green** = vacant, **red** = occupied.
   - The recommended slot: **highlighted in yellow**.
2. **Continuously updated 2D parking-lot diagram**: Displays vacant/occupied status for all slots and the suggested route.
3. **Shortest-path information**: A list of nodes on the graph from the current position to the nearest vacant slot, along with the estimated total distance and a visual marker on the video feed.

# Requirements (Functional requirements – measurable)
| ID | Requirement | Acceptance threshold |
|---|---|---|
| R1 | Accurately classify the status of each parking slot (vacant / occupied). Pipeline: YOLOv8 detection → compute IoA (Intersection over Area) with slot polygons → apply temporal smoothing → output binary status. | Slot-level F1-score ≥ 0.90 on the test set |
| R2 | Identify the vacant slot with the shortest walkway distance from the user’s position (based on Dijkstra on the graph). When multiple slots share the same shortest distance, choose the slot with the smallest ID (deterministic tie-breaking). | Correct selection rate ≥ 95% compared to ground truth (manual Dijkstra with the same tie-breaking rule) |
| R3 | End-to-end processing time: from receiving 1 frame → YOLOv8 inference → compute IoA → find path → return result. Measured on a CUDA-enabled GPU. | ≤ 100 ms per frame (average over 50 trials) |
| R4 | Update slot status when a vehicle enters or leaves a slot | Average latency ≤ 3 seconds from the moment the vehicle starts occupying/leaving the slot |
| R5 | Display results on a web interface: annotated video, 2D diagram, suggested route, click-to-navigate functionality. | Pass all test cases in the functional test suite (see M5) |

# Constraints
1. **Camera**: Use 1 fixed camera for the demo, resolution ≥ 720p (1080p recommended), mounted high (≥ 3m) looking down. The camera handles ≤ 20 slots. For the demo, use pre-recorded video.
2. **Detection Model**: The system uses **YOLOv8** (e.g., `yolov8n-visdrone.pt` or `yolov8m.pt`) for vehicle detection. Occupancy is determined geometrically (IoA > 0.35 or vehicle's bottom center inside the slot polygon).
3. **Processing hardware**: A **CUDA-enabled GPU** is required to run the YOLOv8 model at real-time speeds. The system does not fall back to CPU-only execution gracefully for real-time video streaming.
4. **Python Environment**: The project relies on a local virtual environment (`./venv/bin/python`) with PyTorch (CUDA) installed.
5. **Demo video source**: Custom videos or PKLot dataset camera sequences can be used as **demo video input** and **evaluation ground truth**.
6. **Demo parking lot size**: Maximum 20 parking slots, single level, 1 camera.

# Assumptions
1. Each parking slot has clearly marked lines and is large enough for one standard passenger car.
2. The parked vehicle lies completely within the defined slot polygon (no partial parking into another slot).
3. The YOLOv8 model is capable of detecting vehicles reliably from the camera's overhead perspective.
4. The parking lot map (slot polygons, walkway graph) is manually set up once before system operation and does not change at runtime.
5. The “nearest” criterion is defined purely as shortest graph distance (shortest path on the graph), without considering real-world factors (ease of turning, proximity to exit, etc.).

# Scope
**In-scope:**
- Use YOLOv8 object detection to identify vehicles in the frame.
- Calculate Intersection over Area (IoA) between vehicle bounding boxes and slot polygons.
- Apply temporal smoothing (majority voting over consecutive frames) to reduce flickering and stabilize occupancy status.
- Find the shortest path to the nearest vacant slot using Dijkstra's algorithm.
- Dynamically create temporary routing nodes when the user clicks on the video feed.
- Display results on a web interface: annotated video, 2D diagram, route information, and click-to-navigate.

**Out-of-scope:**
- Classical CV (edge density, color variance) or lightweight cropped-image CNN classifiers.
- License plate recognition.
- Payment / reservation system.
- Multi-level parking lots or simultaneous multi-camera (>1 camera) tracking.
- Detailed turn-by-turn navigation for the driver.

# Evaluation Metrics

## M1 — Parking slot status classification accuracy (slot-level)
- **Requirement mapping**: R1
- **Metric**: Precision, Recall, F1-score at the slot level (per-slot binary classification: vacant vs. occupied)
- **Threshold**: F1-score ≥ 0.90
- **Evaluation pipeline**:
  1. **Ground truth**: Each test frame is manually labeled for each slot: `occupied` or `vacant`.
  2. **System prediction**: The system runs YOLOv8 to get bounding boxes, calculates IoA with slot polygons, and applies temporal smoothing to output a status.
  3. **Comparison**: For each slot in each frame, compare predicted label vs. ground truth label.
  4. **Calculation**: Confusion matrix (TP, TN, FP, FN) → Precision, Recall, F1-score.

## M2 — Nearest slot selection accuracy
- **Requirement mapping**: R2
- **Metric**: Accuracy (correct selection rate)
- **Threshold**: ≥ 95%
- **Formula**: `Accuracy = Number of times the system selects correctly / Total number of trials`
- **Definition of “correct”**: The system’s chosen slot S is correct if S belongs to the set of slots that have the minimum shortest-path distance (computed by Dijkstra).
- **Measurement method**:
  - Prepare ≥ 30 test scenarios with different starting positions (using click-to-navigate) and parking lot occupancy states.
  - For each scenario, compute the shortest path manually using Dijkstra on the same graph as ground truth.
  - Compare the system-selected slot with the ground truth set of slots.

## M3 — Response time
- **Requirement mapping**: R3
- **Metric**: Average Response Time
- **Threshold**: ≤ 2 seconds (with GPU, typical performance is < 100ms)
- **Formula**: `T_avg = (1/N) × Σ (T_output_i − T_input_i)` with N ≥ 50
- **Measurement method**:
  - Record timestamp when the system receives an input frame.
  - Record timestamp when the system returns the complete result (annotated frame + route).
  - Compute the average over ≥ 50 trials with the GPU configuration.

## M4 — Status update latency
- **Requirement mapping**: R4
- **Metric**: Average Update Latency
- **Threshold**: ≤ 3 seconds
- **Formula**: `L_avg = (1/N) × Σ (T_system_update_i − T_event_i)` with N ≥ 20
- **Measurement method**:
  - Use a test video with timestamp markers indicating the moment a vehicle begins to enter/leave a slot.
  - Compare with the timestamp when the system updates the corresponding slot status (accounting for the 3-frame temporal smoothing delay).

## M5 — Functional testing of the web interface
- **Requirement mapping**: R5
- **Metric**: Test case pass rate
- **Threshold**: 100% test cases PASS
- **Test case table**:

| TC ID | Test case description | PASS condition |
|---|---|---|
| TC5.1 | Annotated video displays in the browser | Video renders continuously, slot polygons show correct colors (green/red), vehicle bounding boxes are visible |
| TC5.2 | 2D diagram updates when slot status changes | Status on diagram matches annotated video within 5s |
| TC5.3 | User sets starting position via click-to-navigate | Route is displayed on the 2D diagram within 5s after click |
| TC5.4 | Works on the current Chrome version | No JavaScript errors blocking the UI, layout is not broken |
| TC5.5 | Displays number of vacant slots / total slots | The figure matches the actual status in the video |

# Known Limitations

1. **Fixed Slot Coordinates**: Parking slot polygons use fixed pixel coordinates configured once during setup. If the camera shifts position significantly, all slot definitions must be reconfigured manually.
2. **YOLO Perspective Issues**: YOLOv8 is typically trained on forward-facing imagery. If the camera angle is extremely top-down or distorted, YOLO may fail to detect vehicles unless fine-tuned on drone/overhead datasets (e.g., VisDrone).
3. **GPU Dependency**: The system strictly requires a CUDA-enabled GPU for real-time inference.

# Future Work

1. **Adaptive Slot Mapping**: Use feature matching / homography alignment to dynamically update slot polygons when the camera shifts.
2. **DeepSORT Tracking**: Add DeepSORT or ByteTrack to the YOLOv8 detections to track individual vehicles across the parking lot instead of just checking static intersections.
3. **Overhead Fine-tuning**: Fine-tune the YOLOv8 model specifically on the parking lot's overhead camera angles to improve detection confidence.