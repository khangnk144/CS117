# Smart Parking Slot Occupancy Detection and Shortest-Path Navigation Using YOLOv8 — A system for parking slot occupancy detection and shortest‑path navigation using YOLOv8

# Context description and motivation (no more than 5 sentences)
In indoor parking lots (shopping malls), drivers often spend 5–15 minutes cruising for a vacant space because real‑time occupancy information is unavailable. Unnecessary cruising wastes time, increases internal congestion, and degrades the user experience. The proposed system uses YOLOv8 to detect vehicles inside pre‑defined parking slots, thereby inferring the occupancy status (occupied/vacant) of each slot, and applies a shortest‑path algorithm on a graph to guide the driver to the nearest vacant slot. The system is designed to run on mid‑range GPU hardware (RTX 2080 Ti or Google Colab T4), ensuring feasibility for academic research and demo environments.

# Input
1. **Surveillance camera video**: Pre‑recorded video or a video stream (RTSP/USB), minimum resolution 720p (1080p recommended), frame rate ≥ 15 FPS. The camera observes an area of ≤ 20 parking slots. The input video is resized to 640×640 before being fed into YOLOv8 (the standard inference resolution of Ultralytics).
2. **Parking Lot Map**: A JSON configuration file describing:
   - **Slot list**: Each slot has a unique ID and polygon coordinates on the video frame (manually annotated once by the operator before operation).
   - **Camera‑to‑slot mapping**: The camera is mapped to the list of slots it observes.
   - **Walkway graph (adjacency graph)**: Nodes (slot, turning point, entrance gate) and edges with weights (distance in meters or grid cells).
3. **Current vehicle position**: The user selects a starting node on the web interface (e.g., entrance A, entrance B) for the path‑finding algorithm.

# Output
1. **Annotated Video**: The original video stream is overlaid with:
   - Each parking slot marked with a bounding box: **green** = vacant, **red** = occupied.
   - The recommended slot: **highlighted in yellow**.
2. **Continuously updated 2D parking‑lot diagram**: Displays vacant/occupied status for all slots and the suggested route.
3. **Shortest‑path information**: A list of nodes on the graph from the current position to the nearest vacant slot (based on shortest‑path distance), along with the estimated total distance.

# Requirements (Functional requirements – measurable)
| ID | Requirement | Acceptance threshold |
|---|---|---|
| R1 | Accurately classify the status of each parking slot (vacant / occupied). Pipeline: YOLOv8s detects vehicles → compute IoU between vehicle bbox and slot polygon → if IoU ≥ 0.3 → slot = occupied, otherwise = vacant. | Slot‑level F1‑score ≥ 0.90 on the test set |
| R2 | Identify the vacant slot with the shortest walkway distance from the user’s position (based on Dijkstra on the graph). When multiple slots share the same shortest distance, choose the slot with the smallest ID (deterministic tie‑breaking). | Correct selection rate ≥ 95% compared to ground truth (manual Dijkstra with the same tie‑breaking rule) |
| R3 | End‑to‑end processing time: from receiving 1 frame → detect → classify slot → find path → return result. Measured on RTX 2080 Ti or T4. | ≤ 2 seconds (average over 50 trials) |
| R4 | Update slot status when a vehicle enters or leaves a slot | Average latency ≤ 3 seconds from the moment the vehicle starts occupying/leaving the slot |
| R5 | Display results on a web interface: annotated video, 2D diagram, suggested route | Pass all test cases in the functional test suite (see M5) |

# Constraints
1. **Camera**: Use 1 fixed camera for the demo, resolution ≥ 720p (1080p recommended), mounted high (≥ 3m) looking down. The camera handles ≤ 20 slots, ensuring a minimum pixel density of ~50×50 px for the farthest slot. For the demo, use pre‑recorded video.
2. **Model**: Use **YOLOv8s** (small variant, ~11.2M parameters, ~22MB) from Ultralytics as the vehicle detector. Use COCO pretrained weights (class `car`, `truck`) directly — no fine‑tuning required. COCO pretrained weights reliably detect cars in indoor parking lot surveillance footage. Note: YOLO only detects vehicles, it does not directly classify the slot — slot classification is a post‑processing step based on IoU overlap. If hardware is more constrained, YOLOv8n (nano, ~3.2M params, ~6MB) can be substituted with a small accuracy trade‑off.
3. **Demo video source**: PKLot dataset camera sequences (e.g., PUCPR, UFPR04, UFPR05) are used as **demo video input** and **evaluation ground truth**. PKLot provides time‑series overhead images from fixed cameras with per‑slot occupancy labels, which directly supports evaluation metric M1. Sequential frames are stitched into a video for the demo.
4. **Processing hardware (GPU)**: One of the two configurations:
   - **Config A**: NVIDIA RTX 2080 Ti (11GB VRAM, CUDA Compute 7.5).
   - **Config B**: Google Colab with T4 GPU (16GB VRAM, CUDA Compute 7.5).
   - Inference VRAM budget: ≤ 4GB (YOLOv8s @ 640×640, batch=1).
   - Training VRAM budget (if fine‑tuning): ≤ 10GB (YOLOv8s, batch=8, imgsz=640, AMP=True).
5. **No fine‑tuning required**: The system uses COCO pretrained YOLOv8s weights directly. This eliminates training time, dataset preparation, and GPU training budget. If future improvement is needed, fine‑tuning on a custom‑annotated parking lot dataset (with per‑vehicle bounding boxes) can be explored separately.
6. **Network**: LAN/Wi‑Fi connection between camera and server with bandwidth ≥ 10 Mbps (if using a real video stream). Not required for pre‑recorded video.
7. **Demo parking lot size**: Maximum 20 parking slots, single level, 1 camera.
8. **Vehicle types**: Only 4‑wheel cars (sedan, SUV). Motorcycles, bicycles, and large trucks are not handled.

# Assumptions
1. Each parking slot has clearly marked lines and is large enough for one standard passenger car.
2. The parked vehicle lies completely within the defined slot polygon (no partial parking into another slot, no diagonal parking across two slots).
3. Lighting conditions in the parking lot are sufficient for the camera to capture clear images (indoor parking lot with functioning lighting).
4. At any given moment, at most 2 vehicles simultaneously change status (enter/leave) within the camera’s field of view.
5. The parking lot map (slot polygons, walkway graph) is manually set up once before system operation and does not change at runtime.
6. No illegally parked vehicles (e.g., parking on the walkway) — the system only checks registered slots.
7. The “nearest” criterion is defined purely as shortest graph distance (shortest path on the graph), without considering real‑world factors (ease of turning, proximity to exit, etc.). This is an intentional project limitation.
8. The GPU (RTX 2080 Ti or T4) is available throughout the demo/evaluation. The Colab session is not interrupted during benchmark measurements.
9. The COCO pretrained weights of YOLOv8s are good enough to detect cars in an indoor parking lot without fine‑tuning (fine‑tuning is optional for further improvement).

# Scope
**In‑scope:**
- Detect vehicles using YOLOv8s (COCO pretrained, no fine‑tuning) → infer parking slot status (vacant/occupied) based on IoU overlap between vehicle bbox and slot polygon.
- Use PKLot camera sequences as demo video source and evaluation ground truth (per‑slot occupancy labels).
- Find the shortest path to the nearest vacant slot using Dijkstra’s algorithm on the parking lot graph.
- Display results on a web interface: annotated video, 2D diagram, route information.
- Demo on pre‑recorded video, single‑level indoor parking lot, ≤ 20 slots, 1 camera.
- The entire inference pipeline runs on a single GPU (RTX 2080 Ti or T4).

**Out‑of‑scope:**
- License plate recognition.
- Payment / reservation system.
- Outdoor parking lots (weather affects image quality).
- Multi‑level parking lots.
- Simultaneous multi‑camera (>1 camera) in the demo.
- Detailed turn‑by‑turn navigation for the driver.
- Multi‑criteria optimization (e.g., near exit, easy to reverse into, etc.).
- Production deployment on cloud infrastructure or edge devices.
- Training a model from scratch — only pretrained or fine‑tuned models are used.

# Evaluation Metrics

## M1 — Parking slot status classification accuracy (slot‑level)
- **Requirement mapping**: R1
- **Metric**: Precision, Recall, F1‑score at the slot level (per‑slot binary classification: vacant vs. occupied)
- **Threshold**: F1‑score ≥ 0.90
- **Evaluation pipeline**:
  1. **Ground truth**: Each test frame is manually labeled for each slot: `occupied` or `vacant`. These are slot status labels, NOT vehicle bounding‑box labels.
  2. **System prediction**: YOLOv8s detects vehicles (conf ≥ 0.25) → compute IoU between each vehicle bbox and slot polygon → if IoU ≥ 0.3 → slot = occupied, otherwise = vacant.
  3. **Comparison**: For each slot in each frame, compare predicted label vs. ground truth label.
  4. **Calculation**: Confusion matrix (TP, TN, FP, FN) → Precision, Recall, F1‑score.
- **Test set**: ≥ 200 frames, including scenarios: nearly empty lot (≤ 20% occupied), moderately filled (40–60%), almost full (≥ 80%).
- **Reason for not using mAP@0.5**: mAP evaluates detection bbox quality, not directly the slot status. The core problem is occupancy classification at the slot level, so the correct metrics are Precision/Recall/F1 on the slot labels.

---

## M2 — Nearest slot selection accuracy
- **Requirement mapping**: R2
- **Metric**: Accuracy (correct selection rate)
- **Threshold**: ≥ 95%
- **Formula**: `Accuracy = Number of times the system selects correctly / Total number of trials`
- **Definition of “correct”**: The system’s chosen slot S is correct if S belongs to the set of slots that have the minimum shortest‑path distance (computed by Dijkstra). When multiple slots share the same shortest distance, any slot in that set is considered correct.
- **Measurement method**:
  - Prepare ≥ 30 test scenarios with different starting positions and parking lot occupancy states (including ≥ 5 scenarios where multiple slots have the same shortest distance).
  - For each scenario, compute the shortest path manually using Dijkstra on the same graph as ground truth.
  - Compare the system‑selected slot with the ground truth set of slots.
- **Note**: This metric evaluates purely the path‑finding algorithm + occupancy detection, NOT “optimality” in a multi‑criteria sense. The 95% threshold (instead of 100%) allows for errors caused by incorrect occupancy detection → impacting Dijkstra’s input.

---

## M3 — Response time
- **Requirement mapping**: R3
- **Metric**: Average Response Time
- **Threshold**: ≤ 2 seconds
- **Formula**: `T_avg = (1/N) × Σ (T_output_i − T_input_i)` with N ≥ 50
- **Measurement method**:
  - Record timestamp when the system receives an input frame.
  - Record timestamp when the system returns the complete result (annotated frame + route).
  - Compute the average over ≥ 50 trials with a fixed hardware configuration.
  - Report alongside: GPU configuration (RTX 2080 Ti or T4), number of slots in the lot, frame size.
- **Threshold rationale**: YOLOv8s inference on RTX 2080 Ti achieves ~50–150 FPS at 640×640 (~7–20ms/frame). The post‑processing pipeline (IoU + Dijkstra on 20 nodes) adds < 10ms. An end‑to‑end threshold of 2 seconds (including rendering + web transmission) is very achievable.

---

## M4 — Status update latency
- **Requirement mapping**: R4
- **Metric**: Average Update Latency
- **Threshold**: ≤ 3 seconds
- **Formula**: `L_avg = (1/N) × Σ (T_system_update_i − T_event_i)` with N ≥ 20
- **Measurement method**:
  - Use a test video with timestamp markers indicating the moment a vehicle begins to enter/leave a slot (ground truth by manual frame‑by‑frame observation).
  - Compare with the timestamp when the system updates the corresponding slot status.
  - Average over ≥ 20 entry/exit events.

---

## M5 — Functional testing of the web interface
- **Requirement mapping**: R5
- **Metric**: Test case pass rate
- **Threshold**: 100% test cases PASS
- **Test case table**:

| TC ID | Test case description | PASS condition |
|---|---|---|
| TC5.1 | Annotated video displays in the browser | Video renders continuously, slot bboxes show correct colors (green/red), no stutter > 2s |
| TC5.2 | 2D diagram updates when slot status changes | Status on diagram matches annotated video within 5s |
| TC5.3 | User selects a starting position and the system displays the route | Route is displayed on the 2D diagram within 5s after selection |
| TC5.4 | Works on the current Chrome version | No JavaScript errors blocking the UI, layout is not broken |
| TC5.5 | Displays number of vacant slots / total slots | The figure matches the actual status in the video |

---

# Summary table Requirement ↔ Metric

| Requirement | Metric | Threshold | Minimum sample size |
|---|---|---|---|
| R1 – Slot status classification | M1 – Slot‑level F1‑score | ≥ 0.90 | ≥ 200 frames, 3 density levels |
| R2 – Nearest slot selection (shortest path) | M2 – Accuracy | ≥ 95% | ≥ 30 scenarios (≥ 5 with tie) |
| R3 – Response time (on RTX 2080 Ti / T4) | M3 – Avg Response Time | ≤ 2s | ≥ 50 trials |
| R4 – Status update | M4 – Avg Update Latency | ≤ 3s | ≥ 20 events |
| R5 – Web interface | M5 – Test case pass rate | 100% (5/5 TC) | 5 test cases |