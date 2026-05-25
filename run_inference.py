import argparse
import json
import os

import cv2

from src.pipeline import ParkingPipeline


def main():
    parser = argparse.ArgumentParser(
        description="Run calibrated parking occupancy inference on a video."
    )
    parser.add_argument("--config", default="config/parking_lot.json")
    parser.add_argument("--video", default=None, help="Input video path; overrides config.")
    parser.add_argument("--output", default="results/output.mp4")
    parser.add_argument("--model", default=None, help="Optional Ultralytics detector weights.")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument(
        "--mode", choices=["hybrid", "appearance", "detector"], default=None
    )
    parser.add_argument(
        "--empty-reference",
        default=None,
        help="Image showing empty configured slots for background calibration.",
    )
    parser.add_argument(
        "--calibrate-first-frame",
        action="store_true",
        help="Use frame 0 as empty reference only when every configured slot is empty.",
    )
    parser.add_argument(
        "--skip-auto-calibration",
        action="store_true",
        help="Skip the default detector-guided scan of the input video.",
    )
    parser.add_argument(
        "--auto-calibration-samples",
        type=int,
        default=None,
        help="Maximum video frames sampled to learn empty references.",
    )
    parser.add_argument("--disable-detector", action="store_true")
    args = parser.parse_args()

    with open(args.config) as config_file:
        config = json.load(config_file)
    inference = config.setdefault("inference", {})
    if args.mode:
        inference["mode"] = args.mode
    if args.disable_detector:
        inference.setdefault("detector", {})["enabled"] = False

    video_path = args.video or config.get("video_path")
    if not video_path:
        raise SystemExit("No video supplied via --video or config video_path.")
    config["video_path"] = video_path

    print(f"Initializing {inference.get('mode', 'hybrid')} occupancy pipeline...")
    pipeline = ParkingPipeline(config, device=args.device, model_name=args.model)
    if args.empty_reference:
        reference = cv2.imread(args.empty_reference)
        if reference is None:
            raise SystemExit(f"Could not read reference image: {args.empty_reference}")
        pipeline.calibrate(reference)

    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise SystemExit(f"Could not open video: {video_path}")
    if args.calibrate_first_frame:
        success, empty_frame = capture.read()
        if not success:
            raise SystemExit("Could not read frame 0 for calibration.")
        pipeline.calibrate(empty_frame)
        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
    elif not args.skip_auto_calibration:
        print("Automatically learning visible empty-slot references from video...")
        report = pipeline.auto_calibrate_video(
            video_path, max_samples=args.auto_calibration_samples
        )
        if report.get("warning"):
            print(f"Calibration warning: {report['warning']}")
        print(
            f"Calibration confirmed {len(report['calibrated_slots'])}/"
            f"{len(config['slots'])} slots from {report.get('sampled_frames', 0)} samples."
        )

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    writer = cv2.VideoWriter(
        args.output, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )

    frame_count = 0
    while True:
        success, frame = capture.read()
        if not success:
            break
        frame_count += 1
        result = pipeline.process_frame(frame)
        writer.write(result["annotated_frame"])
        if frame_count % 30 == 0:
            summary = result["summary"]
            print(
                f"Processed {frame_count} frames; "
                f"occupied={summary['occupied']}, vacant={summary['vacant']}, "
                f"unknown={summary['unknown']}"
            )

    capture.release()
    writer.release()
    print(f"Finished processing. Output saved to {args.output}")


if __name__ == "__main__":
    main()
