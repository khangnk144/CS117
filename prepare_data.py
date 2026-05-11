"""
PKLot Dataset Parser.
Parses PKLot XML annotations to extract slot polygons and occupancy labels.
Prepares data for use as demo video source and evaluation ground truth.
"""

import os
import xml.etree.ElementTree as ET
import json
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import glob


def parse_pklot_xml(xml_path: str) -> Tuple[List[Dict], Dict[str, str]]:
    """
    Parse a PKLot XML annotation file.

    PKLot XML structure:
        <parking id="...">
            <space id="1" occupied="1">
                <contour>
                    <point x="..." y="..."/>
                    ...
                </contour>
            </space>
            ...
        </parking>

    Args:
        xml_path: Path to the XML file.

    Returns:
        Tuple of:
            - slots: list of {'id': str, 'polygon': [[x,y], ...]}
            - labels: dict mapping slot_id -> 'occupied' or 'vacant'
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    slots = []
    labels = {}

    for space in root.iter("space"):
        slot_id = f"S{space.get('id')}"
        occupied = space.get("occupied", "0")
        status = "occupied" if occupied == "1" else "vacant"

        points = []
        contour = space.find("contour")
        if contour is not None:
            for point in contour.findall("point"):
                x = int(point.get("x", 0))
                y = int(point.get("y", 0))
                points.append([x, y])

        if points:
            slots.append({"id": slot_id, "polygon": points})
            labels[slot_id] = status

    return slots, labels


def find_pklot_sequences(pklot_root: str, parking_lot: str = "PUCPR",
                         weather: str = "Sunny",
                         max_images: int = 0) -> List[Tuple[str, str]]:
    """
    Find image-XML pairs from a specific PKLot camera sequence.

    Args:
        pklot_root: Root directory of the PKLot dataset.
        parking_lot: Which lot to use: 'PUCPR', 'UFPR04', 'UFPR05'.
        weather: Weather condition: 'Sunny', 'Cloudy', 'Rainy'.
        max_images: Max number of images to return (0 = all).

    Returns:
        List of (image_path, xml_path) tuples, sorted by filename.
    """
    # PKLot structure: PKLot/{lot}/{weather}/{date}/*.jpg + *.xml
    lot_dir = os.path.join(pklot_root, parking_lot, weather)
    if not os.path.isdir(lot_dir):
        # Try alternate structures
        for alt in [parking_lot.lower(), parking_lot.upper()]:
            for wt in [weather, weather.lower(), weather.upper()]:
                alt_dir = os.path.join(pklot_root, alt, wt)
                if os.path.isdir(alt_dir):
                    lot_dir = alt_dir
                    break

    if not os.path.isdir(lot_dir):
        print(f"Warning: Directory not found: {lot_dir}")
        print(f"Available in {pklot_root}:")
        if os.path.isdir(pklot_root):
            for item in os.listdir(pklot_root):
                print(f"  {item}")
        return []

    # Collect all jpg files with matching XML
    pairs = []
    for date_dir in sorted(os.listdir(lot_dir)):
        date_path = os.path.join(lot_dir, date_dir)
        if not os.path.isdir(date_path):
            continue
        for img_file in sorted(os.listdir(date_path)):
            if not img_file.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            img_path = os.path.join(date_path, img_file)
            # XML file has the same name but .xml extension
            xml_name = os.path.splitext(img_file)[0] + ".xml"
            xml_path = os.path.join(date_path, xml_name)
            if os.path.exists(xml_path):
                pairs.append((img_path, xml_path))

    if max_images > 0:
        pairs = pairs[:max_images]

    print(f"Found {len(pairs)} image-XML pairs in {lot_dir}")
    return pairs


def create_config_from_pklot(pklot_root: str,
                              parking_lot: str = "PUCPR",
                              weather: str = "Sunny",
                              output_path: str = "config/parking_lot.json") -> Dict:
    """
    Create the parking lot configuration JSON from PKLot annotations.
    Uses the first frame's XML to extract slot polygons, then builds
    a simple walkway graph connecting all slots.

    Args:
        pklot_root: Root directory of PKLot dataset.
        parking_lot: Which lot to use.
        weather: Weather condition.
        output_path: Where to save the config JSON.

    Returns:
        The config dict.
    """
    pairs = find_pklot_sequences(pklot_root, parking_lot, weather, max_images=1)
    if not pairs:
        raise FileNotFoundError(
            f"No PKLot data found for {parking_lot}/{weather} in {pklot_root}")

    img_path, xml_path = pairs[0]
    slots, _ = parse_pklot_xml(xml_path)

    # Include all slots
    # slots = slots[:20]

    # Build a simple walkway graph:
    # - One entrance node E1 at top-center of image
    # - Waypoints along a central aisle
    # - Each slot connects to the nearest waypoint
    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {img_path}")
    h, w = img.shape[:2]

    # Create graph nodes
    nodes = []
    edges = []

    # Entrance at top center
    nodes.append({"id": "E1", "type": "entrance", "x": w // 2, "y": 30})

    # Create waypoints along a central horizontal aisle
    num_waypoints = min(len(slots), 10)
    wp_y = h // 2  # middle of image
    for i in range(num_waypoints):
        wp_x = int(w * (i + 1) / (num_waypoints + 1))
        wp_id = f"W{i + 1}"
        nodes.append({"id": wp_id, "type": "waypoint", "x": wp_x, "y": wp_y})

        # Connect consecutive waypoints
        if i > 0:
            prev_wp = f"W{i}"
            dist = abs(wp_x - int(w * i / (num_waypoints + 1)))
            edges.append({"from": prev_wp, "to": wp_id, "weight": round(dist * 0.05, 1)})

    # Connect entrance to first waypoint
    if num_waypoints > 0:
        edges.append({"from": "E1", "to": "W1", "weight": round(abs(wp_y - 30) * 0.05, 1)})

    # Add slot nodes and connect to nearest waypoint
    for slot in slots:
        cx = int(np.mean([p[0] for p in slot["polygon"]]))
        cy = int(np.mean([p[1] for p in slot["polygon"]]))
        nodes.append({"id": slot["id"], "type": "slot", "x": cx, "y": cy})

        # Find nearest waypoint
        min_dist = float("inf")
        nearest_wp = "W1"
        for i in range(num_waypoints):
            wp_x = int(w * (i + 1) / (num_waypoints + 1))
            dist = np.sqrt((cx - wp_x) ** 2 + (cy - wp_y) ** 2)
            if dist < min_dist:
                min_dist = dist
                nearest_wp = f"W{i + 1}"

        edges.append({
            "from": slot["id"], "to": nearest_wp,
            "weight": round(min_dist * 0.05, 1)
        })

    config = {
        "parking_lot": parking_lot,
        "weather": weather,
        "image_size": {"width": w, "height": h},
        "slots": slots,
        "graph": {"nodes": nodes, "edges": edges},
        "model": {
            "name": "yolov8m.pt",
            "conf_threshold": 0.25,
            "iou_threshold": 0.3,
        },
    }

    # Save config
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Config saved to {output_path}")

    return config


def create_demo_video(pklot_root: str,
                       parking_lot: str = "PUCPR",
                       weather: str = "Sunny",
                       output_path: str = "dataset/demo_video.mp4",
                       max_frames: int = 300,
                       fps: int = 2) -> str:
    """
    Create a demo video from PKLot sequential images.

    Args:
        pklot_root: Root directory of the PKLot dataset.
        parking_lot: Which lot to use.
        weather: Weather condition.
        output_path: Path for the output video file.
        max_frames: Maximum number of frames to include.
        fps: Frames per second for the output video.

    Returns:
        Path to the created video file.
    """
    pairs = find_pklot_sequences(pklot_root, parking_lot, weather,
                                  max_images=max_frames)
    if not pairs:
        raise FileNotFoundError("No PKLot images found")

    # Read first image to get dimensions
    first_img = cv2.imread(pairs[0][0])
    if first_img is None:
        raise FileNotFoundError(f"Cannot read: {pairs[0][0]}")
    h, w = first_img.shape[:2]

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    print(f"Creating demo video: {len(pairs)} frames @ {fps} FPS")
    for i, (img_path, _) in enumerate(pairs):
        img = cv2.imread(img_path)
        if img is not None:
            writer.write(img)
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(pairs)} frames")

    writer.release()
    print(f"Demo video saved to {output_path}")
    return output_path


def create_ground_truth(pklot_root: str,
                         parking_lot: str = "PUCPR",
                         weather: str = "Sunny",
                         output_path: str = "dataset/ground_truth.json",
                         max_frames: int = 300) -> str:
    """
    Create ground truth labels from PKLot XML annotations.

    Args:
        pklot_root: Root directory of PKLot dataset.
        parking_lot: Which lot.
        weather: Weather condition.
        output_path: Where to save the ground truth JSON.
        max_frames: Max frames to process.

    Returns:
        Path to the ground truth file.
    """
    pairs = find_pklot_sequences(pklot_root, parking_lot, weather,
                                  max_images=max_frames)

    ground_truth = []
    for i, (img_path, xml_path) in enumerate(pairs):
        _, labels = parse_pklot_xml(xml_path)
        # Include all slots
        limited_labels = labels

        ground_truth.append({
            "frame_index": i,
            "image_path": img_path,
            "labels": limited_labels,
        })

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(ground_truth, f, indent=2)
    print(f"Ground truth saved to {output_path} ({len(ground_truth)} frames)")
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prepare PKLot data for demo")
    parser.add_argument("--pklot-root", type=str,
                        default="dataset/PKLot",
                        help="Root directory of PKLot dataset")
    parser.add_argument("--lot", type=str, default="PUCPR",
                        choices=["PUCPR", "UFPR04", "UFPR05"],
                        help="Which parking lot to use")
    parser.add_argument("--weather", type=str, default="Sunny",
                        choices=["Sunny", "Cloudy", "Rainy"],
                        help="Weather condition")
    parser.add_argument("--max-frames", type=int, default=300,
                        help="Max frames for demo video")
    parser.add_argument("--fps", type=int, default=2,
                        help="FPS for demo video")

    args = parser.parse_args()

    print("=" * 60)
    print("Step 1: Creating parking lot config from PKLot annotations")
    print("=" * 60)
    config = create_config_from_pklot(
        args.pklot_root, args.lot, args.weather,
        output_path="config/parking_lot.json"
    )
    print(f"  → {len(config['slots'])} slots configured")
    print(f"  → {len(config['graph']['nodes'])} graph nodes")
    print(f"  → {len(config['graph']['edges'])} graph edges")

    print()
    print("=" * 60)
    print("Step 2: Creating demo video from PKLot images")
    print("=" * 60)
    create_demo_video(
        args.pklot_root, args.lot, args.weather,
        output_path="dataset/demo_video.mp4",
        max_frames=args.max_frames, fps=args.fps
    )

    print()
    print("=" * 60)
    print("Step 3: Creating ground truth labels")
    print("=" * 60)
    create_ground_truth(
        args.pklot_root, args.lot, args.weather,
        output_path="dataset/ground_truth.json",
        max_frames=args.max_frames
    )

    print()
    print("Done! Next steps:")
    print("  1. Run the web app:  python web/app.py")
    print("  2. Run evaluation:   python evaluate.py")
