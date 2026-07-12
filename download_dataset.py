"""
Dataset Downloader - TBS Kelapa Sawit
======================================

Script untuk download dataset dari Kaggle/Mendeley dan ekstrak otomatis.

Setup (run ONCE):
1. pip install kaggle
2. Download API key dari https://www.kaggle.com/settings/account
3. Copy ke ~/.kaggle/kaggle.json (Linux/Mac) atau C:\\Users\\YOUR_USER\\.kaggle\\kaggle.json (Windows)

Usage:
  python download_dataset.py --source kaggle
  python download_dataset.py --source mendeley
"""
import os
import sys
import subprocess
from pathlib import Path

DATASETS = {
    "kaggle": {
        "id": "kunals99/outdoor-oil-palm-fruit-ripeness-dataset",
        "name": "Outdoor Oil Palm Fruit Ripeness Dataset (Kaggle)",
        "classes": 5,
        "images": 5000
    },
    "mendeley": {
        "url": "https://data.mendeley.com/datasets/424y96m6sw/1",
        "name": "Ordinal Dataset for Ripeness (Mendeley)",
        "note": "Manual download required (lihat instruksi di bawah)"
    }
}

def download_from_kaggle(dataset_id):
    print(f"\n[*] Downloading from Kaggle: {dataset_id}")
    print("[!] Pastikan Kaggle API sudah ter-setup")
    print("    https://www.kaggle.com/settings/account → Download API key → Copy ke ~/.kaggle/kaggle.json\n")
    
    try:
        result = subprocess.run(
            ["kaggle", "datasets", "download", "-d", dataset_id, "-p", "dataset_raw/"],
            capture_output=True, text=True, timeout=600
        )
        
        if result.returncode == 0:
            print("✓ Download OK")
            extract_kaggle_zip()
            return True
        else:
            print(f"✗ Error: {result.stderr}")
            return False
    except FileNotFoundError:
        print("✗ kaggle CLI not found. Run: pip install kaggle")
        return False
    except subprocess.TimeoutExpired:
        print("✗ Download timeout")
        return False

def extract_kaggle_zip():
    print("[*] Extracting dataset...")
    import zipfile
    
    dataset_dir = Path("dataset_raw")
    dataset_dir.mkdir(exist_ok=True)
    
    for zip_file in dataset_dir.glob("*.zip"):
        print(f"  Extracting {zip_file.name}...")
        with zipfile.ZipFile(zip_file, 'r') as z:
            z.extractall(dataset_dir)
        zip_file.unlink()
    
    print("✓ Extraction complete")

def organize_dataset():
    """Reorganize downloaded dataset ke struktur training yang benar."""
    print("\n[*] Organizing dataset structure...")
    
    CLASS_MAPPING = {
        # Mapping dari berbagai nama folder ke 5 kelas standard
        "unripe": "mentah",
        "immature": "mentah",
        "underripe": "kurang_matang",
        "partially_ripe": "kurang_matang",
        "ripe": "matang",
        "fully_ripe": "matang",
        "overripe": "terlalu_matang",
        "decayed": "busuk",
        "damaged": "busuk",
        "abnormal": "busuk",
        "empty": "busuk",
    }
    
    raw_dir = Path("dataset_raw")
    final_dir = Path("dataset")
    final_dir.mkdir(exist_ok=True)
    
    # Create target folders
    for cls in ["mentah", "kurang_matang", "matang", "terlalu_matang", "busuk"]:
        (final_dir / cls).mkdir(exist_ok=True)
    
    # Move files
    moved = 0
    for src_folder in raw_dir.rglob("*"):
        if not src_folder.is_dir():
            continue
        
        folder_name = src_folder.name.lower().replace(" ", "_")
        target_class = CLASS_MAPPING.get(folder_name)
        
        if not target_class:
            continue
        
        for img_file in src_folder.glob("*.*"):
            if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                dest = final_dir / target_class / img_file.name
                if not dest.exists():
                    import shutil
                    shutil.copy2(img_file, dest)
                    moved += 1
    
    print(f"✓ Moved {moved} images to dataset/")
    print("\nDataset structure:")
    for cls in ["mentah", "kurang_matang", "matang", "terlalu_matang", "busuk"]:
        count = len(list((final_dir / cls).glob("*.*")))
        print(f"  {cls:20s}: {count:5d} images")

def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["kaggle", "mendeley", "roboflow"], 
                        default="kaggle", help="Dataset source")
    args = parser.parse_args()
    
    print("="*60)
    print("  TBS DATASET DOWNLOADER")
    print("="*60)
    
    if args.source == "kaggle":
        dataset_id = DATASETS["kaggle"]["id"]
        success = download_from_kaggle(dataset_id)
        if success:
            organize_dataset()
    
    elif args.source == "mendeley":
        print("\n[!] Mendeley dataset harus di-download manual:")
        print("    1. Kunjungi: https://data.mendeley.com/datasets/424y96m6sw/1")
        print("    2. Klik 'Download' → extract ke folder dataset_raw/")
        print("    3. Run: python download_dataset.py --organize")
    
    elif args.source == "roboflow":
        print("\n[!] Roboflow dataset:")
        print("    1. Kunjungi: https://universe.roboflow.com/achmad-fahri-x6r0k/oil-palm-fruit-ripeness-7r3zr")
        print("    2. Klik 'Download' → pilih 'Folder Structure' → extract ke folder dataset_raw/")
        print("    3. Run: python download_dataset.py --organize")
    
    print("\n" + "="*60)
    print("  Next: python train_model_tbs.py")
    print("="*60)

if __name__ == "__main__":
    main()
