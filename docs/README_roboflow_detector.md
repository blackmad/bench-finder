# Roboflow Detection CLI Tool

A command-line tool that runs Roboflow inference on images and displays the results with bounding boxes or segmentation masks directly in your Warp terminal.

## Features

- **Multiple Model Support**: Run inference with one or multiple Roboflow models for comparison
- **Terminal Display**: View annotated images directly in Warp terminal using Kitty graphics protocol
- **Flexible Output**: Save annotated images to custom directories or temporary files
- **Both Detection Types**: Supports both bounding box detection and segmentation masks
- **Environment Integration**: Uses dotenv for API key management

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your Roboflow API key:
```bash
cp .env.example .env
# Edit .env and add your ROBOFLOW_API_KEY
```

## Usage

### Single Model
```bash
python roboflow_detector.py path/to/image.jpg your-model-name
```

### Multiple Models
```bash
python roboflow_detector.py path/to/image.jpg model1 model2 model3
```

### Advanced Options
```bash
python roboflow_detector.py path/to/image.jpg model-name \
  --workspace your-workspace \
  --confidence 0.6 \
  --output-dir ./results \
  --no-display
```

## Arguments

- `image_path`: Path to the input image
- `models`: One or more Roboflow model names (e.g., 'workspace/project' or just 'project')

### Optional Arguments

- `--api-key`: Roboflow API key (or set ROBOFLOW_API_KEY env var)
- `--workspace`: Roboflow workspace name (if not included in model_name)
- `--confidence`: Confidence threshold (default: 0.4)
- `--output-dir`: Directory to save annotated images (default: temporary directory)
- `--no-display`: Don't display images in terminal

## Examples

### Object Detection
```bash
python roboflow_detector.py photo.jpg microsoft-coco/1
```

### Multiple Model Comparison
```bash
python roboflow_detector.py street_scene.jpg \
  workspace/traffic-signs \
  workspace/vehicles \
  workspace/pedestrians \
  --confidence 0.5 \
  --output-dir ./comparison_results
```

### Custom Workspace
```bash
python roboflow_detector.py image.jpg my-model \
  --workspace my-workspace \
  --confidence 0.7
```

## Output

- **Terminal Display**: Annotated images are displayed directly in Warp terminal
- **Text Summary**: Detection results with class names and confidence scores
- **Saved Images**: Annotated images saved with model names in filenames

For multiple models, each model's results are displayed separately with clear headers, and a final summary shows all output file locations.

## Model Name Formats

- `project-name` - Uses default workspace
- `workspace/project-name` - Specifies workspace and project
- Use `--workspace` flag if workspace is not in the model name

## Requirements

- Warp terminal (for image display)
- Roboflow account and API key
- Python 3.7+
- Required packages (see requirements.txt)
