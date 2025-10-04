#!/usr/bin/env python3
"""
Roboflow Detection CLI Tool
Takes an image and runs bench detection using either local inference (default) or cloud API.
Supports various YOLO models for local inference and displays results in terminal.
"""

import argparse
import sys
import os
from typing import Optional, Dict, Any, List
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from term_image.image import from_file
import tempfile
from roboflow_client import RoboflowClient
from term_image.image import ITerm2Image
from term_image.utils import get_terminal_name_version

if get_terminal_name_version()[0] == "warp":
    ITerm2Image.is_supported = lambda *_: True


def setup_client(use_local: bool = True, model_id: Optional[str] = None) -> RoboflowClient:
    """Initialize RoboflowClient.
    
    Args:
        use_local: Whether to use local inference (default: True)
        model_id: Model ID to use (optional)
    """
    try:
        client = RoboflowClient(use_local_inference=use_local, model_id=model_id)
        return client
    except ValueError as e:
        print(f"Error: {e}")
        if not use_local:
            print("Please ensure ROBOFLOW_API_KEY is set in your config.py or environment.")
        sys.exit(1)


def run_inference(client: RoboflowClient, image_path: str) -> Dict[str, Any]:
    """Run inference on the image using RoboflowClient."""
    try:
        result = client.detect_benches_in_image(image_path)
        if not result['success']:
            print(f"Error running inference: {result.get('error', 'Unknown error')}")
            sys.exit(1)
        return result
    except Exception as e:
        print(f"Error running inference: {e}")
        sys.exit(1)


def render_detections(image_path: str, result: Dict[str, Any], model_name: str = "Model") -> Image.Image:
    """Draw bounding boxes on the image based on RoboflowClient results."""
    # Load the original image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image from {image_path}")
        sys.exit(1)
    
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(image)
    draw = ImageDraw.Draw(pil_image)
    
    # Try to load a font (fallback to default if not available)
    try:
        font = ImageFont.truetype("Arial.ttf", 16)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 16)
        except (OSError, IOError):
            font = ImageFont.load_default()
    
    # Colors for different classes
    colors = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
        (255, 0, 255), (0, 255, 255), (128, 0, 0), (0, 128, 0)
    ]
    
    # Extract detections from RoboflowClient result format
    detections = result.get('detections', [])
    bench_count = result.get('bench_count', 0)
    max_confidence = result.get('max_confidence', 0)
    inference_type = result.get('inference_type', 'unknown')
    model_id = result.get('model_id', 'unknown')
    
    print(f"\n[{model_name}] Found {bench_count} bench detection(s) using {inference_type} inference ({model_id}):")  
    if bench_count > 0:
        print(f"  Max confidence: {max_confidence:.2f}")
    
    for i, detection in enumerate(detections):
        color = colors[i % len(colors)]
        
        # Extract detection info
        if 'class' in detection:
            class_name = detection['class']
        elif 'class_name' in detection:
            class_name = detection['class_name']
        else:
            class_name = detection.get('label', 'Unknown')
            
        confidence = detection.get('confidence', 0.0)
        
        print(f"  {i+1}. {class_name} (confidence: {confidence:.2f})")
        
        # Handle bounding box detection
        if 'x' in detection and 'y' in detection and 'width' in detection and 'height' in detection:
            x, y, w, h = detection['x'], detection['y'], detection['width'], detection['height']
            
            # Convert center coordinates to corner coordinates
            x1 = int(x - w/2)
            y1 = int(y - h/2)
            x2 = int(x + w/2)
            y2 = int(y + h/2)
            
            # Draw bounding box
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            
            # Draw label
            label = f"{class_name} {confidence:.2f}"
            bbox = draw.textbbox((x1, y1-25), label, font=font)
            draw.rectangle([bbox[0]-2, bbox[1]-2, bbox[2]+2, bbox[3]+2], fill=color)
            draw.text((x1, y1-25), label, fill=(255, 255, 255), font=font)
        
        # Handle segmentation masks (if available)
        elif 'points' in detection:
            points = detection['points']
            if points:
                # Convert points to tuples for PIL
                polygon_points = [(point['x'], point['y']) for point in points]
                
                # Draw segmentation mask
                draw.polygon(polygon_points, outline=color, width=3)
                
                # Draw label at centroid
                if polygon_points:
                    cx = sum(p[0] for p in polygon_points) / len(polygon_points)
                    cy = sum(p[1] for p in polygon_points) / len(polygon_points)
                    
                    label = f"{class_name} {confidence:.2f}"
                    bbox = draw.textbbox((cx-50, cy-10), label, font=font)
                    draw.rectangle([bbox[0]-2, bbox[1]-2, bbox[2]+2, bbox[3]+2], fill=color)
                    draw.text((cx-50, cy-10), label, fill=(255, 255, 255), font=font)
    return pil_image

def draw_detections(image_path: str, result: Dict[str, Any], output_path: str, model_name: str = "Model") -> None:
    pil_image = render_detections(image_path, result, model_name)
    # Save the annotated image
    pil_image.save(output_path)
    print(f"\nAnnotated image saved to: {output_path}")

def display_image_in_terminal(image_path: str, model_name: str = "Model") -> None:
    """Display the image directly in the terminal using term-image."""
    try:
        img = from_file(image_path)
        print("\n" + "="*60)
        print(f"DETECTION RESULTS - {model_name}:")
        print("="*60)
        print(img)
        print("="*60)
    except Exception as e:
        print(f"Error displaying image in terminal: {e}")
        print(f"Annotated image available at: {image_path}")




def main():
    parser = argparse.ArgumentParser(
        description="Run Roboflow bench detection on an image and display results in terminal"
    )
    parser.add_argument("image_path", help="Path to the input image")
    parser.add_argument("--output-dir", help="Directory to save annotated images (default: temporary directory)")
    parser.add_argument("--no-display", action="store_true", help="Don't display images in terminal")
    parser.add_argument("--cloud", action="store_true", help="Use cloud API instead of local inference")
    parser.add_argument("-m", "--model-id", help="Specific model ID to use (e.g., 'yolov8n-640', 'yolov8s-640')")
    parser.add_argument("--cache-info", action="store_true", help="Show model cache information")
    
    args = parser.parse_args()
    
    # Validate input image
    if not os.path.exists(args.image_path):
        print(f"Error: Image file '{args.image_path}' not found.")
        sys.exit(1)
    
    print(f"Loading image: {args.image_path}")
    
    # Determine inference type
    use_local = not args.cloud
    inference_type = "local" if use_local else "cloud"
    model_info = f" with model {args.model_id}" if args.model_id else ""
    print(f"Using {inference_type} inference{model_info}...")
    
    # Setup RoboflowClient
    client = setup_client(use_local=use_local, model_id=args.model_id)
    
    # Run inference
    print("Running bench detection...")
    result = run_inference(client, args.image_path)
    
    # Prepare output path
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(args.image_path))[0]
        output_path = os.path.join(args.output_dir, f"{base_name}_bench_detection.jpg")
    else:
        temp_dir = tempfile.gettempdir()
        base_name = os.path.splitext(os.path.basename(args.image_path))[0]
        output_path = os.path.join(temp_dir, f"{base_name}_bench_detection.jpg")
    
    # Draw detections
    draw_detections(args.image_path, result, output_path, "Bench Detection")
    
    if not args.no_display:
        display_image_in_terminal(output_path, "Bench Detection")
    else:
        print(f"Annotated image saved to: {output_path}")


if __name__ == "__main__":
    main()