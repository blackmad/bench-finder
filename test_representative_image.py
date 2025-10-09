#!/usr/bin/env python3
"""
Test script demonstrating the new representative image selection feature.

This test shows how the system now:
1. Runs detection on all 4 images (N, E, S, W headings)
2. Calculates pixel coverage for each detection
3. Selects the image where the bench occupies the largest percentage of pixels
4. Only displays and copies the representative image
"""

import sys
from pathlib import Path


# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))


def test_pixel_coverage_calculation():
    """Test the pixel coverage calculation logic."""
    print("=== Testing Pixel Coverage Calculation ===")

    # Mock detection results to test the calculation
    mock_detections = [
        {
            "heading": 0,
            "has_bench": True,
            "max_confidence": 0.85,
            "detections": [
                {"x": 320, "y": 240, "width": 100, "height": 80}  # 8,000 pixels
            ],
        },
        {
            "heading": 90,
            "has_bench": True,
            "max_confidence": 0.92,
            "detections": [
                {"x": 320, "y": 240, "width": 200, "height": 150}  # 30,000 pixels
            ],
        },
        {
            "heading": 180,
            "has_bench": True,
            "max_confidence": 0.78,
            "detections": [
                {"x": 320, "y": 240, "width": 150, "height": 120}  # 18,000 pixels
            ],
        },
        {"heading": 270, "has_bench": False, "max_confidence": 0.0, "detections": []},
    ]

    # Simulate image dimensions (640x640 = 409,600 total pixels)
    image_total_pixels = 640 * 640

    print("Mock detection results:")
    for detection in mock_detections:
        if detection["has_bench"]:
            # Calculate pixel coverage for this mock detection
            total_bench_pixels = 0
            for det in detection["detections"]:
                total_bench_pixels += det["width"] * det["height"]

            coverage_percentage = (total_bench_pixels / image_total_pixels) * 100
            print(
                f"  Heading {detection['heading']:3d}°: {detection['max_confidence']:.2f} confidence, "
                f"{coverage_percentage:.1f}% pixel coverage ({total_bench_pixels:,} pixels)"
            )
        else:
            print(f"  Heading {detection['heading']:3d}°: No bench detected")

    # Find representative image (highest pixel coverage)
    bench_detections = [d for d in mock_detections if d["has_bench"]]
    if bench_detections:
        # Calculate coverage for sorting
        for detection in bench_detections:
            total_bench_pixels = sum(
                det["width"] * det["height"] for det in detection["detections"]
            )
            detection["pixel_coverage"] = (
                total_bench_pixels / image_total_pixels
            ) * 100

        representative = max(bench_detections, key=lambda x: x["pixel_coverage"])
        print(
            f"\n🎯 Selected representative: Heading {representative['heading']}° with "
            f"{representative['pixel_coverage']:.1f}% pixel coverage"
        )
        print(
            "   This image shows the bench taking up the most space, making it the best representative view"
        )

    print("\n✅ Pixel coverage calculation test completed!")


def explain_feature():
    """Explain the new representative image selection feature."""
    print("\n=== Representative Image Selection Feature ===")
    print()
    print("🔄 NEW WORKFLOW:")
    print("1. Capture 4 street view images (N, E, S, W headings)")
    print("2. Run AI detection on ALL 4 images")
    print(
        "3. Calculate pixel coverage for each detection (% of image occupied by bench)"
    )
    print("4. Select the image where the bench takes up the most space")
    print("5. Display and copy only the representative image")
    print()
    print("🎯 BENEFITS:")
    print("• Shows the clearest, most prominent view of the bench")
    print("• Reduces visual clutter by showing only the best image")
    print("• Still processes all images for data completeness")
    print("• Better user experience with more relevant results")
    print()
    print("📊 SELECTION CRITERIA (in order of priority):")
    print("1. Highest pixel coverage (bench occupies more of the image)")
    print("2. Highest confidence score (if pixel coverage is tied)")
    print("3. If no bench detected, show debug information for all images")
    print()
    print("💡 EXAMPLE SCENARIOS:")
    print("• North view: Bench partially visible (20% coverage, 0.85 confidence)")
    print(
        "• East view:  Bench fully visible    (45% coverage, 0.92 confidence) ← SELECTED"
    )
    print("• South view: Bench distant          (15% coverage, 0.78 confidence)")
    print("• West view:  No bench detected      (0% coverage)")
    print("→ East view selected as representative (highest pixel coverage)")


def main():
    """Run the demonstration."""
    print("Representative Image Selection Feature Test")
    print("=" * 50)

    explain_feature()
    test_pixel_coverage_calculation()

    print("\n" + "=" * 50)
    print(
        "🎉 The bench finder now intelligently selects the best representative image!"
    )
    print()
    print("To see this in action, run:")
    print("  ./bin/bench_finder 'Central Park, NYC'")
    print()
    print("Look for these new log messages:")
    print("• '🎯 Selected representative image: heading X° with Y% pixel coverage'")
    print("• '🏆 Representative bench image: ... with X% pixel coverage'")
    print("• '📊 Detection Summary (N images with benches):'")


if __name__ == "__main__":
    main()
