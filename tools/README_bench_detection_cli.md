# Bench Detection CLI Tool

A comprehensive CLI tool for testing all bench detection configurations and displaying results using term_image.

## Features

- **Multiple Detection Backends**: Tests Roboflow (local/cloud), Ultralytics (local/cloud), and Multi-model detection
- **Visual Results**: Displays annotated images directly in the terminal using term_image
- **Bounding Box & Polygon Support**: Shows both bounding boxes and segmentation polygons
- **Flexible Configuration**: Choose which detection methods to test
- **Detailed Output**: Shows confidence scores, inference times, and detection statistics

## Usage

### Basic Usage

```bash
# Test all configurations with default image (test_data/image.png)
python tools/bench_detection_cli.py

# Test with custom image
python tools/bench_detection_cli.py path/to/your/image.jpg

# Test specific configurations only
python tools/bench_detection_cli.py --configs roboflow-local ultralytics-local

# Save annotated images to specific directory
python tools/bench_detection_cli.py --output-dir ./results

# Skip terminal display (just save images)
python tools/bench_detection_cli.py --no-display
```

### Using the Wrapper Script

```bash
# Use the convenient wrapper script
python bin/bench_detection_test

# With custom image
python bin/bench_detection_test path/to/your/image.jpg
```

## Available Configurations

- **`roboflow-local`**: Roboflow local inference using YOLOv8n
- **`roboflow-cloud`**: Roboflow cloud API using streetview-benches model
- **`ultralytics-local`**: Ultralytics local YOLO11-seg inference
- **`ultralytics-cloud`**: Ultralytics cloud API
- **`multi-model`**: Multi-model detection with fallback logic

## Output

The tool provides:

1. **Real-time Progress**: Shows which configurations are being tested
2. **Detection Results**: Lists found benches with confidence scores
3. **Visual Display**: Shows annotated images in terminal (if supported)
4. **Summary Statistics**: Reports success/failure rates
5. **Saved Images**: Annotated images saved to output directory

## Example Output

```
🖼️  Loading image: test_data/image.png
📁 Output directory: /tmp/bench_detection_xyz

🔧 Testing Roboflow Local Inference...
[Roboflow Local] Found 2 bench detection(s) using RoboflowClient (yolov8n-640):
  Max confidence: 0.85
  1. bench (confidence: 0.85)
  2. bench (confidence: 0.72)

☁️  Testing Roboflow Cloud API...
[Roboflow Cloud] Found 1 bench detection(s) using RoboflowClient (streetview-benches-m4bc5/1):
  Max confidence: 0.91
  1. bench (confidence: 0.91)

🚀 Testing Ultralytics Local Inference...
[Ultralytics Local] Found 1 bench detection(s) using UltralyticsClient (yolo11n-seg.pt):
  Max confidence: 0.78
  Inference time: 2.145s
  1. bench (confidence: 0.78)

================================================================================
📊 SUMMARY
================================================================================
✅ Successful: 3/5
  - Roboflow Local
  - Roboflow Cloud  
  - Ultralytics Local

❌ Failed: 2
  - Ultralytics Cloud
  - Multi-Model

📁 All annotated images saved to: /tmp/bench_detection_xyz
```

## Requirements

- Python 3.8+
- All dependencies from `requirements.txt`
- Valid API keys for cloud services (optional)
- Terminal with image display support (for visual output)

## Notes

- **Local Inference**: Requires appropriate model files and dependencies
- **Cloud APIs**: Require valid API keys in environment variables
- **Image Display**: Works best in terminals that support term_image (iTerm2, Warp, etc.)
- **Performance**: Local inference is typically faster than cloud APIs
- **Accuracy**: Different models may have varying accuracy for different image types

## Troubleshooting

- **"No module named 'inference'"**: Local Roboflow inference not available, will fall back to cloud
- **"HTTP 413"**: Image too large for cloud API, try resizing
- **"API key required"**: Set appropriate environment variables for cloud services
- **Image display issues**: Use `--no-display` to skip terminal visualization
