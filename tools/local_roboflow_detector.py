#!/usr/bin/env python3
"""
Local Roboflow Detector CLI Tool

A command-line interface for running object detection using Roboflow models.
"""

from pathlib import Path
from typing import Optional

import cv2
import dotenv
import supervision as sv
import typer
from PIL import Image
from term_image.image import AutoImage, ITerm2Image
from term_image.utils import get_terminal_name_version


print(get_terminal_name_version())

if get_terminal_name_version()[0] == "warp":
    # override KittyImage to always return that it is supported
    ITerm2Image.is_supported = lambda *_: True


dotenv.load_dotenv()

app = typer.Typer(
    help="Local Roboflow Detector - Run object detection on images using Roboflow models"
)


@app.command()
def detect(
    image_path: str = typer.Argument(..., help="Path to the input image file"),
    model_id: str = typer.Option(
        "yolov8n-640", "--model", "-m", help="Roboflow model ID to use"
    ),
    output_path: Optional[str] = typer.Option(
        None, "--output", "-o", help="Path to save the annotated image (optional)"
    ),
    show_image: bool = typer.Option(
        True, "--show/--no-show", help="Display the annotated image"
    ),
    confidence: float = typer.Option(
        0.5, "--confidence", "-c", help="Confidence threshold for detections"
    ),
):
    """
    Run object detection on an image using a Roboflow model.

    Example:
        python local_roboflow_detector.py image.jpg --model yolov8n-640 --output result.jpg
    """
    # Validate input image exists
    image_file = Path(image_path)
    if not image_file.exists():
        typer.echo(f"Error: Image file '{image_path}' not found.", err=True)
        raise typer.Exit(1)

    typer.echo(f"Loading image: {image_path}")

    # Load the image
    image = cv2.imread(str(image_file))
    if image is None:
        typer.echo(
            f"Error: Could not load image '{image_path}'. Please check if it's a valid image file.",
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(f"Loading model: {model_id}")

    # Load the pre-trained model
    try:
        from inference import get_model
        model = get_model(model_id=model_id)
    except Exception as e:
        typer.echo(f"Error loading model '{model_id}': {e}", err=True)
        raise typer.Exit(1)

    typer.echo("Running inference...")

    # Run inference on the image
    try:
        results = model.infer(image)
    except Exception as e:
        typer.echo(f"Error running inference: {e}", err=True)
        raise typer.Exit(1) from e

    # Load the results into the supervision Detections API
    try:
        detections = sv.Detections.from_inference(
            results[0].dict(by_alias=True, exclude_none=True)
        )
    except Exception as e:
        typer.echo(f"Error processing detection results: {e}", err=True)
        raise typer.Exit(1) from e

    # Filter detections by confidence
    if confidence > 0 and detections.confidence is not None:
        detections = detections[detections.confidence >= confidence]

    typer.echo(f"Found {len(detections)} detections")

    # Create supervision annotators
    bounding_box_annotator = sv.BoxAnnotator()
    label_annotator = sv.LabelAnnotator()

    # Annotate the image with our inference results
    annotated_image = bounding_box_annotator.annotate(
        scene=image, detections=detections
    )
    annotated_image = label_annotator.annotate(
        scene=annotated_image, detections=detections
    )

    # Save the annotated image if output path is specified
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_file), annotated_image)
        typer.echo(f"Annotated image saved to: {output_path}")

    # Display the image if requested
    if show_image:
        typer.echo("Displaying annotated image...")
        # Convert OpenCV image (BGR) to PIL Image (RGB)
        annotated_image_rgb = cv2.cvtColor(annotated_image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(annotated_image_rgb)
        print(AutoImage(pil_image))


if __name__ == "__main__":
    app()
