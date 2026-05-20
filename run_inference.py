import cv2
import json
import argparse
import os
from src.pipeline import ParkingPipeline

def main():
    parser = argparse.ArgumentParser(description="Run YOLO-based parking inference on a video.")
    parser.add_argument("--config", type=str, default="config/parking_lot.json", help="Path to config file.")
    parser.add_argument("--video", type=str, default="dataset/test2.mp4", help="Path to input video.")
    parser.add_argument("--output", type=str, default="results/output.mp4", help="Path to output video.")
    parser.add_argument("--model", type=str, default="yolov8n-visdrone.pt", help="YOLO model to use.")
    args = parser.parse_args()

    # Load config
    with open(args.config, "r") as f:
        config = json.load(f)

    # Override video path in config if provided
    if args.video:
        config["video_path"] = args.video

    print(f"Initializing pipeline with {args.model}...")
    pipeline = ParkingPipeline(config, device="cuda", model_name=args.model)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: Could not open video {args.video}")
        return

    # Get video properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        fps = 30

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(args.output, fourcc, fps, (width, height))

    print(f"Processing video {args.video}...")
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        
        # Process frame
        result = pipeline.process_frame(frame)
        annotated = result["annotated_frame"]
        
        # Write to output
        out.write(annotated)
        
        # Print progress
        if frame_count % 30 == 0:
            print(f"Processed {frame_count} frames... Occupied: {result['summary']['occupied']}/{result['summary']['total_slots']}")

    cap.release()
    out.release()
    print(f"Finished processing. Output saved to {args.output}")

if __name__ == "__main__":
    main()
