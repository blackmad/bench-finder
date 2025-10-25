#!/usr/bin/env python3
"""
CLI tool for testing the Bench Finder FastAPI server.

This tool provides various commands to interact with the FastAPI server:
- Get random benches
- Find closest benches to coordinates
- List bench candidates with filtering
- Display images with detection annotations
- Check server health and configuration
"""

import argparse
import builtins
import contextlib
import json
import math
import os
import sys
from typing import Any

import requests
from term_image.image import AutoImage

from bench_finder.display import create_combined_image_display


class FastAPIClient:
    """Client for interacting with the Bench Finder FastAPI server."""

    def __init__(self, base_url: str = "http://localhost:8866"):
        """Initialize the FastAPI client."""
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "BenchFinder-CLI/1.0"})

    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make a request to the FastAPI server."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            print(f"❌ Error: Could not connect to server at {self.base_url}")
            print(
                "   Make sure the FastAPI server is running with: python api/fastapi_server.py"
            )
            sys.exit(1)
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error {e.response.status_code}: {e.response.text}")
            sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"❌ Request Error: {e}")
            sys.exit(1)

    def health_check(self) -> dict[str, Any]:
        """Check server health."""
        return self._make_request("GET", "/health")

    def get_config(self) -> dict[str, Any]:
        """Get server configuration."""
        return self._make_request("GET", "/api/config")

    def get_api_info(self) -> dict[str, Any]:
        """Get API information."""
        return self._make_request("GET", "/api/info")

    def get_random_bench(
        self, min_confidence: float = 0.8, mode: str = "benches"
    ) -> dict[str, Any]:
        """Get a random bench."""
        params = {
            "min_confidence": min_confidence,
            "mode": mode,
        }
        return self._make_request("GET", "/api/benches/random", params=params)

    def get_benches(
        self,
        page: int = 0,
        page_size: int = 20,
        min_confidence: float = 0.8,
        start_lat: float = 52.3613577,
        start_lng: float = 4.8666322,
        sort_by: str = "distance",
        mode: str = "benches",
        clustered: bool = True,
    ) -> dict[str, Any]:
        """Get list of benches."""
        params = {
            "page": page,
            "page_size": page_size,
            "min_confidence": min_confidence,
            "start_lat": start_lat,
            "start_lng": start_lng,
            "sort_by": sort_by,
            "mode": mode,
            "clustered": clustered,
        }
        return self._make_request("GET", "/api/benches", params=params)

    def get_benches_in_bbox(
        self,
        north: float,
        south: float,
        east: float,
        west: float,
        min_confidence: float = 0.8,
        source: str | None = None,
        mode: str = "benches",
        sort_by: str = "distance",
        limit: int = 200,
        clustered: bool = True,
    ) -> dict[str, Any]:
        """Get benches in bounding box."""
        params = {
            "north": north,
            "south": south,
            "east": east,
            "west": west,
            "min_confidence": min_confidence,
            "sort_by": sort_by,
            "mode": mode,
            "limit": limit,
            "clustered": clustered,
        }
        if source:
            params["source"] = source
        return self._make_request("GET", "/api/benches/bbox", params=params)

    def get_bench_images(self, bench_id: int) -> dict[str, Any]:
        """Get images for a specific bench."""
        return self._make_request("GET", f"/api/bench/{bench_id}/images")

    def get_image_segmentation(self, image_id: int) -> dict[str, Any]:
        """Get detection visualization data for an image."""
        return self._make_request("GET", f"/api/image/{image_id}/segmentation")

    def get_searches(self) -> dict[str, Any]:
        """Get list of completed searches."""
        return self._make_request("GET", "/api/searches")

    def download_image(self, filename: str, save_path: str | None = None) -> str:
        """Download an image from the server."""
        url = f"{self.base_url}/images/{filename}"
        try:
            response = self.session.get(url)
            response.raise_for_status()

            if save_path is None:
                save_path = f"downloaded_{filename}"

            with open(save_path, "wb") as f:
                f.write(response.content)

            return save_path
        except requests.exceptions.RequestException as e:
            print(f"❌ Error downloading image {filename}: {e}")
            return ""

    def calculate_distance(
        self, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        """Calculate distance between two points in meters."""
        # Convert decimal degrees to radians
        lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])

        # Haversine formula
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        # Earth's radius in meters
        r = 6371000
        return c * r


def format_bench_info(bench: dict[str, Any], show_images: bool = False) -> str:
    """Format bench information for display."""
    lines = []

    # Basic info
    lines.append(f"🪑 Bench ID: {bench['id']}")
    lines.append(f"📍 Location: {bench['lat']:.6f}, {bench['lng']:.6f}")
    lines.append(f"📊 Source: {bench['source']}")
    lines.append(f"🎯 Detection Type: {bench['detection_type']}")
    lines.append(f"✅ Bench Found: {bench['bench_found']}")

    # Confidence scores
    lines.append(f"🎯 Best Confidence: {bench['best_confidence']:.3f}")
    if bench.get("roboflow_confidence", 0) > 0:
        lines.append(f"   Roboflow: {bench['roboflow_confidence']:.3f}")
    if bench.get("ultralytics_confidence", 0) > 0:
        lines.append(f"   Ultralytics: {bench['ultralytics_confidence']:.3f}")
    if bench.get("mapillary_confidence", 0) > 0:
        lines.append(f"   Mapillary: {bench['mapillary_confidence']:.3f}")

    # Distance
    if "distance_meters" in bench:
        lines.append(
            f"📏 Distance: {bench['distance_meters']}m ({bench['distance_km']:.2f}km)"
        )

    # Images
    lines.append(f"🖼️  Images: {bench['image_count']}")
    if show_images and bench.get("image_filenames"):
        lines.append("   Image files:")
        for filename in bench["image_filenames"][:5]:  # Show first 5
            lines.append(f"     • {filename}")  # noqa: PERF401
        if len(bench["image_filenames"]) > 5:
            lines.append(f"     ... and {len(bench['image_filenames']) - 5} more")

    # Clustering info
    if bench.get("cluster_id"):
        lines.append(f"🔗 Cluster ID: {bench['cluster_id']}")
        lines.append(
            f"   Cluster Center: {bench['cluster_center_lat']:.6f}, {bench['cluster_center_lng']:.6f}"
        )
        lines.append(f"   Benches in Cluster: {bench['cluster_bench_count']}")
        if bench.get("is_cluster_representative"):
            lines.append("   🏆 Representative Bench")

    return "\n".join(lines)


def display_bench_images(
    client: FastAPIClient, bench: dict[str, Any], show_annotations: bool = False
):
    """Display images for a bench."""
    if not bench.get("image_filenames"):
        print("❌ No images available for this bench")
        return

    print(
        f"\n🖼️  Displaying {len(bench['image_filenames'])} images for bench {bench['id']}:"
    )

    # Download and display images
    image_paths = []
    for i, filename in enumerate(bench["image_filenames"][:4]):  # Limit to 4 images
        print(
            f"📥 Downloading image {i+1}/{min(4, len(bench['image_filenames']))}: {filename}"
        )
        local_path = client.download_image(filename)
        if local_path:
            image_paths.append({"filepath": local_path})

    if not image_paths:
        print("❌ Failed to download any images")
        return

    # Create combined display
    combined_image = create_combined_image_display(image_paths, target_width=300)
    if combined_image:
        print("\n📸 Combined image view:")
        print(AutoImage(combined_image))

        # Show annotations if requested and we have detection data
        if show_annotations and bench.get("image_ids"):
            print("\n🔍 Detection annotations:")
            for i, image_id in enumerate(bench["image_ids"][:2]):  # Show first 2
                try:
                    seg_data = client.get_image_segmentation(image_id)
                    print(f"   Image {i+1} (ID: {image_id}):")
                    print(f"     Detection Type: {seg_data['detection_type']}")
                    print(f"     Confidence: {seg_data['confidence_score']:.3f}")
                    print(f"     Segmentation: {seg_data['segmentation_available']}")
                    print(f"     Bounding Box: {seg_data['bounding_box_available']}")
                except Exception as e:
                    print(f"     Error getting detection data: {e}")

    # Clean up downloaded files
    for img_data in image_paths:
        with contextlib.suppress(builtins.BaseException):
            os.remove(img_data["filepath"])


def cmd_health(client: FastAPIClient, args):
    """Health check command."""
    print("🏥 Checking server health...")
    health = client.health_check()
    print(f"✅ Status: {health['status']}")
    print(f"🗄️  Database: {health['database']}")
    print(f"🗺️  Mapillary: {health['mapillary']}")


def cmd_config(client: FastAPIClient, args):
    """Configuration command."""
    print("⚙️  Server Configuration:")
    config = client.get_config()
    print(
        f"📍 Default Location: {config['default_start_lat']:.6f}, {config['default_start_lng']:.6f}"
    )
    print(f"🎯 Default Min Confidence: {config['default_min_confidence']}")
    print(f"📄 Page Size: {config['page_size']}")


def cmd_info(client: FastAPIClient, args):
    """API info command."""
    print("ℹ️  API Information:")
    info = client.get_api_info()
    print(f"📛 Name: {info['name']}")
    print(f"🔢 Version: {info['version']}")
    print(f"📝 Description: {info['description']}")
    print(f"📊 Supported Sources: {', '.join(info['supported_sources'])}")
    print(f"🤖 Detection Models: {', '.join(info['supported_detection_models'])}")
    print(f"✨ Features: {', '.join(info['features'])}")
    print(f"📏 Limits: {json.dumps(info['limits'], indent=2)}")


def cmd_random(client: FastAPIClient, args):
    """Random bench command."""
    print(
        f"🎲 Getting random bench (min_confidence={args.min_confidence}, mode={args.mode})..."
    )
    response = client.get_random_bench(args.min_confidence, args.mode)
    bench = response["bench"]

    print("\n" + "=" * 60)
    print(format_bench_info(bench, show_images=True))
    print("=" * 60)

    if args.show_images:
        display_bench_images(client, bench, show_annotations=args.show_annotations)


def cmd_closest(client: FastAPIClient, args):
    """Closest bench command."""
    print(f"🎯 Finding closest benches to {args.lat}, {args.lng}...")

    # Get benches sorted by distance
    response = client.get_benches(
        page=0,
        page_size=args.limit,
        min_confidence=args.min_confidence,
        start_lat=args.lat,
        start_lng=args.lng,
        sort_by="distance",
        mode=args.mode,
        clustered=args.clustered,
    )

    if "benches" in response:
        benches = response["benches"]
    elif "clustered_benches" in response:
        benches = [
            cluster["representative_bench"] for cluster in response["clustered_benches"]
        ]
    else:
        print("❌ Unexpected response format")
        return

    if not benches:
        print("❌ No benches found")
        return

    print(f"\n📊 Found {len(benches)} benches:")
    print("=" * 80)

    for i, bench in enumerate(benches[: args.limit]):
        print(f"\n{i+1}. {format_bench_info(bench)}")
        if args.show_images and i < 2:  # Show images for first 2 benches
            display_bench_images(client, bench, show_annotations=args.show_annotations)


def cmd_list(client: FastAPIClient, args):
    """List benches command."""
    print(f"📋 Listing benches (page={args.page}, mode={args.mode})...")

    response = client.get_benches(
        page=args.page,
        page_size=args.page_size,
        min_confidence=args.min_confidence,
        start_lat=args.start_lat,
        start_lng=args.start_lng,
        sort_by=args.sort_by,
        mode=args.mode,
        clustered=args.clustered,
    )

    if "benches" in response:
        benches = response["benches"]
        pagination = response["pagination"]
    elif "clustered_benches" in response:
        benches = [
            cluster["representative_bench"] for cluster in response["clustered_benches"]
        ]
        pagination = response["pagination"]
    else:
        print("❌ Unexpected response format")
        return

    print(
        f"\n📊 Page {pagination['page'] + 1} of {pagination['total_pages']} "
        f"({pagination['total_count']} total benches)"
    )
    print("=" * 80)

    for i, bench in enumerate(benches):
        print(f"\n{i+1}. {format_bench_info(bench, show_images=args.show_images)}")
        if args.show_images and i < 2:  # Show images for first 2 benches
            display_bench_images(client, bench, show_annotations=args.show_annotations)


def cmd_bbox(client: FastAPIClient, args):
    """Bounding box search command."""
    print(
        f"🗺️  Searching bounding box: {args.north}N, {args.south}S, {args.east}E, {args.west}W"
    )

    response = client.get_benches_in_bbox(
        north=args.north,
        south=args.south,
        east=args.east,
        west=args.west,
        min_confidence=args.min_confidence,
        source=args.source,
        mode=args.mode,
        sort_by=args.sort_by,
        limit=args.limit,
        clustered=args.clustered,
    )

    if "benches" in response:
        benches = response["benches"]
        total_count = response["total_count"]
    elif "clustered_benches" in response:
        benches = [
            cluster["representative_bench"] for cluster in response["clustered_benches"]
        ]
        total_count = len(benches)
    else:
        print("❌ Unexpected response format")
        return

    print(f"\n📊 Found {len(benches)} benches in bounding box (total: {total_count})")
    print("=" * 80)

    for i, bench in enumerate(benches):
        print(f"\n{i+1}. {format_bench_info(bench, show_images=args.show_images)}")
        if args.show_images and i < 2:  # Show images for first 2 benches
            display_bench_images(client, bench, show_annotations=args.show_annotations)


def cmd_searches(client: FastAPIClient, args):
    """List searches command."""
    print("🔍 Listing completed searches...")
    response = client.get_searches()
    searches = response["searches"]

    if not searches:
        print("❌ No completed searches found")
        return

    print(f"\n📊 Found {len(searches)} completed searches:")
    print("=" * 80)

    for i, search in enumerate(searches):
        print(f"\n{i+1}. Search ID: {search['id']}")
        print(f"   Query: {search['query']}")
        print(f"   Location: {search['start_lat']:.6f}, {search['start_lng']:.6f}")
        print(f"   Radius: {search['search_radius']}m")
        print(f"   Benches Found: {search['bench_count']}")
        print(f"   Created: {search['created_at']}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="CLI tool for testing the Bench Finder FastAPI server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check server health
  python tools/fastapi_cli.py health

  # Get a random bench with images
  python tools/fastapi_cli.py random --show-images

  # Find closest benches to Amsterdam
  python tools/fastapi_cli.py closest 52.3676 4.9041 --limit 5

  # List benches with high confidence
  python tools/fastapi_cli.py list --min-confidence 0.9 --sort-by confidence

  # Search bounding box around Amsterdam
  python tools/fastapi_cli.py bbox 52.4 52.3 5.0 4.8 --limit 10

  # Show server configuration
  python tools/fastapi_cli.py config
        """,
    )

    parser.add_argument(
        "--server",
        default="http://localhost:8866",
        help="FastAPI server URL (default: http://localhost:8866)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Health command
    subparsers.add_parser("health", help="Check server health")

    # Config command
    subparsers.add_parser("config", help="Show server configuration")

    # Info command
    subparsers.add_parser("info", help="Show API information")

    # Random command
    random_parser = subparsers.add_parser("random", help="Get a random bench")
    random_parser.add_argument(
        "--min-confidence", type=float, default=0.8, help="Minimum confidence (0.0-1.0)"
    )
    random_parser.add_argument(
        "--mode",
        choices=["benches", "no_bench", "both"],
        default="benches",
        help="Bench mode",
    )
    random_parser.add_argument(
        "--show-images", action="store_true", help="Display bench images"
    )
    random_parser.add_argument(
        "--show-annotations", action="store_true", help="Show detection annotations"
    )

    # Closest command
    closest_parser = subparsers.add_parser(
        "closest", help="Find closest benches to coordinates"
    )
    closest_parser.add_argument("lat", type=float, help="Latitude")
    closest_parser.add_argument("lng", type=float, help="Longitude")
    closest_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum number of results"
    )
    closest_parser.add_argument(
        "--min-confidence", type=float, default=0.8, help="Minimum confidence (0.0-1.0)"
    )
    closest_parser.add_argument(
        "--mode",
        choices=["benches", "no_bench", "both"],
        default="benches",
        help="Bench mode",
    )
    closest_parser.add_argument(
        "--clustered", action="store_true", default=True, help="Use clustered results"
    )
    closest_parser.add_argument(
        "--show-images", action="store_true", help="Display bench images"
    )
    closest_parser.add_argument(
        "--show-annotations", action="store_true", help="Show detection annotations"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List benches with pagination")
    list_parser.add_argument(
        "--page", type=int, default=0, help="Page number (0-based)"
    )
    list_parser.add_argument("--page-size", type=int, default=20, help="Items per page")
    list_parser.add_argument(
        "--min-confidence", type=float, default=0.8, help="Minimum confidence (0.0-1.0)"
    )
    list_parser.add_argument(
        "--start-lat",
        type=float,
        default=52.3613577,
        help="Starting latitude for distance sorting",
    )
    list_parser.add_argument(
        "--start-lng",
        type=float,
        default=4.8666322,
        help="Starting longitude for distance sorting",
    )
    list_parser.add_argument(
        "--sort-by",
        choices=["distance", "confidence", "images", "recent"],
        default="distance",
        help="Sort criteria",
    )
    list_parser.add_argument(
        "--mode",
        choices=["benches", "no_bench", "both"],
        default="benches",
        help="Bench mode",
    )
    list_parser.add_argument(
        "--clustered", action="store_true", default=True, help="Use clustered results"
    )
    list_parser.add_argument(
        "--show-images", action="store_true", help="Display bench images"
    )
    list_parser.add_argument(
        "--show-annotations", action="store_true", help="Show detection annotations"
    )

    # Bbox command
    bbox_parser = subparsers.add_parser("bbox", help="Search benches in bounding box")
    bbox_parser.add_argument("north", type=float, help="Northern latitude boundary")
    bbox_parser.add_argument("south", type=float, help="Southern latitude boundary")
    bbox_parser.add_argument("east", type=float, help="Eastern longitude boundary")
    bbox_parser.add_argument("west", type=float, help="Western longitude boundary")
    bbox_parser.add_argument(
        "--min-confidence", type=float, default=0.8, help="Minimum confidence (0.0-1.0)"
    )
    bbox_parser.add_argument(
        "--source", choices=["osm", "mapillary"], help="Filter by data source"
    )
    bbox_parser.add_argument(
        "--mode",
        choices=["benches", "no_bench", "both"],
        default="benches",
        help="Bench mode",
    )
    bbox_parser.add_argument(
        "--sort-by",
        choices=["distance", "confidence", "images", "recent"],
        default="distance",
        help="Sort criteria",
    )
    bbox_parser.add_argument(
        "--limit", type=int, default=200, help="Maximum number of results"
    )
    bbox_parser.add_argument(
        "--clustered", action="store_true", default=True, help="Use clustered results"
    )
    bbox_parser.add_argument(
        "--show-images", action="store_true", help="Display bench images"
    )
    bbox_parser.add_argument(
        "--show-annotations", action="store_true", help="Show detection annotations"
    )

    # Searches command
    subparsers.add_parser("searches", help="List completed searches")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize client
    client = FastAPIClient(args.server)

    # Route to appropriate command
    commands = {
        "health": cmd_health,
        "config": cmd_config,
        "info": cmd_info,
        "random": cmd_random,
        "closest": cmd_closest,
        "list": cmd_list,
        "bbox": cmd_bbox,
        "searches": cmd_searches,
    }

    if args.command in commands:
        commands[args.command](client, args)
    else:
        print(f"❌ Unknown command: {args.command}")
        parser.print_help()


if __name__ == "__main__":
    main()
