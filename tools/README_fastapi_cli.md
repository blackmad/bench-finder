# FastAPI CLI Tool

A comprehensive command-line interface for testing the Bench Finder FastAPI server.

## Features

- 🏥 **Health Check**: Verify server status and connectivity
- 🎲 **Random Bench**: Get a randomly selected bench with optional image display
- 🎯 **Closest Benches**: Find benches closest to specific coordinates
- 📋 **List Benches**: Browse benches with pagination and filtering
- 🗺️ **Bounding Box Search**: Search for benches within geographic boundaries
- 🔍 **Search History**: View completed search operations
- ⚙️ **Configuration**: View server settings and API information
- 🖼️ **Image Display**: View bench images with detection annotations

## Installation

The CLI tool requires the following Python packages:
- `requests` - For HTTP requests to the FastAPI server
- `PIL` (Pillow) - For image processing
- `term-image` - For terminal image display

Install dependencies:
```bash
pip install requests pillow term-image
```

## Usage

### Basic Commands

```bash
# Check server health
python tools/fastapi_cli.py health

# Get server configuration
python tools/fastapi_cli.py config

# Show API information
python tools/fastapi_cli.py info
```

### Random Bench

```bash
# Get a random bench
python tools/fastapi_cli.py random

# Get random bench with images
python tools/fastapi_cli.py random --show-images

# Get random bench with detection annotations
python tools/fastapi_cli.py random --show-images --show-annotations

# Get random bench with lower confidence threshold
python tools/fastapi_cli.py random --min-confidence 0.6
```

### Closest Benches

```bash
# Find closest benches to Amsterdam
python tools/fastapi_cli.py closest 52.3676 4.9041

# Find 5 closest benches with images
python tools/fastapi_cli.py closest 52.3676 4.9041 --limit 5 --show-images

# Find closest benches with high confidence
python tools/fastapi_cli.py closest 52.3676 4.9041 --min-confidence 0.9
```

### List Benches

```bash
# List first page of benches
python tools/fastapi_cli.py list

# List benches sorted by confidence
python tools/fastapi_cli.py list --sort-by confidence

# List benches with images
python tools/fastapi_cli.py list --show-images

# List benches from a specific page
python tools/fastapi_cli.py list --page 2 --page-size 10
```

### Bounding Box Search

```bash
# Search bounding box around Amsterdam
python tools/fastapi_cli.py bbox 52.4 52.3 5.0 4.8

# Search with specific source filter
python tools/fastapi_cli.py bbox 52.4 52.3 5.0 4.8 --source osm

# Search with limit and images
python tools/fastapi_cli.py bbox 52.4 52.3 5.0 4.8 --limit 10 --show-images
```

### Search History

```bash
# List completed searches
python tools/fastapi_cli.py searches
```

## Command Options

### Global Options

- `--server URL`: FastAPI server URL (default: http://localhost:8866)

### Common Options

- `--min-confidence FLOAT`: Minimum detection confidence (0.0-1.0, default: 0.8)
- `--mode MODE`: Bench mode - "benches" (detected), "no_bench" (not detected), or "both"
- `--show-images`: Display bench images in terminal
- `--show-annotations`: Show detection annotations with images
- `--clustered`: Use clustered results (default: true)

### List Command Options

- `--page INT`: Page number (0-based, default: 0)
- `--page-size INT`: Items per page (default: 20)
- `--start-lat FLOAT`: Starting latitude for distance sorting
- `--start-lng FLOAT`: Starting longitude for distance sorting
- `--sort-by SORT`: Sort criteria - "distance", "confidence", "images", or "recent"

### Bbox Command Options

- `--source SOURCE`: Filter by data source - "osm" or "mapillary"
- `--limit INT`: Maximum number of results (default: 200)

## Examples

### Quick Start

```bash
# 1. Start the FastAPI server
python api/fastapi_server.py

# 2. Check server health
python tools/fastapi_cli.py health

# 3. Get a random bench with images
python tools/fastapi_cli.py random --show-images

# 4. Find closest benches to your location
python tools/fastapi_cli.py closest 52.3676 4.9041 --limit 5 --show-images
```

### Advanced Usage

```bash
# Find high-confidence benches in a specific area
python tools/fastapi_cli.py bbox 52.4 52.3 5.0 4.8 \
  --min-confidence 0.9 \
  --source osm \
  --show-images \
  --show-annotations

# Browse benches by confidence
python tools/fastapi_cli.py list \
  --sort-by confidence \
  --page-size 10 \
  --show-images

# Find benches without detections
python tools/fastapi_cli.py list --mode no_bench --limit 5
```

## Image Display

The CLI tool can display images directly in the terminal using the `term-image` library. When using `--show-images`:

1. Images are downloaded from the server
2. Combined into a single view (up to 4 images)
3. Displayed in the terminal
4. Automatically cleaned up after display

Detection annotations are shown when using `--show-annotations`:
- Segmentation polygons from Ultralytics
- Bounding boxes from Roboflow
- Confidence scores and detection metadata

## Error Handling

The CLI tool includes comprehensive error handling:

- **Connection Errors**: Clear messages when server is unreachable
- **HTTP Errors**: Detailed error information from the server
- **Image Errors**: Graceful handling of missing or corrupted images
- **Validation Errors**: Input validation with helpful error messages

## Server Requirements

The CLI tool requires the FastAPI server to be running with the following endpoints:

- `/health` - Health check
- `/api/config` - Server configuration
- `/api/info` - API information
- `/api/benches/random` - Random bench
- `/api/benches` - List benches
- `/api/benches/bbox` - Bounding box search
- `/api/searches` - Search history
- `/api/bench/{id}/images` - Bench images
- `/api/image/{id}/segmentation` - Detection data
- `/images/{filename}` - Image serving

## Troubleshooting

### Common Issues

1. **Server not running**: Make sure to start the FastAPI server first
   ```bash
   python api/fastapi_server.py
   ```

2. **Connection refused**: Check the server URL and port
   ```bash
   python tools/fastapi_cli.py --server http://localhost:8866 health
   ```

3. **Image display issues**: Ensure `term-image` is installed
   ```bash
   pip install term-image
   ```

4. **No benches found**: Try lowering the confidence threshold
   ```bash
   python tools/fastapi_cli.py random --min-confidence 0.5
   ```

### Debug Mode

For debugging, you can add verbose output by modifying the client to include more detailed logging.
