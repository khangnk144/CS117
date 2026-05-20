"""
PKLot CNN Training Script.

Trains or fine-tunes the lightweight ParkingSlotCNN on PKLotSegmented data.

PKLotSegmented contains pre-cropped parking slot images organized as:
    PKLotSegmented/{Lot}/{Weather}/{Date}/Occupied/*.jpg
    PKLotSegmented/{Lot}/{Weather}/{Date}/Empty/*.jpg

This script:
    1. Loads and splits PKLotSegmented images into train/val/test sets
    2. Applies data augmentation (random flip, rotation, color jitter)
    3. Trains the CNN with early stopping
    4. Saves the best model checkpoint to models/slot_classifier.pth
    5. Reports per-weather and cross-lot evaluation metrics

Usage:
    # Train on all lots/weathers
    ./venv/bin/python train_cnn.py --pklot-root dataset/PKLot/PKLotSegmented

    # Train on specific lot/weather
    ./venv/bin/python train_cnn.py --pklot-root dataset/PKLot/PKLotSegmented \
        --lots PUC --weathers Sunny Cloudy

    # Fine-tune from existing checkpoint
    ./venv/bin/python train_cnn.py --pklot-root dataset/PKLot/PKLotSegmented \
        --resume models/slot_classifier.pth

    # Quick test run (small sample)
    ./venv/bin/python train_cnn.py --pklot-root dataset/PKLot/PKLotSegmented \
        --max-per-class 500 --epochs 5
"""

import os
import sys
import argparse
import random
import time
import json
import numpy as np
import cv2
from typing import List, Tuple, Dict, Optional
from pathlib import Path

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    print("ERROR: PyTorch is required for training.")
    print("Install with: pip install torch torchvision")
    sys.exit(1)

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))
from src.cnn_classifier import ParkingSlotCNN


# ==============================================================================
# Dataset
# ==============================================================================

class PKLotSegmentedDataset(Dataset):
    """
    PyTorch Dataset for PKLotSegmented images.

    Loads cropped parking slot images from the folder structure:
        {root}/{lot}/{weather}/{date}/Occupied/*.jpg  → label=1
        {root}/{lot}/{weather}/{date}/Empty/*.jpg     → label=0
    """

    def __init__(self, image_paths: List[str], labels: List[int],
                 input_size: int = 64, augment: bool = False):
        self.image_paths = image_paths
        self.labels = labels
        self.input_size = input_size
        self.augment = augment

        # ImageNet normalization
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        img = cv2.imread(self.image_paths[idx])
        if img is None:
            # Return a black image if file is corrupted
            img = np.zeros((self.input_size, self.input_size, 3), dtype=np.uint8)

        # Resize
        img = cv2.resize(img, (self.input_size, self.input_size))

        # Data augmentation
        if self.augment:
            img = self._augment(img)

        # BGR → RGB → float → normalize
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = (img - self.mean) / self.std

        # HWC → CHW
        tensor = torch.from_numpy(img).permute(2, 0, 1)
        label = torch.tensor(self.labels[idx], dtype=torch.long)

        return tensor, label

    def _augment(self, img: np.ndarray) -> np.ndarray:
        """Apply random augmentations."""
        # Random horizontal flip
        if random.random() > 0.5:
            img = cv2.flip(img, 1)

        # Random vertical flip (parking slots can be rotated)
        if random.random() > 0.5:
            img = cv2.flip(img, 0)

        # Random rotation (±15 degrees)
        if random.random() > 0.5:
            angle = random.uniform(-15, 15)
            h, w = img.shape[:2]
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)

        # Random brightness/contrast
        if random.random() > 0.5:
            alpha = random.uniform(0.8, 1.2)  # contrast
            beta = random.randint(-20, 20)  # brightness
            img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

        # Random color jitter (simulate weather changes)
        if random.random() > 0.3:
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[:, :, 0] += random.uniform(-10, 10)  # hue
            hsv[:, :, 1] *= random.uniform(0.8, 1.2)  # saturation
            hsv[:, :, 2] *= random.uniform(0.8, 1.2)  # value
            hsv = np.clip(hsv, 0, 255).astype(np.uint8)
            img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        # Random Gaussian noise
        if random.random() > 0.7:
            noise = np.random.normal(0, 5, img.shape).astype(np.uint8)
            img = cv2.add(img, noise)

        return img


def collect_pklot_images(pklot_root: str,
                          lots: List[str] = None,
                          weathers: List[str] = None,
                          max_per_class: int = 0) -> Tuple[List[str], List[int], List[Dict]]:
    """
    Collect image paths and labels from PKLotSegmented directory.

    Args:
        pklot_root: Root of PKLotSegmented (contains PUC/, UFPR04/, UFPR05/).
        lots: Which parking lots to include. None = all.
        weathers: Which weather conditions. None = all.
        max_per_class: Max images per class (0 = all). For quick testing.

    Returns:
        Tuple of (paths, labels, metadata).
        metadata contains per-image info: lot, weather, date.
    """
    all_lots = lots or ["PUC", "UFPR04", "UFPR05"]
    all_weathers = weathers or ["Sunny", "Cloudy", "Rainy"]

    occupied_paths = []
    empty_paths = []
    occupied_meta = []
    empty_meta = []

    for lot in all_lots:
        for weather in all_weathers:
            weather_dir = os.path.join(pklot_root, lot, weather)
            if not os.path.isdir(weather_dir):
                continue

            for date_dir in sorted(os.listdir(weather_dir)):
                date_path = os.path.join(weather_dir, date_dir)
                if not os.path.isdir(date_path):
                    continue

                # Occupied images
                occ_dir = os.path.join(date_path, "Occupied")
                if os.path.isdir(occ_dir):
                    for f in os.listdir(occ_dir):
                        if f.lower().endswith((".jpg", ".jpeg", ".png")):
                            occupied_paths.append(os.path.join(occ_dir, f))
                            occupied_meta.append({
                                "lot": lot, "weather": weather, "date": date_dir
                            })

                # Empty images
                emp_dir = os.path.join(date_path, "Empty")
                if os.path.isdir(emp_dir):
                    for f in os.listdir(emp_dir):
                        if f.lower().endswith((".jpg", ".jpeg", ".png")):
                            empty_paths.append(os.path.join(emp_dir, f))
                            empty_meta.append({
                                "lot": lot, "weather": weather, "date": date_dir
                            })

    print(f"Raw counts: Occupied={len(occupied_paths)}, Empty={len(empty_paths)}")

    # Subsample if requested
    if max_per_class > 0:
        if len(occupied_paths) > max_per_class:
            indices = random.sample(range(len(occupied_paths)), max_per_class)
            occupied_paths = [occupied_paths[i] for i in indices]
            occupied_meta = [occupied_meta[i] for i in indices]
        if len(empty_paths) > max_per_class:
            indices = random.sample(range(len(empty_paths)), max_per_class)
            empty_paths = [empty_paths[i] for i in indices]
            empty_meta = [empty_meta[i] for i in indices]

    # Balance classes (undersample majority)
    min_count = min(len(occupied_paths), len(empty_paths))
    if len(occupied_paths) > min_count:
        indices = random.sample(range(len(occupied_paths)), min_count)
        occupied_paths = [occupied_paths[i] for i in indices]
        occupied_meta = [occupied_meta[i] for i in indices]
    if len(empty_paths) > min_count:
        indices = random.sample(range(len(empty_paths)), min_count)
        empty_paths = [empty_paths[i] for i in indices]
        empty_meta = [empty_meta[i] for i in indices]

    print(f"Balanced: {min_count} per class, {min_count * 2} total")

    # Combine
    paths = occupied_paths + empty_paths
    labels = [1] * len(occupied_paths) + [0] * len(empty_paths)
    metadata = occupied_meta + empty_meta

    return paths, labels, metadata


def split_dataset(paths: List[str], labels: List[int],
                  metadata: List[Dict],
                  val_ratio: float = 0.15,
                  test_ratio: float = 0.15,
                  split_by_date: bool = True) -> Dict:
    """
    Split dataset into train/val/test, optionally by date for fair evaluation.

    When split_by_date=True, entire dates are assigned to splits to prevent
    temporal data leakage (consecutive frames from same date are very similar).
    """
    if split_by_date and metadata:
        # Group by date
        date_groups: Dict[str, List[int]] = {}
        for i, m in enumerate(metadata):
            key = f"{m['lot']}_{m['weather']}_{m['date']}"
            if key not in date_groups:
                date_groups[key] = []
            date_groups[key].append(i)

        dates = list(date_groups.keys())
        random.shuffle(dates)

        n_dates = len(dates)
        n_val = max(1, int(n_dates * val_ratio))
        n_test = max(1, int(n_dates * test_ratio))

        test_dates = dates[:n_test]
        val_dates = dates[n_test:n_test + n_val]
        train_dates = dates[n_test + n_val:]

        train_idx = [i for d in train_dates for i in date_groups[d]]
        val_idx = [i for d in val_dates for i in date_groups[d]]
        test_idx = [i for d in test_dates for i in date_groups[d]]

        print(f"Split by date: {len(train_dates)} train dates, "
              f"{len(val_dates)} val dates, {len(test_dates)} test dates")
    else:
        indices = list(range(len(paths)))
        random.shuffle(indices)
        n = len(indices)
        n_test = int(n * test_ratio)
        n_val = int(n * val_ratio)

        test_idx = indices[:n_test]
        val_idx = indices[n_test:n_test + n_val]
        train_idx = indices[n_test + n_val:]

    return {
        "train": {
            "paths": [paths[i] for i in train_idx],
            "labels": [labels[i] for i in train_idx],
        },
        "val": {
            "paths": [paths[i] for i in val_idx],
            "labels": [labels[i] for i in val_idx],
        },
        "test": {
            "paths": [paths[i] for i in test_idx],
            "labels": [labels[i] for i in test_idx],
        },
    }


# ==============================================================================
# Training Loop
# ==============================================================================

def train_one_epoch(model, dataloader, optimizer, criterion, device):
    """Train for one epoch. Returns (loss, accuracy)."""
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0

    for batch_idx, (images, labels) in enumerate(dataloader):
        images = images.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        correct += predicted.eq(labels).sum().item()
        total += labels.size(0)

    return total_loss / total, correct / total


@torch.no_grad()
def evaluate(model, dataloader, criterion, device):
    """Evaluate model. Returns (loss, accuracy, precision, recall, f1)."""
    model.eval()
    total_loss = 0.0
    tp, fp, fn, tn = 0, 0, 0, 0

    for images, labels in dataloader:
        images = images.to(device)
        labels = labels.to(device)

        outputs = model(images)
        loss = criterion(outputs, labels)
        total_loss += loss.item() * images.size(0)

        _, predicted = outputs.max(1)
        # occupied=1, empty=0
        tp += ((predicted == 1) & (labels == 1)).sum().item()
        fp += ((predicted == 1) & (labels == 0)).sum().item()
        fn += ((predicted == 0) & (labels == 1)).sum().item()
        tn += ((predicted == 0) & (labels == 0)).sum().item()

    total = tp + fp + fn + tn
    accuracy = (tp + tn) / max(total, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-8)

    return total_loss / max(total, 1), accuracy, precision, recall, f1


def train(args):
    """Main training function."""
    print("=" * 60)
    print("PKLot CNN Slot Classifier — Training")
    print("=" * 60)

    # Set random seeds for reproducibility
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = torch.device(args.device)
    print(f"Device: {device}")

    # Collect data
    print(f"\nCollecting images from {args.pklot_root}...")
    lots = args.lots if args.lots else None
    weathers = args.weathers if args.weathers else None
    paths, labels, metadata = collect_pklot_images(
        args.pklot_root, lots=lots, weathers=weathers,
        max_per_class=args.max_per_class
    )

    if len(paths) == 0:
        print("ERROR: No images found. Check --pklot-root path.")
        return

    # Split
    print("\nSplitting dataset...")
    splits = split_dataset(paths, labels, metadata,
                           val_ratio=0.15, test_ratio=0.15,
                           split_by_date=True)

    for split_name, split_data in splits.items():
        n_occ = sum(1 for l in split_data["labels"] if l == 1)
        n_emp = len(split_data["labels"]) - n_occ
        print(f"  {split_name}: {len(split_data['labels'])} images "
              f"(occupied={n_occ}, empty={n_emp})")

    # Create datasets and dataloaders
    train_ds = PKLotSegmentedDataset(
        splits["train"]["paths"], splits["train"]["labels"],
        input_size=64, augment=True
    )
    val_ds = PKLotSegmentedDataset(
        splits["val"]["paths"], splits["val"]["labels"],
        input_size=64, augment=False
    )
    test_ds = PKLotSegmentedDataset(
        splits["test"]["paths"], splits["test"]["labels"],
        input_size=64, augment=False
    )

    train_loader = DataLoader(train_ds, batch_size=args.batch_size,
                               shuffle=True, num_workers=args.workers,
                               pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size,
                             shuffle=False, num_workers=args.workers,
                             pin_memory=True)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size,
                              shuffle=False, num_workers=args.workers,
                              pin_memory=True)

    # Create model
    model = ParkingSlotCNN().to(device)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"\nModel: ParkingSlotCNN ({total_params:,} parameters)")

    # Resume from checkpoint
    start_epoch = 0
    if args.resume and os.path.exists(args.resume):
        checkpoint = torch.load(args.resume, map_location=device, weights_only=True)
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            model.load_state_dict(checkpoint["model_state_dict"])
            start_epoch = checkpoint.get("epoch", 0)
            print(f"Resumed from {args.resume} (epoch {start_epoch})")
        else:
            model.load_state_dict(checkpoint)
            print(f"Loaded weights from {args.resume}")

    # Optimizer and scheduler
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs, eta_min=1e-6)
    criterion = nn.CrossEntropyLoss()

    # Training loop with early stopping
    best_val_f1 = 0.0
    patience_counter = 0
    os.makedirs(args.output_dir, exist_ok=True)
    best_model_path = os.path.join(args.output_dir, "slot_classifier.pth")

    print(f"\nTraining for {args.epochs} epochs...")
    print(f"{'Epoch':>6} | {'Train Loss':>10} | {'Train Acc':>9} | "
          f"{'Val Loss':>8} | {'Val Acc':>7} | {'Val F1':>6} | {'LR':>10}")
    print("-" * 75)

    for epoch in range(start_epoch, args.epochs):
        t_start = time.time()

        # Train
        train_loss, train_acc = train_one_epoch(
            model, train_loader, optimizer, criterion, device)

        # Validate
        val_loss, val_acc, val_prec, val_rec, val_f1 = evaluate(
            model, val_loader, criterion, device)

        scheduler.step()
        lr = optimizer.param_groups[0]["lr"]
        elapsed = time.time() - t_start

        print(f"  {epoch + 1:4d} | {train_loss:10.4f} | {train_acc:8.4f} | "
              f"{val_loss:8.4f} | {val_acc:6.4f} | {val_f1:5.4f} | {lr:10.6f}  "
              f"({elapsed:.1f}s)")

        # Save best model
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            patience_counter = 0
            torch.save({
                "epoch": epoch + 1,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_f1": val_f1,
                "val_acc": val_acc,
            }, best_model_path)
            print(f"         ↳ Saved best model (F1={val_f1:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                print(f"\nEarly stopping at epoch {epoch + 1} "
                      f"(no improvement for {args.patience} epochs)")
                break

    # Load best model for test evaluation
    print(f"\n{'=' * 60}")
    print("Test Evaluation")
    print(f"{'=' * 60}")

    checkpoint = torch.load(best_model_path, map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model_state_dict"])

    test_loss, test_acc, test_prec, test_rec, test_f1 = evaluate(
        model, test_loader, criterion, device)

    print(f"  Accuracy  : {test_acc:.4f}")
    print(f"  Precision : {test_prec:.4f}")
    print(f"  Recall    : {test_rec:.4f}")
    print(f"  F1-score  : {test_f1:.4f}")
    print(f"  Loss      : {test_loss:.4f}")
    print(f"\nBest model saved to: {best_model_path}")

    # Save training results
    results = {
        "model_path": best_model_path,
        "total_params": total_params,
        "best_val_f1": round(best_val_f1, 4),
        "test_metrics": {
            "accuracy": round(test_acc, 4),
            "precision": round(test_prec, 4),
            "recall": round(test_rec, 4),
            "f1_score": round(test_f1, 4),
            "loss": round(test_loss, 4),
        },
        "data": {
            "lots": lots or ["PUC", "UFPR04", "UFPR05"],
            "weathers": weathers or ["Sunny", "Cloudy", "Rainy"],
            "train_size": len(splits["train"]["labels"]),
            "val_size": len(splits["val"]["labels"]),
            "test_size": len(splits["test"]["labels"]),
        },
        "hyperparameters": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.lr,
            "input_size": 64,
        },
    }

    results_path = os.path.join(args.output_dir, "training_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Training results saved to: {results_path}")


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Train CNN slot classifier on PKLotSegmented data")

    parser.add_argument("--pklot-root", type=str,
                        default="dataset/PKLot/PKLotSegmented",
                        help="Root directory of PKLotSegmented")
    parser.add_argument("--lots", type=str, nargs="+",
                        default=None,
                        help="Parking lots to train on (default: all)")
    parser.add_argument("--weathers", type=str, nargs="+",
                        default=None,
                        help="Weather conditions (default: all)")
    parser.add_argument("--max-per-class", type=int, default=0,
                        help="Max images per class, 0=all (for quick tests)")
    parser.add_argument("--output-dir", type=str, default="models",
                        help="Directory to save model checkpoints")

    parser.add_argument("--epochs", type=int, default=30,
                        help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=64,
                        help="Training batch size")
    parser.add_argument("--lr", type=float, default=1e-3,
                        help="Initial learning rate")
    parser.add_argument("--patience", type=int, default=7,
                        help="Early stopping patience (epochs)")
    parser.add_argument("--workers", type=int, default=4,
                        help="DataLoader worker threads")

    parser.add_argument("--device", type=str, default="cpu",
                        help="Device: 'cpu' or 'cuda'")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    parser.add_argument("--resume", type=str, default=None,
                        help="Path to checkpoint to resume training from")

    args = parser.parse_args()
    train(args)
