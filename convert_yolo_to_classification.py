"""
Convert Roboflow YOLO/Object Detection → Classification Dataset
================================================================

Script ini mengubah dataset object detection (bounding box) menjadi
dataset classification dengan cara:
1. Parse YOLO annotations atau COCO JSON
2. Crop gambar berdasarkan bounding box TBS
3. Simpan crop ke folder klasifikasi

Dataset Input (Roboflow):
  raw_data/
  ├── images/
  │   ├── IMG_0001.jpg
  │   └── ...
  ├── labels/
  │   ├── IMG_0001.txt (YOLO format)
  │   └── ...
  └── data.yaml (YOLO config)

Atau COCO format:
  annotations.json

Dataset Output (Classification):
  dataset/
  ├── mentah/
  ├── kurang_matang/
  ├── matang/
  ├── terlalu_matang/
  └── busuk/

Usage:
    python convert_yolo_to_classification.py --input raw_data --output dataset --crop
    python convert_yolo_to_classification.py --input annotations.json --output dataset

Updated: 2026-07-12 11:30 UTC
"""

import os
import sys
import json
import argparse
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

# Suppress verbose warnings
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

def parse_yolo_label(label_path, img_width, img_height):
    """Parse YOLO format label file (single class assumed)"""
    boxes = []
    try:
        with open(label_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    # YOLO: class x_center y_center width height (normalized 0-1)
                    class_id = int(parts[0])
                    x_center = float(parts[1]) * img_width
                    y_center = float(parts[2]) * img_height
                    width = float(parts[3]) * img_width
                    height = float(parts[4]) * img_height
                    
                    # Convert to x1, y1, x2, y2
                    x1 = int(max(0, x_center - width/2))
                    y1 = int(max(0, y_center - height/2))
                    x2 = int(min(img_width, x_center + width/2))
                    y2 = int(min(img_height, y_center + height/2))
                    
                    boxes.append((class_id, x1, y1, x2, y2))
    except Exception as e:
        pass
    
    return boxes

def parse_coco_annotations(json_path):
    """Parse COCO JSON annotations"""
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    annotations = {}
    images = {img['id']: img for img in data['images']}
    
    for ann in data['annotations']:
        img_id = ann['image_id']
        if img_id not in annotations:
            annotations[img_id] = []
        
        bbox = ann['bbox']  # COCO: x, y, width, height
        annotations[img_id].append({
            'x': int(bbox[0]),
            'y': int(bbox[1]),
            'w': int(bbox[2]),
            'h': int(bbox[3])
        })
    
    return images, annotations

def crop_image_to_class(img_path, boxes, output_folders, class_mapping, max_crops=10):
    """
    Crop image to multiple regions, assign to classes
    
    Args:
        img_path: Path to original image
        boxes: List of (class_id, x1, y1, x2, y2)
        output_folders: Dict mapping class_id to output folder path
        class_mapping: Dict mapping class_id to class_name
        max_crops: Maximum number of crops per image
    
    Returns:
        Number of crops created
    """
    if not boxes:
        return 0
    
    try:
        img = cv2.imread(str(img_path))
        if img is None:
            return 0
        
        crops_created = 0
        crop_idx = 0
        
        for class_id, x1, y1, x2, y2 in boxes:
            if crop_idx >= max_crops:
                break
            
            # Get class name
            class_name = class_mapping.get(class_id, f"class_{class_id}")
            output_folder = output_folders.get(class_name)
            
            if not output_folder:
                continue
            
            # Crop
            crop = img[y1:y2, x1:x2]
            
            if crop.size == 0:
                continue
            
            # Save crop
            filename = f"{class_name}_{Path(img_path).stem}_{crop_idx:02d}.jpg"
            output_path = Path(output_folder) / filename
            cv2.imwrite(str(output_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            crops_created += 1
            crop_idx += 1
        
        return crops_created
    
    except Exception as e:
        print(f"  Error processing {img_path}: {e}")
        return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='Input folder (YOLO) or JSON (COCO)')
    parser.add_argument('--output', required=True, help='Output dataset folder')
    parser.add_argument('--crop', action='store_true', help='Crop images to bounding boxes')
    parser.add_argument('--max-crops', type=int, default=10, help='Max crops per image')
    parser.add_argument('--class-mapping', type=str, default=None, 
                       help='Class mapping JSON (class_id -> class_name)')
    args = parser.parse_args()
    
    # Class mapping: Roboflow label IDs → TBS classes
    DEFAULT_CLASS_MAPPING = {
        0: 'mentah',  # Unripe
        1: 'kurang_matang',  # Underripe
        2: 'matang',  # Ripe
        3: 'terlalu_matang',  # Overripe
        4: 'busuk',  # Rotten/Abnormal
        5: 'busuk',  # Empty Bunch (map to busuk)
    }
    
    if args.class_mapping and os.path.exists(args.class_mapping):
        with open(args.class_mapping, 'r') as f:
            class_mapping = json.load(f)
    else:
        class_mapping = DEFAULT_CLASS_MAPPING
    
    # Create output folders
    output_path = Path(args.output)
    output_path.mkdir(exist_ok=True)
    
    class_names = list(set(class_mapping.values()))
    for cls in class_names:
        (output_path / cls).mkdir(exist_ok=True)
    
    output_folders = {cls: str(output_path / cls) for cls in class_names}
    
    # Detect input type
    input_path = Path(args.input)
    
    if args.input.endswith('.json'):
        # COCO format
        print("[1/3] Loading COCO annotations...")
        images, annotations = parse_coco_annotations(args.input)
        
        print(f"[2/3] Processing {len(images)} images...")
        total_crops = 0
        
        for img_id, img_info in images.items():
            img_path = input_path.parent / 'images' / img_info['file_name']
            
            if not img_path.exists():
                continue
            
            boxes = annotations.get(img_id, [])
            
            if args.crop and boxes:
                crops = crop_image_to_class(
                    img_path, boxes, output_folders, class_mapping, args.max_crops
                )
                total_crops += crops
                print(f"  {img_info['file_name']}: {len(boxes)} boxes → {crops} crops")
            else:
                # Save full image (fallback)
                for cls in class_names:
                    crop_filename = f"{cls}_{Path(img_path).stem}_full.jpg"
                    crop_path = Path(output_folders[cls]) / crop_filename
                    if not crop_path.exists():
                        os.system(f'copy "{img_path}" "{crop_path}"')
                        total_crops += 1
                        break  # Only copy to one folder
        
        print(f"\n✓ Total crops: {total_crops}")
    
    elif input_path.is_dir():
        # YOLO format: images/ + labels/
        print("[1/3] Processing YOLO format...")
        
        images_dir = input_path / 'images'
        labels_dir = input_path / 'labels'
        
        if not images_dir.exists():
            print("ERROR: images/ folder not found!")
            return
        
        image_files = list(images_dir.glob('*.jpg')) + list(images_dir.glob('*.jpeg')) + list(images_dir.glob('*.png'))
        
        print(f"[2/3] Processing {len(image_files)} images...")
        total_crops = 0
        
        for img_path in image_files:
            label_path = labels_dir / (img_path.stem + '.txt')
            
            if label_path.exists():
                # Parse YOLO label
                boxes = parse_yolo_label(
                    label_path, 
                    img_info.get('width', 1024), 
                    img_info.get('height', 1024)
                )
                
                if args.crop and boxes:
                    # Get image dimensions
                    try:
                        pil_img = Image.open(img_path)
                        img_width, img_height = pil_img.size
                        boxes = parse_yolo_label(label_path, img_width, img_height)
                    except:
                        boxes = []
                
                if args.crop and boxes:
                    crops = crop_image_to_class(
                        img_path, boxes, output_folders, class_mapping, args.max_crops
                    )
                    total_crops += crops
                    print(f"  {img_path.name}: {len(boxes)} boxes → {crops} crops")
                else:
                    # Save full image
                    for cls in class_names:
                        crop_filename = f"{cls}_{img_path.stem}_full.jpg"
                        crop_path = Path(output_folders[cls]) / crop_filename
                        if not crop_path.exists():
                            os.system(f'copy "{img_path}" "{crop_path}"')
                            total_crops += 1
                            break
            else:
                # No label file, skip or save as fallback
                for cls in class_names:
                    crop_filename = f"{cls}_{img_path.stem}_unknown.jpg"
                    crop_path = Path(output_folders[cls]) / crop_filename
                    if not crop_path.exists():
                        os.system(f'copy "{img_path}" "{crop_path}"')
                        total_crops += 1
                        break
        
        print(f"\n✓ Total crops: {total_crops}")
    
    else:
        print(f"ERROR: Unknown input format: {args.input}")
        return
    
    # Summary
    print("\n" + "="*60)
    print("  DATASET CONVERSION COMPLETE!")
    print("="*60)
    print(f"\nOutput: {output_path}")
    print("Dataset structure:")
    
    for cls in class_names:
        cls_path = output_path / cls
        if cls_path.exists():
            count = len(list(cls_path.glob('*.*')))
            print(f"  {cls:20s}: {count:5d} images")
    
    print("\n" + "="*60)
    print("  Next: python train_model_tbs.py")
    print("="*60)

if __name__ == "__main__":
    main()
