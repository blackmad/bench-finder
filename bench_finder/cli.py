#!/usr/bin/env python3
"""
CLI interface for the bench finder application using Typer.
"""

import logging
from typing import TYPE_CHECKING, Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from bench_finder.config import MAPILLARY_ACCESS_TOKEN, SEARCH_RADIUS_METERS
from bench_finder.core.geocoder import Geocoder
from bench_finder.models.schemas import SearchCreate
from bench_finder.pipeline import BenchFinder
from bench_finder.services.database import BenchDatabase
from bench_finder.utils import setup_logging
from examples.mapillary_bench_generator import MapillaryBenchGenerator
from examples.overpass_bench_generator import OverpassBenchGenerator


if TYPE_CHECKING:
    from examples.bench_generator import BenchCandidate, BenchGenerator


# Initialize Typer app and console
app = typer.Typer(
    name="bench-finder",
    help="Find benches using OSM data, Street View images, and AI detection",
    no_args_is_help=True,
)
console = Console()


@app.command("generate-candidates")
def generate_candidates(
    query: str = typer.Argument(
        ..., help="Search query (address, location name, etc.)"
    ),
    radius: int = typer.Option(
        SEARCH_RADIUS_METERS,
        "--radius",
        "-r",
        help=f"Search radius in meters (default: {SEARCH_RADIUS_METERS})",
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    show_table: bool = typer.Option(
        True, "--show-table/--no-show-table", help="Display results in a table"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format: table, json, csv"
    ),
):
    """
    Generate bench candidates by running the first 3 phases:
    1. Geocode query
    2. Create search record
    3. Find candidates using OSM and Mapillary

    This command only finds potential bench locations without processing images or running detection.
    """
    # Setup logging
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)

    console.print(
        f"[bold blue]🔍 Generating bench candidates for: '{query}'[/bold blue]"
    )
    console.print(f"[dim]Search radius: {radius}m[/dim]\n")

    # Initialize components
    geocoder = Geocoder()
    database = BenchDatabase()

    # Phase 1: Geocode the query
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        geocode_task = progress.add_task("Geocoding query...", total=None)
        coordinates = geocoder.geocode_query(query)
        progress.update(geocode_task, description="✅ Geocoding complete")

    if not coordinates:
        console.print("[bold red]❌ Failed to geocode query[/bold red]")
        raise typer.Exit(1)

    start_lat, start_lng = coordinates
    console.print(f"[green]📍 Location: {start_lat:.6f}, {start_lng:.6f}[/green]\n")

    # Phase 2: Create search record in database
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        search_task = progress.add_task("Creating search record...", total=None)
        search_id = database.create_search(
            SearchCreate(
                query=query,
                start_lat=start_lat,
                start_lng=start_lng,
                search_radius=radius,
            )
        )
        progress.update(search_task, description="✅ Search record created")

    console.print(f"[green]📝 Search ID: {search_id}[/green]\n")

    # Phase 3: Find benches using all available generators
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        candidates_task = progress.add_task("Finding bench candidates...", total=None)

        # Create bench generators
        generators: list[BenchGenerator] = []

        # Always add OSM generator
        try:
            osm_generator = OverpassBenchGenerator()
            generators.append(osm_generator)
            logger.info("Added OpenStreetMap generator")
        except Exception:
            logger.exception("Failed to initialize OSM generator")

        # Add Mapillary generator if token is available
        try:
            if MAPILLARY_ACCESS_TOKEN:
                mapillary_generator = MapillaryBenchGenerator()
                generators.append(mapillary_generator)
                logger.info("Added Mapillary generator")
            else:
                logger.warning(
                    "MAPILLARY_ACCESS_TOKEN not set - Mapillary generator not available"
                )
        except Exception as e:
            logger.warning(f"Failed to initialize Mapillary generator: {e}")

        if not generators:
            console.print(
                "[bold red]❌ No bench generators could be initialized[/bold red]"
            )
            raise typer.Exit(1)

        # Find candidates using all generators
        all_candidates: list[BenchCandidate] = []
        generator_results = {}

        for generator in generators:
            try:
                logger.debug(f"Querying {generator.name} for benches")
                candidates = generator.find_benches_near_point(
                    start_lat, start_lng, radius
                )
                all_candidates.extend(candidates)
                generator_results[generator.name] = len(candidates)
                logger.info(
                    f"{generator.name}: found {len(candidates)} bench candidates"
                )
            except Exception:
                logger.exception(f"Error querying {generator.name}")
                generator_results[generator.name] = 0

        # Deduplicate candidates
        deduplicated_candidates = _deduplicate_bench_candidates(all_candidates)

        # Store candidates in database
        for candidate in deduplicated_candidates:
            database.add_bench_candidate(
                search_id=search_id,
                provider_id=candidate.provider_id,
                lat=candidate.lat,
                lng=candidate.lng,
                tags=candidate.tags,
                source=candidate.source,
                external_id=candidate.external_id,
                confidence=candidate.confidence,
            )

        progress.update(
            candidates_task, description="✅ Bench candidates found and stored"
        )

    # Display results
    console.print(
        f"\n[bold green]✅ Found {len(deduplicated_candidates)} unique bench candidates[/bold green]"
    )
    console.print(f"[dim]Generator results: {generator_results}[/dim]\n")

    if show_table and deduplicated_candidates:
        _display_candidates_table(deduplicated_candidates, output_format)

    # Get stored candidates from database for verification
    stored_candidates = database.get_bench_candidates(search_id)
    console.print(
        f"\n[dim]📊 Stored {len(stored_candidates)} candidates in database (search_id: {search_id})[/dim]"
    )


@app.command("find-benches")
def find_benches(
    query: str = typer.Argument(
        ..., help="Search query (address, location name, etc.)"
    ),
    radius: int = typer.Option(
        SEARCH_RADIUS_METERS,
        "--radius",
        "-r",
        help=f"Search radius in meters (default: {SEARCH_RADIUS_METERS})",
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
):
    """
    Complete bench finding pipeline: find candidates and capture images.

    This pipeline finds bench candidates and captures Street View images.
    Use 'run-detections' command separately to run AI detection on the captured images.
    """

    # Setup logging
    setup_logging(level=log_level)
    logging.getLogger(__name__)

    # Initialize bench finder
    bench_finder = BenchFinder()

    console.print(
        f"[bold blue]🔍 BenchFinder starting with query: '{query}'[/bold blue]"
    )

    results = bench_finder.find_benches(query, radius)

    if results.success:
        console.print(f"[bold green]✅ {results.message}[/bold green]")

        if results.search_id:
            search_results = bench_finder.database.get_search_results(results.search_id)
            if search_results:
                console.print("\n[bold]📊 Summary:[/bold]")
                console.print(f"   • Search ID: {search_results.search.id}")
                console.print(f"   • Query: {search_results.search.query}")
                console.print(
                    f"   • Location: ({search_results.search.start_lat}, {search_results.search.start_lng})"
                )
                console.print(
                    f"   • Search radius: {search_results.search.search_radius}m"
                )
                console.print(f"   • Benches found: {search_results.bench_count}")
                console.print(
                    f"   • Images captured: {search_results.successful_images}/{search_results.total_images}"
                )
        if results.stats:
            stats = results.stats
            console.print(
                f"   • Processing stats: {stats.benches_added}/{stats.benches_processed} benches processed"
            )
            console.print(f"   • Images captured: {stats.images_successful}/{stats.images_captured}")

        console.print(
            "\n[bold blue]💡 Next step: Run 'run-detections' to analyze the captured images with AI[/bold blue]"
        )


    else:
        console.print(f"[bold red]❌ {results.error}[/bold red]")
        raise typer.Exit(1)


@app.command("list-candidates")
def list_candidates(
    search_id: int = typer.Argument(..., help="Search ID to list candidates for"),
    output_format: str = typer.Option(
        "table", "--format", help="Output format: table, json, csv"
    ),
):
    """
    List bench candidates for a specific search ID.
    """
    database = BenchDatabase()
    candidates = database.get_bench_candidates(search_id)

    if not candidates:
        console.print(
            f"[yellow]No candidates found for search ID {search_id}[/yellow]"
        )
        return

    console.print(
        f"[bold blue]📋 Bench candidates for search ID {search_id}[/bold blue]"
    )
    console.print(f"[dim]Found {len(candidates)} candidates[/dim]\n")

    _display_candidates_table(candidates, output_format)



@app.command("run-detections")
def run_detections(
    search_id: Optional[int] = typer.Argument(None, help="Search ID to run detections for (defaults to latest search)"),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    max_candidates: Optional[int] = typer.Option(
        None,
        "--max-candidates",
        help="Maximum number of candidates to process (for testing)",
    ),
    backend: Optional[str] = typer.Option(
        None, "--backend", help="Detection backend: roboflow, ultralytics, or multi"
    ),
    disable_fallback: bool = typer.Option(
        False, "--disable-fallback", help="Disable multi-model fallback detection"
    ),
    no_copy_bench_images: bool = typer.Option(
        False,
        "--no-copy-bench-images",
        help="Disable copying images with detected benches",
    ),
):
    """
    Run AI detection on bench candidates that have images downloaded.

    This command processes existing bench candidates with 'image_download_done' status
    by running AI detection on their captured images.
    """
    # Setup logging first
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)

    try:
        # Initialize database and get candidates
        database = BenchDatabase()

        # If no search_id provided, use the latest search
        if search_id is None:
            search_id = database.get_latest_search_id()
            if search_id is None:
                console.print("[red]No searches found in database. Please run a search first.[/red]")
                return
            console.print(f"[blue]Using latest search ID: {search_id}[/blue]")

        # Get candidates with image_download_done status
        candidates = database.get_bench_candidates_by_status(search_id, "image_download_done")

        if not candidates:
            console.print(
                f"[yellow]No candidates with 'image_download_done' status found for search ID {search_id}[/yellow]"
            )
            return

        # Limit candidates if specified
        if max_candidates and len(candidates) > max_candidates:
            candidates = candidates[:max_candidates]
            console.print(f"[dim]Limited to first {max_candidates} candidates[/dim]")

        console.print(
            f"[bold blue]🤖 Running detections on {len(candidates)} bench candidates (search_id: {search_id})[/bold blue]\n"
        )

        # Initialize detection service
        from bench_finder.detection import BenchDetector

        enable_fallback = not disable_fallback
        copy_bench_images = not no_copy_bench_images
        detector = BenchDetector(
            detection_backend=backend,
            enable_fallback=enable_fallback,
            copy_bench_images=copy_bench_images,
        )

        console.print("[dim]Detection service initialized[/dim]\n")

        # Convert candidates to BenchCandidate objects for processing
        from examples.bench_generator import BenchCandidate as BenchCandidateClass

        bench_candidates = []
        for candidate in candidates:
            # Ensure provider_id is always a string
            provider_id = candidate.provider_id or f"candidate_{candidate.id}"
            bench_candidate = BenchCandidateClass(
                provider_id=provider_id,
                lat=candidate.lat,
                lng=candidate.lng,
                tags=candidate.tags or {},
                source=candidate.source,
                external_id=candidate.external_id,
                confidence=candidate.confidence,
            )
            bench_candidates.append(bench_candidate)

        # Process the candidates using the detection service with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"🤖 Running detections on {len(bench_candidates)} candidates",
                total=len(bench_candidates)
            )

            results = detector.process_benches_with_progress(
                search_id, bench_candidates, progress, task
            )

        # Display results
        console.print(
            "\n[bold green]✅ Detection complete![/bold green]"
        )
        console.print("[bold]📊 Detection Summary:[/bold]")
        console.print(f"   • Candidates processed: {results.benches_processed}")
        console.print(f"   • Benches detected: {results.benches_detected}")
        console.print(f"   • Detections performed: {results.detections_performed}")
        console.print(f"   • Best confidence: {results.best_confidence:.2f}")

        # Update search status to completed
        database.update_search_status(search_id, "completed")
        console.print("\n[dim]📝 Updated search status to 'completed'[/dim]")

    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Operation cancelled by user[/bold yellow]")
        raise typer.Exit(130) from None
    except Exception as e:
        console.print(f"[bold red]💥 Unexpected error: {e}[/bold red]")
        logger.exception("Unexpected error")
        raise typer.Exit(1) from e


@app.command("fetch-images")
def fetch_images(
    search_id: Optional[int] = typer.Argument(None, help="Search ID to fetch images for (defaults to latest search)"),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    max_candidates: Optional[int] = typer.Option(
        None,
        "--max-candidates",
        help="Maximum number of candidates to process (for testing)",
    ),
    status: str = typer.Option(
        "pending",
        "--status",
        help="Process candidates with this status (pending, image_download_done, detection_done, or all)",
    ),
):
    """
    Download and cache images for bench candidates from the database.

    This command processes existing bench candidates by:
    1. Loading candidates from the bench_candidates table
    2. Converting them to Bench records
    3. Capturing Street View images
    4. Storing images in the database

    Use this after running generate-candidates to download images.
    Detection can be run separately if needed.
    """
    # Setup logging first
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)

    try:
        # Initialize database and get candidates
        database = BenchDatabase()

        # If no search_id provided, use the latest search
        if search_id is None:
            search_id = database.get_latest_search_id()
            if search_id is None:
                console.print("[red]No searches found in database. Please run a search first.[/red]")
                return
            console.print(f"[blue]Using latest search ID: {search_id}[/blue]")

        # Get candidates based on status filter
        if status == "all":
            candidates = database.get_bench_candidates(search_id)
        else:
            candidates = database.get_bench_candidates_by_status(search_id, status)

        if not candidates:
            console.print(
                f"[yellow]No candidates found for search ID {search_id}[/yellow]"
            )
            return

        # Limit candidates if specified
        if max_candidates and len(candidates) > max_candidates:
            candidates = candidates[:max_candidates]
            console.print(f"[dim]Limited to first {max_candidates} candidates[/dim]")

        console.print(
            f"[bold blue]📸 Fetching images for {len(candidates)} bench candidates (search_id: {search_id}, status: {status})[/bold blue]\n"
        )

        # Initialize image download service
        from bench_finder.services.image_download_service import ImageDownloadService

        image_service = ImageDownloadService()

        console.print("[dim]Image download service initialized[/dim]\n")

        # Convert candidates to BenchCandidate objects for processing
        from examples.bench_generator import BenchCandidate as BenchCandidateClass

        bench_candidates = []
        for candidate in candidates:
            # Ensure provider_id is always a string
            provider_id = candidate.provider_id or f"candidate_{candidate.id}"
            bench_candidate = BenchCandidateClass(
                provider_id=provider_id,
                lat=candidate.lat,
                lng=candidate.lng,
                tags=candidate.tags or {},
                source=candidate.source,
                external_id=candidate.external_id,
                confidence=candidate.confidence,
            )
            bench_candidates.append(bench_candidate)

        # Process the candidates using the image download service with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"📸 Downloading images for {len(bench_candidates)} candidates",
                total=len(bench_candidates)
            )

            results = image_service.process_benches_with_progress(
                search_id, bench_candidates, progress, task
            )

        # Display results
        console.print(
            "\n[bold green]✅ Image downloading complete![/bold green]"
        )
        console.print("[bold]📊 Download Summary:[/bold]")
        console.print(f"   • Candidates processed: {results.benches_processed}")
        console.print(f"   • Benches added to database: {results.benches_added}")
        console.print(f"   • Images captured: {results.images_captured}")
        console.print(f"   • Images successful: {results.images_successful}")

        console.print("\n[dim]💡 Note: This command only downloads and caches images. Run detection separately if needed.[/dim]")

        # Update search status to completed
        database.update_search_status(search_id, "completed")
        console.print("\n[dim]📝 Updated search status to 'completed'[/dim]")

    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Operation cancelled by user[/bold yellow]")
        raise typer.Exit(130) from None
    except Exception as e:
        console.print(f"[bold red]💥 Unexpected error: {e}[/bold red]")
        logger.exception("Unexpected error")
        raise typer.Exit(1) from e


def _deduplicate_bench_candidates(candidates: list) -> list:
    """
    Remove duplicate bench candidates based on proximity.

    Two benches are considered duplicates if they are within 10 meters of each other.
    When duplicates are found, prefers the one with higher confidence or from OSM.
    """
    if not candidates:
        return candidates

    # Distance threshold for considering two benches as duplicates (meters)
    DUPLICATE_THRESHOLD_METERS = 10

    unique_candidates: list = []

    for candidate in candidates:
        is_duplicate = False

        # Check if this candidate is close to any existing unique candidate
        for i, existing in enumerate(unique_candidates):
            distance = _haversine_distance(
                candidate.lat, candidate.lng, existing.lat, existing.lng
            )

            if distance <= DUPLICATE_THRESHOLD_METERS:
                is_duplicate = True

                # Replace existing if current candidate is "better"
                if _is_better_candidate(candidate, existing):
                    unique_candidates[i] = candidate
                break

        if not is_duplicate:
            unique_candidates.append(candidate)

    return unique_candidates


def _is_better_candidate(candidate1, candidate2) -> bool:
    """
    Determine which candidate is "better" for deduplication purposes.
    """
    # Prefer candidate with confidence score
    if candidate1.confidence is not None and candidate2.confidence is None:
        return True
    if candidate1.confidence is None and candidate2.confidence is not None:
        return False

    # If both have confidence, prefer higher confidence
    if candidate1.confidence is not None and candidate2.confidence is not None:
        return candidate1.confidence > candidate2.confidence

    # If neither has confidence, prefer OSM (more reliable positioning)
    if candidate1.source == "osm" and candidate2.source != "osm":
        return True
    if candidate1.source != "osm" and candidate2.source == "osm":
        return False

    # If same source type, prefer the first one (arbitrary)
    return False


def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the Haversine distance between two points in meters.
    """
    import math

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

    # Radius of Earth in meters
    R = 6371000
    return R * c


def _display_candidates_table(candidates: list, output_format: str = "table"):
    """
    Display candidates in the specified format.
    """
    if output_format == "table":
        table = Table(title="Bench Candidates")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Provider ID", style="green")
        table.add_column("Source", style="blue")
        table.add_column("Latitude", style="magenta")
        table.add_column("Longitude", style="magenta")
        table.add_column("Confidence", style="yellow")
        table.add_column("Tags", style="dim")

        for candidate in candidates:
            # Get provider_id or use a fallback
            provider_id = (
                getattr(candidate, "provider_id", None)
                or f"candidate_{getattr(candidate, 'id', 'unknown')}"
            )

            # Get tags as a string
            tags = getattr(candidate, "tags", {})
            if isinstance(tags, dict):
                tags_str = ", ".join(
                    [f"{k}: {v}" for k, v in list(tags.items())[:2]]
                )  # Show first 2 tags
                if len(tags) > 2:
                    tags_str += "..."
            else:
                tags_str = str(tags)[:50] + "..." if len(str(tags)) > 50 else str(tags)

            table.add_row(
                str(getattr(candidate, "id", "N/A")),
                provider_id,
                getattr(candidate, "source", "unknown"),
                f"{getattr(candidate, 'lat', 0):.6f}",
                f"{getattr(candidate, 'lng', 0):.6f}",
                f"{getattr(candidate, 'confidence', 0):.2f}"
                if getattr(candidate, "confidence", None) is not None
                else "N/A",
                tags_str,
            )

        console.print(table)

    elif output_format == "json":
        import json

        console.print(json.dumps(candidates, indent=2))

    elif output_format == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            [
                "ID",
                "Provider ID",
                "Source",
                "Latitude",
                "Longitude",
                "Confidence",
                "Tags",
            ]
        )

        # Write data
        for candidate in candidates:
            tags = getattr(candidate, "tags", {})
            tags_str = str(tags) if tags else ""

            writer.writerow(
                [
                    getattr(candidate, "id", "N/A"),
                    getattr(candidate, "provider_id", "N/A"),
                    getattr(candidate, "source", "unknown"),
                    getattr(candidate, "lat", 0),
                    getattr(candidate, "lng", 0),
                    getattr(candidate, "confidence", "N/A"),
                    tags_str,
                ]
            )

        console.print(output.getvalue())


if __name__ == "__main__":
    app()
