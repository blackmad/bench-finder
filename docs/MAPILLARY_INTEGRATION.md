# Mapillary Integration with Image Downloading

The bench finder now supports Mapillary as a data source for finding benches with automatic image downloading capability.

## Features

- **Bench Detection**: Search for bench detections from Mapillary's computer vision API
- **Image Downloading**: Automatically download high-resolution images of detected benches
- **Database Integration**: Store Mapillary benches alongside OSM data in unified database
- **Web UI Support**: View Mapillary benches in the web interface with source filtering
- **Multiple Image Sizes**: Support for different image resolutions (256px, 1024px, 2048px)

## Setup

1. **Get Mapillary Access Token**:
   - Go to [Mapillary Developer Portal](https://www.mapillary.com/developer)
   - Create an application to get an access token
   - Set the token as an environment variable:
   ```bash
   export MAPILLARY_ACCESS_TOKEN='your_token_here'
   ```

2. **Configure Image Downloading**:
   ```bash
   # Optional: Set image size (default: 2048px)
   export MAPILLARY_IMAGE_SIZE=2048

   # Optional: Enable/disable image downloading (default: true)
   export MAPILLARY_DOWNLOAD_IMAGES=true
   ```

3. **Directory Setup**:
   - Images are downloaded to the `images/` directory by default
   - Mapillary images are prefixed with `mapillary_` for easy identification

## Usage

### Via Web API

Search for Mapillary benches via the REST API:

```bash
# Search for benches around a location
curl -X POST http://localhost:8866/api/mapillary/search \
  -H "Content-Type: application/json" \
  -d '{
    "center_lat": 52.3613577,
    "center_lng": 4.8666322,
    "radius_meters": 1000,
    "limit": 100
  }'

# Get benches filtered by source
curl "http://localhost:8866/api/benches/source/mapillary?min_confidence=0.5"
```

### Via Python

```python
from mapillary_service import MapillaryBenchService

# Initialize service
service = MapillaryBenchService(
    database_path="data/benches.db",
    mapillary_access_token="your_token",
    images_dir="images"
)

# Search and store benches with image downloading
result = service.search_and_store_benches(
    center_lat=52.3613577,
    center_lng=4.8666322,
    radius_meters=1000,
    limit=100
)

print(f"Found {len(result.benches)} benches")
```

### Testing

Run the test script to verify the integration:

```bash
cd /Users/blackmad/bench_finder
python test_mapillary_download.py
```

## Database Schema

Mapillary benches are stored in the unified `benches` table with:

- `provider_id`: Mapillary image ID
- `source`: Set to "mapillary"
- `external_id`: Mapillary image ID
- `tags`: JSON containing Mapillary metadata

Images are stored in the `images` table with:

- `filepath`: Path to downloaded image file
- `filename`: Generated filename (e.g., `mapillary_123456789.jpg`)
- `file_size`: Size of downloaded image in bytes
- `capture_success`: `true` for successful downloads

Detections are stored in the `detections` table with:

- `source`: Set to "mapillary"
- `external_detection_id`: Mapillary detection ID
- `geometry_decoded`: Bench outline/segmentation data (if available)

## Configuration Options

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Access Token | `MAPILLARY_ACCESS_TOKEN` | None | Required for API access |
| Image Size | `MAPILLARY_IMAGE_SIZE` | 2048 | Downloaded image width in pixels |
| Download Images | `MAPILLARY_DOWNLOAD_IMAGES` | true | Whether to download images |
| Images Directory | `IMAGES_DIR` | "images" | Directory to store downloaded images |

## Image Sizes

Mapillary provides multiple thumbnail sizes:

- **256px**: Fast download, lower quality
- **1024px**: Good balance of size and quality
- **2048px**: High quality, larger file size

The system automatically selects the best available size based on your `MAPILLARY_IMAGE_SIZE` setting.

## Web UI Integration

The web interface supports:

- **Source Filtering**: Filter benches by "OSM", "Mapillary", or "Both"
- **Image Display**: View downloaded Mapillary images alongside detection results
- **Confidence Scoring**: Mapillary benches are assigned high confidence (1.0)
- **Distance Calculation**: Shows distance from search center
- **Segmentation**: Mapillary provides geometric outline data for benches

## Performance Considerations

- **Rate Limits**: Mapillary API has rate limits - be mindful when processing large areas
- **Storage**: High-resolution images can consume significant disk space
- **Download Time**: Image downloading adds time to the search process
- **Caching**: Images are cached locally to avoid re-downloading

## Error Handling

The system gracefully handles:

- **Missing Images**: Creates database entries even if image download fails
- **API Limits**: Continues processing other images if some fail
- **Network Issues**: Retries and logs errors for troubleshooting
- **Storage Issues**: Checks disk space and permissions

## Troubleshooting

1. **No benches found**: Check if the area has Mapillary coverage
2. **Download failures**: Verify internet connection and disk space
3. **API errors**: Check access token validity and rate limits
4. **Storage issues**: Ensure images directory is writable

## Example Output

```
🔍 Testing Mapillary bench detection with image downloading...
📍 Location: 52.3613577, 4.8666322
🎯 Radius: 500m
💾 Database: data/benches.db
📁 Images directory: images

✅ Mapillary service initialized successfully

🔍 Searching for benches around 52.3613577, 4.8666322...
📷 Downloaded 8/8 Mapillary images
✅ Successfully committed 8 Mapillary benches

📊 Results:
   Found 8 bench detections
   Total pages: 1
   Total count: 8

🪑 Bench Details:
   1. ID: 123
      Provider ID: 1234567890
      Location: 52.361425, 4.867234
      Source: mapillary
      Confidence: 1.0
      Images: 1
      Image files: mapillary_1234567890.jpg
      Distance: 42m

📷 Downloaded 8 Mapillary images to images
   Sample files: mapillary_1234567890.jpg, mapillary_0987654321.jpg

✅ Test completed successfully!
```
