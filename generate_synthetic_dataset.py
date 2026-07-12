"""
Synthetic Dataset Generator - TBS Deteksi
==========================================
Generate dummy TBS images untuk test training pipeline tanpa download dataset asli.

Output: dataset/ dengan 5 kelas, 50 gambar synthetic per kelas (total 250 images).

Usage:
    python generate_synthetic_dataset.py
    
Note: Model dari synthetic data akurasinya rendah (random pattern), 
      tapi cukup untuk verify training pipeline & deployment workflow.

Updated: 2026-07-12 11:05 UTC
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUTPUT_DIR = "dataset"
IMAGES_PER_CLASS = 50
IMG_SIZE = (224, 224)

CLASS_INFO = {
    "mentah": {
        "color": (220, 38, 38),      # Red
        "pattern": "solid"
    },
    "kurang_matang": {
        "color": (217, 119, 6),      # Orange
        "pattern": "gradient"
    },
    "matang": {
        "color": (22, 163, 74),      # Green
        "pattern": "circle"
    },
    "terlalu_matang": {
        "color": (234, 88, 12),      # Dark orange
        "pattern": "stripe"
    },
    "busuk": {
        "color": (107, 33, 168),     # Purple
        "pattern": "noise"
    }
}

def create_solid(img_array, color):
    """Solid color with noise"""
    img_array[:] = color
    noise = np.random.randint(-30, 30, img_array.shape)
    img_array[:] = np.clip(img_array + noise, 0, 255)

def create_gradient(img_array, color):
    """Vertical gradient"""
    for i in range(IMG_SIZE[0]):
        factor = i / IMG_SIZE[0]
        row_color = tuple(int(c * factor) for c in color)
        img_array[i, :] = row_color
    noise = np.random.randint(-20, 20, img_array.shape)
    img_array[:] = np.clip(img_array + noise, 0, 255)

def create_circle(img_array, color):
    """Circle pattern"""
    img = Image.fromarray(img_array.astype('uint8'))
    draw = ImageDraw.Draw(img)
    
    cx, cy = IMG_SIZE[0] // 2, IMG_SIZE[1] // 2
    radius = np.random.randint(50, 100)
    
    draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), 
                 fill=color, outline=(255, 255, 255), width=3)
    
    return np.array(img)

def create_stripe(img_array, color):
    """Horizontal stripes"""
    stripe_height = 20
    for i in range(0, IMG_SIZE[0], stripe_height):
        if (i // stripe_height) % 2 == 0:
            img_array[i:i+stripe_height, :] = color
        else:
            img_array[i:i+stripe_height, :] = tuple(c // 2 for c in color)
    noise = np.random.randint(-20, 20, img_array.shape)
    img_array[:] = np.clip(img_array + noise, 0, 255)

def create_noise(img_array, color):
    """Random noise pattern"""
    base = np.array(color)
    noise = np.random.randint(-100, 100, img_array.shape)
    img_array[:] = np.clip(base + noise, 0, 255)

def generate_image(class_name, class_info, index):
    """Generate single synthetic image"""
    img_array = np.zeros(IMG_SIZE + (3,), dtype=np.uint8)
    color = class_info["color"]
    pattern = class_info["pattern"]
    
    if pattern == "solid":
        create_solid(img_array, color)
    elif pattern == "gradient":
        create_gradient(img_array, color)
    elif pattern == "circle":
        img_array = create_circle(img_array, color)
    elif pattern == "stripe":
        create_stripe(img_array, color)
    elif pattern == "noise":
        create_noise(img_array, color)
    
    # Add class label text
    img = Image.fromarray(img_array)
    draw = ImageDraw.Draw(img)
    
    try:
        # Try to use default font
        draw.text((10, 10), class_name.upper(), fill=(255, 255, 255))
    except:
        pass
    
    return img

def main():
    print("="*60)
    print("  SYNTHETIC DATASET GENERATOR")
    print("="*60)
    print(f"\nGenerating {IMAGES_PER_CLASS} images per class...")
    print(f"Output: {OUTPUT_DIR}/\n")
    
    # Create directories
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(exist_ok=True)
    
    for class_name in CLASS_INFO.keys():
        class_path = output_path / class_name
        class_path.mkdir(exist_ok=True)
    
    # Generate images
    total = 0
    for class_name, class_info in CLASS_INFO.items():
        print(f"  Generating {class_name}...", end=" ")
        
        class_path = output_path / class_name
        
        for i in range(IMAGES_PER_CLASS):
            img = generate_image(class_name, class_info, i)
            
            # Add random variations
            if np.random.rand() > 0.5:
                # Random rotation
                img = img.rotate(np.random.randint(-15, 15))
            
            if np.random.rand() > 0.5:
                # Random brightness
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(np.random.uniform(0.8, 1.2))
            
            filename = f"{class_name}_{i:04d}.jpg"
            img.save(class_path / filename, quality=85)
            total += 1
        
        print(f"✓ {IMAGES_PER_CLASS} images")
    
    print(f"\n✓ Total: {total} synthetic images generated")
    print("\nDataset structure:")
    for class_name in CLASS_INFO.keys():
        count = len(list((output_path / class_name).glob("*.jpg")))
        print(f"  {class_name:20s}: {count} images")
    
    print("\n" + "="*60)
    print("  Next: python train_model_tbs.py")
    print("="*60)
    print("\nNote: Model trained on synthetic data will have low accuracy")
    print("      Use real dataset for production model.")

if __name__ == "__main__":
    main()
