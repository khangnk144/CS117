"""
Evaluation script for all SRS metrics (M1–M4).
Evaluates the calibrated hybrid occupancy pipeline.
"""

import json
import time
import os
import sys
import cv2
import numpy as np
from typing import Dict, List

from src.pathfinder import ParkingGraph
from src.pipeline import ParkingPipeline

def evaluate_m1_slot_accuracy(pipeline: ParkingPipeline,
                               ground_truth_path: str,
                               verbose: bool = True) -> Dict:
    """
    M1 — Parking slot status classification accuracy (slot-level).
    Threshold: F1-score ≥ 0.95.
    """
    if not os.path.exists(ground_truth_path):
        return {"error": "ground_truth.json not found"}
        
    with open(ground_truth_path) as f:
        ground_truth = json.load(f)

    tp, fp, fn, tn = 0, 0, 0, 0
    unknown_predictions = 0
    total_predictions = 0
    total_frames = 0

    for gt_entry in ground_truth:
        img_path = gt_entry["image_path"]
        gt_labels = gt_entry["labels"]

        if not os.path.exists(img_path):
            continue

        frame = cv2.imread(img_path)
        if frame is None:
            continue

        result = pipeline.process_frame(frame)
        pred_statuses = {s["id"]: s["status"] for s in result["slot_statuses"]}

        for slot_id, gt_status in gt_labels.items():
            pred_status = pred_statuses.get(slot_id)
            if pred_status is None:
                continue
            total_predictions += 1

            if pred_status == "unknown":
                unknown_predictions += 1
                if gt_status == "occupied":
                    fn += 1
            elif gt_status == "occupied" and pred_status == "occupied":
                tp += 1
            elif gt_status == "vacant" and pred_status == "occupied":
                fp += 1
            elif gt_status == "occupied" and pred_status == "vacant":
                fn += 1
            elif gt_status == "vacant" and pred_status == "vacant":
                tn += 1

        total_frames += 1
        if verbose and total_frames % 20 == 0:
            print(f"  Processed {total_frames}/{len(ground_truth)} frames")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    results = {
        "metric": "M1 - Slot-level F1-score",
        "threshold": 0.95,
        "minimum_coverage": 0.95,
        "passed": bool(
            f1 >= 0.95
            and 1.0 - unknown_predictions / max(total_predictions, 1) >= 0.95
        ),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "total_frames": total_frames,
        "total_slot_predictions": total_predictions,
        "unknown_predictions": unknown_predictions,
        "coverage": round(
            1.0 - unknown_predictions / max(total_predictions, 1), 4
        ),
    }

    if verbose:
        print(f"\n{'='*50}")
        print(f"M1 Results — Slot-level Classification")
        print(f"{'='*50}")
        print(f"  Precision : {results['precision']:.4f}")
        print(f"  Recall    : {results['recall']:.4f}")
        print(f"  F1-score  : {results['f1_score']:.4f}  (threshold: ≥ 0.95)")
        print(f"  Coverage  : {results['coverage']:.4f}  (unknown={unknown_predictions})")
        print(f"  PASSED    : {'✓ YES' if results['passed'] else '✗ NO'}")
        print(f"  Confusion : TP={tp} FP={fp} FN={fn} TN={tn}")
        print(f"  Frames    : {total_frames}")

    return results

def evaluate_m2_navigation(graph: ParkingGraph,
                            test_scenarios: List[Dict],
                            verbose: bool = True) -> Dict:
    """
    M2 — Nearest slot selection accuracy.
    Threshold: ≥ 95%
    """
    correct = 0
    total = len(test_scenarios)
    details = []

    for i, scenario in enumerate(test_scenarios):
        result = graph.find_nearest_vacant(scenario["start"],
                                            scenario["vacant_slots"])
        selected = result["target_slot"]
        expected_set = scenario["expected_slots"]
        is_correct = selected in expected_set

        if is_correct:
            correct += 1

        details.append({
            "scenario": i + 1,
            "start": scenario["start"],
            "selected": selected,
            "expected": expected_set,
            "correct": bool(is_correct),
            "distance": result["distance"],
        })

    accuracy = correct / total if total > 0 else 0.0

    results = {
        "metric": "M2 - Navigation Accuracy",
        "threshold": 0.95,
        "passed": bool(accuracy >= 0.95),
        "accuracy": round(accuracy, 4),
        "correct": correct,
        "total": total,
        "details": details,
    }

    if verbose:
        print(f"\n{'='*50}")
        print(f"M2 Results — Navigation Accuracy")
        print(f"{'='*50}")
        print(f"  Accuracy : {accuracy:.4f}  (threshold: ≥ 0.95)")
        print(f"  PASSED   : {'✓ YES' if results['passed'] else '✗ NO'}")
        print(f"  Correct  : {correct}/{total}")

    return results


def evaluate_m3_response_time(pipeline: ParkingPipeline,
                                ground_truth_path: str,
                                num_trials: int = 50,
                                verbose: bool = True) -> Dict:
    """
    M3 — Response time.
    Threshold: ≤ 2 seconds.
    """
    if not os.path.exists(ground_truth_path):
        return {"error": "ground_truth.json not found"}
        
    with open(ground_truth_path) as f:
        ground_truth = json.load(f)

    times = []
    for i, gt_entry in enumerate(ground_truth[:num_trials]):
        img_path = gt_entry["image_path"]
        if not os.path.exists(img_path):
            continue

        frame = cv2.imread(img_path)
        if frame is None:
            continue

        t_start = time.perf_counter()
        pipeline.process_frame(frame)
        t_end = time.perf_counter()

        elapsed_s = t_end - t_start
        times.append(elapsed_s)

    avg_time = np.mean(times) if times else 0.0
    max_time = np.max(times) if times else 0.0
    min_time = np.min(times) if times else 0.0

    results = {
        "metric": "M3 - Avg Response Time",
        "threshold_seconds": 2.0,
        "passed": bool(avg_time <= 2.0),
        "avg_time_seconds": round(float(avg_time), 4),
        "max_time_seconds": round(float(max_time), 4),
        "min_time_seconds": round(float(min_time), 4),
        "num_trials": len(times),
    }

    if verbose:
        print(f"\n{'='*50}")
        print(f"M3 Results — Response Time")
        print(f"{'='*50}")
        print(f"  Avg time : {avg_time:.4f}s  (threshold: ≤ 2.0s)")
        print(f"  PASSED   : {'✓ YES' if results['passed'] else '✗ NO'}")
        print(f"  Min/Max  : {min_time:.4f}s / {max_time:.4f}s")
        print(f"  Trials   : {len(times)}")

    return results


def generate_navigation_test_scenarios(config: Dict,
                                        ground_truth_path: str,
                                        num_scenarios: int = 30) -> List[Dict]:
    if not os.path.exists(ground_truth_path):
        return []
        
    with open(ground_truth_path) as f:
        ground_truth = json.load(f)

    graph = ParkingGraph(config["graph"])
    slot_ids = [s["id"] for s in config["slots"]]
    scenarios = []

    step = max(1, len(ground_truth) // num_scenarios)
    for i in range(0, len(ground_truth), step):
        if len(scenarios) >= num_scenarios:
            break

        gt_entry = ground_truth[i]
        labels = gt_entry["labels"]
        vacant_slots = [sid for sid in slot_ids
                        if labels.get(sid, "vacant") == "vacant"]

        if not vacant_slots:
            continue

        nav = graph.find_nearest_vacant("E1", vacant_slots)
        if nav["target_slot"] is None:
            continue

        dist, _ = graph.dijkstra("E1")
        min_d = nav["distance"]
        expected = sorted([sid for sid in vacant_slots
                          if sid in dist and abs(dist[sid] - min_d) < 1e-9])

        scenarios.append({
            "start": "E1",
            "vacant_slots": vacant_slots,
            "expected_slots": expected,
        })

    return scenarios


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate parking system (M1-M4)")
    parser.add_argument("--config", type=str, default="config/parking_lot.json",
                        help="Path to parking lot config")
    parser.add_argument("--ground-truth", type=str,
                        default="dataset/ground_truth.json",
                        help="Path to ground truth labels")
    parser.add_argument("--model", type=str, default=None,
                        help="Optional Ultralytics detector weights")
    parser.add_argument("--device", type=str, default="auto",
                        choices=["auto", "cpu", "cuda"],
                        help="Detector inference device")
    parser.add_argument("--empty-reference", type=str, default=None,
                        help="Image showing the configured slots empty")
    parser.add_argument("--calibration-video", type=str, default=None,
                        help="Video scanned to auto-learn empty slot references")
    parser.add_argument("--metrics", type=str, nargs="+",
                        default=["M1", "M2", "M3"],
                        help="Which metrics to evaluate")

    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    all_results = {}

    if "M1" in args.metrics or "M3" in args.metrics:
        print("Initializing calibrated hybrid occupancy pipeline...")
        pipeline = ParkingPipeline(config, device=args.device, model_name=args.model)
        if args.calibration_video:
            report = pipeline.auto_calibrate_video(args.calibration_video)
            print(
                f"Auto-calibrated {len(report['calibrated_slots'])}/"
                f"{len(config['slots'])} slots before evaluation."
            )
            if report.get("warning"):
                print(f"Calibration warning: {report['warning']}")
        if args.empty_reference:
            reference_frame = cv2.imread(args.empty_reference)
            if reference_frame is None:
                raise SystemExit(f"Cannot read empty reference: {args.empty_reference}")
            pipeline.calibrate(reference_frame)

    if "M1" in args.metrics:
        print("\n" + "=" * 60)
        print("Evaluating M1 — Slot Classification Accuracy")
        print("=" * 60)
        all_results["M1"] = evaluate_m1_slot_accuracy(pipeline, args.ground_truth)

    if "M2" in args.metrics:
        print("\n" + "=" * 60)
        print("Evaluating M2 — Navigation Accuracy")
        print("=" * 60)
        graph = ParkingGraph(config["graph"])
        scenarios = generate_navigation_test_scenarios(
            config, args.ground_truth, num_scenarios=30)
        if scenarios:
            all_results["M2"] = evaluate_m2_navigation(graph, scenarios)
        else:
            print("No scenarios generated for M2.")

    if "M3" in args.metrics:
        print("\n" + "=" * 60)
        print("Evaluating M3 — Response Time")
        print("=" * 60)
        all_results["M3"] = evaluate_m3_response_time(
            pipeline, args.ground_truth, num_trials=50)

    # Save results
    os.makedirs("results", exist_ok=True)
    output_path = "results/evaluation_results.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nAll results saved to {output_path}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for metric_id, result in all_results.items():
        if "passed" in result:
            status = "✓ PASS" if result["passed"] else "✗ FAIL"
            print(f"  {result.get('metric', metric_id)}: {status}")
        else:
            print(f"  {metric_id}: Evaluation error or skipped")
