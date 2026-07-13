#!/usr/bin/env python3
"""
Merge Roboflow YOLO dataset (Oil Palm Fruit Ripeness) into project dataset/
Maps Roboflow classes to project classes:
  1: Kurang masak      -> kurang_matang
  3: TBS masak         -> matang
  4: TBS mentah        -> mentah
  5: Terlalu masak     -> terlalu_matang
  0: Janjang kosong    -> SKIP (no equivalent)
  2: TBS abnormal      -> SKIP (no equivalent)
  busuk                -> not in Roboflow (keep existing)
"""
import shutil
from pathlib import Path

ROBOFLOW_ROOT = Path(r"C:\Users\ACER\Downloads\Dataset\Oil Palm Fruit Ripeness.v1i.yolov8")
PROJECT_DATASET = Path(r"C:\Users\ACER\Downloads\apk ai tbs\tbs-deteksi\dataset")
SPLITS = ['train', 'valid', 'test']

CLASS_MAP = {
    '1': 'kurang_matang',   # Kurang masak
    '3': 'matang',          # TBS masak
    '4': 'mentah',          # TBS mentah
    '5': 'terlalu_matang',  # Terlalu masak
}

def count_labels(lbl_dir: Path):
    counts = {}
    for f in lbl_dir.glob('*.txt'):
        try:
            line = f.read_text().strip().split('\n')[0]
            if line:
                cls = line.split()[0]
                counts[cls] = counts.get(cls, 0) + 1
        except:
            pass
    return counts

def merge_split(split: str):
    src_img = ROBOFLOW_ROOT / split / 'images'
    src_lbl = ROBOFLOW_ROOT / split / 'labels'
    if not src_img.exists():
        print(f"  {split}: no images folder")
        return 0, 0
    
    copied = 0
    skipped = 0
    
    for img_file in src_img.iterdir():
        if not img_file.is_file():
            continue
        lbl_file = src_lbl / (img_file.stem + '.txt')
        if not lbl_file.exists():
            skipped += 1
            continue
        
        try:
            first_line = lbl_file.read_text().strip().split('\n')[0]
            if not first_line:
                skipped += 1
                continue
            cls_idx = first_line.split()[0]
        except:
            skipped += 1
            continue
        
        if cls_idx not in CLASS_MAP:
            skipped += 1
            continue
        
        target_folder = CLASS_MAP[cls_idx]
        dst_folder = PROJECT_DATASET / target_folder
        dst_folder.mkdir(parents=True, exist_ok=True)
        
        new_name = f"roboflow_{split}_{img_file.name}"
        shutil.copy2(img_file, dst_folder / new_name)
        copied += 1
    
    print(f"  {split}: copied {copied}, skipped {skipped}")
    return copied, skipped

def main():
    print("="*60)
    print("Merging Roboflow dataset -> project dataset/")
    print("="*60)
    print("Class mapping:")
    for k, v in CLASS_MAP.items():
        print(f"  Roboflow class {k} -> {v}")
    print("  Classes 0 (Janjang kosong) & 2 (TBS abnormal) -> SKIP")
    print()
    
    # Show source counts
    for split in SPLITS:
        lbl_dir = ROBOFLOW_ROOT / split / 'labels'
        if lbl_dir.exists():
            counts = count_labels(lbl_dir)
            print(f"Source {split} label counts: {dict(sorted(counts.items()))}")
    
    print()
    for split in SPLITS:
        merge_split(split)
    
    # Final project counts
    print("\nFinal project dataset/ counts:")
    total = 0
    for cls in ['mentah', 'kurang_matang', 'matang', 'terlalu_matang', 'busuk']:
        p = PROJECT_DATASET / cls
        cnt = len(list(p.glob('*'))) if p.exists() else 0
        total += cnt
        print(f"  {cls}: {cnt}")
    print(f"  TOTAL: {total}")

if __name__ == '__main__':
    main()