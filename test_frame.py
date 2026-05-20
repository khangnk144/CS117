import cv2
import numpy as np

cap = cv2.VideoCapture('dataset/test.mp4')
ret, frame = cap.read()
if ret:
    print(f"Frame shape: {frame.shape}, Max pixel: {np.max(frame)}, Min pixel: {np.min(frame)}")
    if np.max(frame) == 0:
        print("FRAME IS COMPLETELY BLACK!")
else:
    print("Could not read frame")
