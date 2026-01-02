#!/usr/bin/env python3
"""
CLI interface for the bench finder application using Typer.
"""

import logging
import os

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
from bench_finder.generators.bench_generator import BenchCandidate, BenchGenerator
from bench_finder.generators.mapillary import MapillaryBenchGenerator
from bench_finder.generators.overpass import OverpassBenchGenerator

# Import enums and models separately to avoid double-loading unified_models
from bench_finder.models.enums import BenchCandidateStatus, DataSource, SearchStatus
from bench_finder.models.unified_models import SearchBase

# Import database first - this will load unified_models once
from bench_finder.services.database import BenchDatabase
from bench_finder.utils import setup_logging


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
    source: list[str] = typer.Option(
        None,
        "--source",
        "-s",
        help="Filter by source(s): osm, mapillary (can be specified multiple times). If not specified, all sources are used.",
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
            SearchBase(
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

        # Normalize source filter if provided
        source_filter: set[DataSource] | None = None
        if source:
            # Normalize source names (handle both lowercase and uppercase)
            source_normalized = [s.upper() for s in source]
            # Map common aliases
            source_mapping = {
                "OSM": DataSource.OSM,
                "MAPILLARY": DataSource.MAPILLARY,
            }
            source_filter = set()
            for s in source_normalized:
                if s in source_mapping:
                    source_filter.add(source_mapping[s])
                else:
                    console.print(
                        f"[yellow]⚠️  Unknown source: {s}. Valid sources are: osm, mapillary[/yellow]"
                    )
                    raise typer.Exit(1)

            if source_filter:
                source_names = ", ".join([s.value for s in source_filter])
                console.print(f"[dim]Filtering sources: {source_names}[/dim]\n")

        # Create bench generators
        generators: list[BenchGenerator] = []

        # Always add OSM generator (if not filtered out)
        if not source_filter or DataSource.OSM in source_filter:
            try:
                osm_generator = OverpassBenchGenerator()
                generators.append(osm_generator)
                logger.info("Added OpenStreetMap generator")
            except Exception:
                logger.exception("Failed to initialize OSM generator")

        # Add Mapillary generator if token is available (if not filtered out)
        if not source_filter or DataSource.MAPILLARY in source_filter:
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
            if source_filter:
                requested_sources = ", ".join([s.value for s in source_filter])
                console.print(
                    f"[bold red]❌ No bench generators could be initialized for requested source(s): {requested_sources}[/bold red]"
                )
            else:
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
        reverse_geocoded_count = 0
        for candidate in deduplicated_candidates:
            bench_candidate_id = database.add_bench_candidate(
                search_id=search_id,
                provider_id=candidate.provider_id,
                lat=candidate.lat,
                lng=candidate.lng,
                tags=candidate.tags,
                source=candidate.source,
                external_id=candidate.external_id,
                confidence=candidate.confidence,
            )

            # Reverse geocode the candidate (structured)
            if bench_candidate_id:
                try:
                    geocoder = Geocoder()
                    structured_address = geocoder.reverse_geocode_structured(
                        candidate.lat, candidate.lng
                    )
                    if structured_address:
                        database.add_or_update_reverse_geocode(
                            bench_candidate_id=bench_candidate_id,
                            formatted_address=structured_address["formatted_address"],
                            street_number=structured_address.get("street_number"),
                            street_name=structured_address.get("street_name"),
                            city=structured_address.get("city"),
                            state=structured_address.get("state"),
                            postal_code=structured_address.get("postal_code"),
                            country=structured_address.get("country"),
                            raw_response=structured_address.get("raw_response"),
                        )
                        reverse_geocoded_count += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to reverse geocode candidate {bench_candidate_id}: {e}"
                    )

        progress.update(
            candidates_task, description="✅ Bench candidates found and stored"
        )

        if reverse_geocoded_count > 0:
            console.print(
                f"[dim]📍 Reverse geocoded {reverse_geocoded_count} candidates[/dim]"
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
        console.print(f"[yellow]No candidates found for search ID {search_id}[/yellow]")
        return

    console.print(
        f"[bold blue]📋 Bench candidates for search ID {search_id}[/bold blue]"
    )
    console.print(f"[dim]Found {len(candidates)} candidates[/dim]\n")

    _display_candidates_table(candidates, output_format)


@app.command("run-detections")
def run_detections(
    search_id: int | None = typer.Argument(
        None, help="Search ID to run detections for (defaults to latest search)"
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    max_candidates: int | None = typer.Option(
        None,
        "--max-candidates",
        help="Maximum number of candidates to process (for testing)",
    ),
    backend: str | None = typer.Option(
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

        # Get candidates with image_download_done status
        candidates = database.get_bench_candidates_by_status(
            BenchCandidateStatus.IMAGE_DOWNLOAD_DONE, search_id
        )

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
        from detection import BenchDetector

        enable_fallback = not disable_fallback
        copy_bench_images = not no_copy_bench_images
        detector = BenchDetector(
            detection_backend=backend,
            enable_fallback=enable_fallback,
            copy_bench_images=copy_bench_images,
        )

        console.print("[dim]Detection service initialized[/dim]\n")

        bench_candidates = []
        for candidate in candidates:
            # Ensure provider_id is always a string
            provider_id = candidate.provider_id or f"candidate_{candidate.id}"
            bench_candidate = BenchCandidate(
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
            disable=True,
        ) as progress:
            task = progress.add_task(
                f"🤖 Running detections on {len(bench_candidates)} candidates",
                total=len(bench_candidates),
            )

            results = detector.process_benches_with_progress(
                bench_candidates, progress, task
            )

        # Display results
        console.print("\n[bold green]✅ Detection complete![/bold green]")
        console.print("[bold]📊 Detection Summary:[/bold]")
        console.print(f"   • Candidates processed: {results.benches_processed}")
        console.print(f"   • Benches detected: {results.benches_detected}")
        console.print(f"   • Detections performed: {results.detections_performed}")
        console.print(f"   • Best confidence: {results.best_confidence:.2f}")

        # Update search status to completed
        database.update_search_status(search_id, SearchStatus.COMPLETED)
        console.print("\n[dim]📝 Updated search status to 'completed'[/dim]")

    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Operation cancelled by user[/bold yellow]")
        raise typer.Exit(130) from None
    except Exception as e:
        console.print(f"[bold red]💥 Unexpected error: {e}[/bold red]")
        logger.exception("Unexpected error")
        raise typer.Exit(1) from e


@app.command("reset-detections")
def reset_detections(
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
):
    """
    Reset detection results by clearing the detections table and resetting bench candidate statuses.

    This command will:
    1. Clear all records from the detections table
    2. Reset bench candidate status from DETECTION_DONE to IMAGE_DOWNLOAD_DONE

    Use this when you want to re-run detections on existing bench candidates.
    """
    # Setup logging
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)

    try:
        # Initialize database
        database = BenchDatabase()

        # Get counts before reset
        with database.get_session() as session:
            from bench_finder.models.unified_models import BenchCandidate, Detection

            detection_count = session.query(Detection).count()
            candidate_count = (
                session.query(BenchCandidate)
                .filter(BenchCandidate.status == BenchCandidateStatus.DETECTION_DONE)
                .count()
            )

        if detection_count == 0 and candidate_count == 0:
            console.print("[yellow]No detections or candidates to reset.[/yellow]")
            return

        # Show what will be reset
        console.print("[bold blue]🔄 Reset Detections[/bold blue]")
        console.print("[dim]This will:[/dim]")
        console.print(f"[dim]  • Clear {detection_count} detection records[/dim]")
        console.print(
            f"[dim]  • Reset {candidate_count} bench candidates from DETECTION_DONE to IMAGE_DOWNLOAD_DONE[/dim]\n"
        )

        # Confirmation prompt
        if not confirm and not typer.confirm("Are you sure you want to proceed?"):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        # Clear detections table
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            clear_task = progress.add_task("Clearing detections table...", total=None)
            cleared_count = database.clear_detections_table()
            progress.update(clear_task, description="✅ Detections table cleared")

        # Reset bench candidate statuses
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            reset_task = progress.add_task(
                "Resetting bench candidate statuses...", total=None
            )
            reset_count = database.reset_bench_candidate_detection_status()
            progress.update(reset_task, description="✅ Bench candidate statuses reset")

        # Display results
        console.print("\n[bold green]✅ Reset complete![/bold green]")
        console.print(f"[green]  • Cleared {cleared_count} detection records[/green]")
        console.print(
            f"[green]  • Reset {reset_count} bench candidates to IMAGE_DOWNLOAD_DONE status[/green]"
        )
        console.print(
            "\n[dim]💡 You can now re-run detections using the run-detections command.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]💥 Unexpected error: {e}[/bold red]")
        logger.exception("Unexpected error")
        raise typer.Exit(1) from e


@app.command("reset-image-status")
def reset_image_status(
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
):
    """
    Reset bench candidate status to PENDING to allow re-downloading images.

    This command resets candidates with status IMAGE_DOWNLOAD_DONE or DETECTION_DONE
    back to PENDING. This is useful if you want to re-run the image fetch process
    (e.g., to retry failed downloads or fetch missing images) without deleting
    the existing images or candidates.
    """
    # Setup logging
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)

    try:
        # Initialize database
        database = BenchDatabase()

        # Get counts before reset
        with database.get_session() as session:
            from bench_finder.models.unified_models import BenchCandidate

            candidate_count = (
                session.query(BenchCandidate)
                .filter(
                    BenchCandidate.status.in_(
                        [
                            BenchCandidateStatus.IMAGE_DOWNLOAD_DONE,
                            BenchCandidateStatus.DETECTION_DONE,
                        ]
                    )
                )
                .count()
            )

        if candidate_count == 0:
            console.print(
                "[yellow]No candidates found with status IMAGE_DOWNLOAD_DONE or DETECTION_DONE.[/yellow]"
            )
            return

        # Show what will be reset
        console.print("[bold blue]🔄 Reset Image Download Status[/bold blue]")
        console.print(
            f"[dim]This will reset {candidate_count} bench candidates to PENDING status.[/dim]"
        )
        console.print("[dim]Existing images will NOT be deleted.[/dim]\n")

        # Confirmation prompt
        if not confirm and not typer.confirm("Are you sure you want to proceed?"):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        # Reset statuses
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            reset_task = progress.add_task(
                "Resetting bench candidate statuses...", total=None
            )
            reset_count = database.reset_bench_candidate_image_status()
            progress.update(reset_task, description="✅ Bench candidate statuses reset")

        # Display results
        console.print("\n[bold green]✅ Reset complete![/bold green]")
        console.print(
            f"[green]  • Reset {reset_count} bench candidates to PENDING status[/green]"
        )
        console.print(
            "\n[dim]💡 You can now re-run fetch-images to download missing images.[/dim]"
        )

    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Operation cancelled by user[/bold yellow]")
        raise typer.Exit(130) from None
    except Exception as e:
        console.print(f"[bold red]💥 Unexpected error: {e}[/bold red]")
        logger.exception("Unexpected error")
        raise typer.Exit(1) from e


@app.command("show-random-image")
def show_random_image(
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
):
    """
    Display a random streetview image from the database using AutoImage.

    This command fetches a random successfully captured streetview image
    and displays it directly in the terminal using AutoImage.
    """
    # Setup logging
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)

    try:
        # Initialize database
        database = BenchDatabase()

        console.print("[bold blue]🎲 Fetching random streetview image...[/bold blue]")

        # Get random image
        random_image = database.get_random_streetview_image()

        if not random_image:
            console.print(
                "[bold red]❌ No streetview images found in database[/bold red]"
            )
            console.print(
                "[dim]Make sure you have run fetch-images command first to download some images.[/dim]"
            )
            return

        # Check if image file exists
        if not random_image.filepath or not os.path.exists(random_image.filepath):
            console.print(
                f"[bold red]❌ Image file not found: {random_image.filepath}[/bold red]"
            )
            return

        # Display image info
        console.print(f"[green]📍 Image: {random_image.filename}[/green]")
        console.print(f"[green]📁 Path: {random_image.filepath}[/green]")
        console.print(f"[green]🧭 Heading: {random_image.heading}°[/green]")
        console.print(f"[green]📏 Size: {random_image.file_size} bytes[/green]")
        console.print(f"[green]🪑 Bench ID: {random_image.bench_id}[/green]\n")

        # Display the image using AutoImage
        console.print("[bold blue]🖼️  Displaying image in terminal:[/bold blue]")
        from PIL import Image
        from term_image.image import AutoImage

        # Increase PIL max image pixels limit to handle large panoramas
        Image.MAX_IMAGE_PIXELS = 300_000_000

        try:
            pil_image = Image.open(random_image.filepath)
            print(AutoImage(pil_image))
        except Exception as e:
            console.print(f"[bold red]❌ Failed to display image: {e}[/bold red]")
            console.print("[dim]Make sure your terminal supports image display.[/dim]")
            return

        console.print(
            "\n[dim]💡 Tip: This is a random streetview image from your database.[/dim]"
        )

    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Operation cancelled by user[/bold yellow]")
        raise typer.Exit(130) from None
    except Exception as e:
        console.print(f"[bold red]💥 Unexpected error: {e}[/bold red]")
        logger.exception("Unexpected error")
        raise typer.Exit(1) from e


@app.command("fetch-images")
def fetch_images(
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    max_candidates: int | None = typer.Option(
        None,
        "--max-candidates",
        help="Maximum number of candidates to process (for testing)",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Maximum number of candidates to process (alias for --max-candidates)",
    ),
    status: str = typer.Option(
        BenchCandidateStatus.PENDING,
        "--status",
        help="Process candidates with this status (pending, image_download_done, detection_done). Ignored if --force is used.",
    ),
    cached_only: bool = typer.Option(
        False,
        "--cached-only",
        help="Only use images that are already cached in the database, skip downloading new images",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force fetch for all candidates regardless of their current status",
    ),
):
    """
    Download and cache images for bench candidates from the database.

    This command processes existing bench candidates by:
    1. Loading candidates from the bench_candidates table with the specified status (or all if --force)
    2. Converting them to Bench records
    3. Capturing Street View images (unless --cached-only is set)
    4. Storing images in the database

    Use this after running generate-candidates to download images.
    Detection can be run separately if needed.

    With --cached-only: Only process candidates that already have images in the database,
    skipping any new downloads from Street View API.

    With --force: Process all candidates regardless of their current status, forcing
    re-fetch even if they already have images or are marked as done.

    This command ignores search_id and processes all candidates with the specified status (or all if --force).
    """
    # Setup logging first
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)

    try:
        # Initialize database and get candidates using SQLAlchemy ORM
        database = BenchDatabase()

        # Query all candidates with the specified status using SQLAlchemy ORM
        with database.get_session() as session:
            from sqlmodel import select

            from bench_finder.models.unified_models import (
                BenchCandidate as DBBenchCandidate,
            )

            # Build query - if force is used, ignore status filter
            statement = select(DBBenchCandidate)

            if not force:
                # Parse status string to enum
                try:
                    status_enum = BenchCandidateStatus(status)
                except ValueError as err:
                    console.print(
                        f"[red]Invalid status: {status}. Valid values: pending, image_download_done, detection_done[/red]"
                    )
                    raise typer.Exit(1) from err

                # Query all candidates with the specified status (ignoring search_id)
                statement = statement.where(DBBenchCandidate.status == status_enum)

            # Apply limit: use --limit if provided, otherwise use --max-candidates
            limit_value = limit if limit is not None else max_candidates
            if limit_value:
                statement = statement.limit(limit_value)

            candidates = list(session.exec(statement).all())

        if not candidates:
            status_str = "any status" if force else f"status '{status}'"
            console.print(f"[yellow]No candidates found with {status_str}[/yellow]")
            return

        mode_str = "cached-only" if cached_only else "download"
        force_str = " (force mode)" if force else ""
        status_str = f"status: {status}" if not force else "all statuses"
        console.print(
            f"[bold blue]📸 Fetching images for {len(candidates)} bench candidates ({status_str}, mode: {mode_str}{force_str})[/bold blue]\n"
        )

        # Initialize image download service
        from bench_finder.services.image_download_service import ImageDownloadService

        image_service = ImageDownloadService(cached_only=cached_only, force=force)

        console.print("[dim]Image download service initialized[/dim]\n")

        bench_candidates = []
        candidate_search_ids = {}  # Map provider_id to search_id for status updates
        for candidate in candidates:
            # Ensure provider_id is always a string
            provider_id = candidate.provider_id or f"candidate_{candidate.id}"
            bench_candidate = BenchCandidate(
                provider_id=provider_id,
                lat=candidate.lat,
                lng=candidate.lng,
                tags=candidate.tags or {},
                source=candidate.source,
                external_id=candidate.external_id,
                confidence=candidate.confidence,
            )
            bench_candidates.append(bench_candidate)
            # Store search_id for this candidate (needed for status updates)
            candidate_search_ids[provider_id] = candidate.search_id

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
            task_description = (
                "📸 Processing cached images for"
                if cached_only
                else "📸 Downloading images for"
            )
            task = progress.add_task(
                f"{task_description} {len(bench_candidates)} candidates",
                total=len(bench_candidates),
            )

            # Process each candidate with its own search_id
            from bench_finder.models.unified_models import ProcessingStats

            stats = ProcessingStats(
                benches_processed=0,
                benches_added=0,
                images_captured=0,
                images_successful=0,
                detections_performed=0,
                benches_detected=0,
                best_confidence=0.0,
            )

            # Track additional statistics
            candidates_with_cached_images = 0  # Had images already
            candidates_skipped = 0  # No images and none downloaded
            candidates_downloaded = 0  # Downloaded new images

            for bench_candidate in bench_candidates:
                search_id = candidate_search_ids.get(bench_candidate.provider_id)
                if search_id is None:
                    logger.warning(
                        f"No search_id found for candidate {bench_candidate.provider_id}, skipping"
                    )
                    candidates_skipped += 1
                    continue

                # Check if candidate already has images (before processing)
                had_existing_images = False
                if not cached_only:
                    with database.get_session() as session:
                        from sqlalchemy import func
                        from sqlmodel import select

                        from bench_finder.models.unified_models import (
                            BenchCandidate as DBBenchCandidate,
                        )
                        from bench_finder.models.unified_models import (
                            Image,
                        )

                        db_candidate = session.exec(
                            select(DBBenchCandidate).where(
                                DBBenchCandidate.provider_id
                                == bench_candidate.provider_id,
                                DBBenchCandidate.search_id == search_id,
                            )
                        ).first()
                        if db_candidate:
                            existing_count = session.exec(
                                select(func.count(Image.id)).where(
                                    Image.bench_candidate_id == db_candidate.id
                                )
                            ).one()
                            had_existing_images = existing_count > 0

                result = image_service._process_single_bench(search_id, bench_candidate)
                stats.benches_processed += 1

                if cached_only:
                    # In cached-only mode, track if we found cached images
                    if result.images_successful > 0:
                        candidates_with_cached_images += 1
                    else:
                        candidates_skipped += 1
                # In normal mode, distinguish between cached and downloaded
                elif result.images_successful > 0:
                    if had_existing_images:
                        # Candidate already had images, we just processed existing ones
                        candidates_with_cached_images += 1
                    else:
                        # New images were downloaded
                        candidates_downloaded += 1
                else:
                    # No images found or downloaded
                    candidates_skipped += 1

                if result.bench_added:
                    stats.benches_added += 1
                stats.images_captured += result.images_captured
                stats.images_successful += result.images_successful
                progress.update(task, advance=1)

            results = stats
            summary_stats = {
                "candidates_with_cached_images": candidates_with_cached_images,
                "candidates_skipped": candidates_skipped,
                "candidates_downloaded": candidates_downloaded,
            }

        # Display results
        action_str = (
            "Processing complete" if cached_only else "Image downloading complete"
        )
        console.print(f"\n[bold green]✅ {action_str}![/bold green]")
        console.print("[bold]📊 Summary:[/bold]")
        console.print(f"   • Candidates processed: {results.benches_processed}")
        console.print(f"   • Benches added to database: {results.benches_added}")
        console.print(f"   • Images captured: {results.images_captured}")
        console.print(f"   • Images successful: {results.images_successful}")

        # Display candidate statistics
        console.print("\n[bold]📈 Candidate Statistics:[/bold]")
        if cached_only:
            console.print(
                f"   • Candidates with cached images: {summary_stats['candidates_with_cached_images']}"
            )
            console.print(
                f"   • Candidates skipped (no cached images): {summary_stats['candidates_skipped']}"
            )
            console.print(
                "\n[dim]💡 Note: Only processed candidates with existing cached images. No new downloads were made.[/dim]"
            )
        else:
            console.print(
                f"   • Candidates with images downloaded: {summary_stats['candidates_downloaded']}"
            )
            console.print(
                f"   • Candidates with cached images (already had images): {summary_stats['candidates_with_cached_images']}"
            )
            console.print(
                f"   • Candidates skipped (no images): {summary_stats['candidates_skipped']}"
            )
            console.print(
                "\n[dim]💡 Note: This command only downloads and caches images. Run detection separately if needed.[/dim]"
            )

        # Note: We don't update search status here since we're processing across multiple searches
        console.print(
            "\n[dim]💡 Note: Search statuses were updated for individual candidates.[/dim]"
        )

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


@app.command("cleanup-deleted-osm")
def cleanup_deleted_osm(
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Dry run mode (default: True). Use --no-dry-run to actually delete candidates",
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    batch_size: int = typer.Option(
        1000,
        "--batch-size",
        help="Number of candidates to check per batch (default: 1000)",
    ),
):
    """
    Check all OSM bench candidates and remove those that have been deleted from OpenStreetMap.

    This command:
    1. Fetches all OSM bench candidates from the database
    2. Checks if they still exist in OSM using bulk Overpass API queries
    3. Deletes candidates and their ProcessedBench entries if they've been removed from OSM

    By default, runs in dry-run mode to preview what would be deleted.
    Use --no-dry-run to actually perform the deletions.
    """
    # Setup logging
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)

    try:
        if dry_run:
            console.print(
                "[yellow]🔍 DRY RUN MODE - No changes will be made[/yellow]\n"
            )
        else:
            console.print(
                "[bold red]⚠️  LIVE MODE - Candidates will be permanently deleted[/bold red]\n"
            )
            if not typer.confirm(
                "Are you sure you want to delete deleted OSM candidates?"
            ):
                console.print("[yellow]Operation cancelled.[/yellow]")
                return

        # Import here to avoid circular imports
        import sys
        from pathlib import Path

        # Add tools directory to path (tools/ is at project root, not in bench_finder/)
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))

        from bench_finder.tools.cleanup_deleted_osm_benches import (
            cleanup_deleted_osm_benches,
        )

        stats = cleanup_deleted_osm_benches(dry_run=dry_run, batch_size=batch_size)

        console.print("\n[bold]📊 Final Summary:[/bold]")
        console.print(f"  • Total OSM candidates: {stats['total_osm_candidates']}")
        console.print(f"  • Checked: {stats['checked']}")
        console.print(f"  • Deleted candidates: {stats['deleted_candidates']}")
        console.print(
            f"  • Deleted processed benches: {stats['deleted_processed_benches']}"
        )
        console.print(f"  • Errors: {stats['errors']}")

    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Operation cancelled by user[/bold yellow]")
        raise typer.Exit(130) from None
    except Exception as e:
        console.print(f"[bold red]💥 Unexpected error: {e}[/bold red]")
        logger.exception("Unexpected error")
        raise typer.Exit(1) from e


@app.command("statistics")
def statistics(
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    format: str = typer.Option("table", "--format", help="Output format: table, json"),  # noqa: A002
):
    """
    Display comprehensive database statistics for debugging and monitoring.

    Shows counts, breakdowns, and statistics across all database tables including:
    - Searches, bench candidates, images, detections
    - Status breakdowns and success rates
    - Recent activity and confidence statistics
    """
    # Setup logging
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)

    try:
        database = BenchDatabase()

        with database.get_session() as session:
            from sqlalchemy import func

            from bench_finder.models.unified_models import (
                BenchCandidate,
                BenchReport,
                Detection,
                DetectionItem,
                Image,
                MissingBenchReport,
                ProcessedBench,
                Search,
            )

            stats = {}

            # ============================================================
            # Overall Counts
            # ============================================================
            stats["total_searches"] = session.query(Search).count()
            stats["total_bench_candidates"] = session.query(BenchCandidate).count()
            stats["total_images"] = session.query(Image).count()
            stats["total_detections"] = session.query(Detection).count()
            stats["total_detection_items"] = session.query(DetectionItem).count()
            stats["total_processed_benches"] = session.query(ProcessedBench).count()
            stats["total_bench_reports"] = session.query(BenchReport).count()
            stats["total_missing_bench_reports"] = session.query(
                MissingBenchReport
            ).count()

            # ============================================================
            # Search Breakdowns
            # ============================================================
            search_status_counts = (
                session.query(Search.status, func.count(Search.id))
                .group_by(Search.status)
                .all()
            )
            stats["search_status"] = {
                str(status): count for status, count in search_status_counts
            }

            # ============================================================
            # Bench Candidate Breakdowns
            # ============================================================
            candidate_status_counts = (
                session.query(BenchCandidate.status, func.count(BenchCandidate.id))
                .group_by(BenchCandidate.status)
                .all()
            )
            stats["candidate_status"] = {
                str(status): count for status, count in candidate_status_counts
            }

            candidate_source_counts = (
                session.query(BenchCandidate.source, func.count(BenchCandidate.id))
                .group_by(BenchCandidate.source)
                .all()
            )
            stats["candidate_source"] = {
                str(source): count for source, count in candidate_source_counts
            }

            # ============================================================
            # Image Statistics
            # ============================================================
            images_successful = (
                session.query(Image).filter(Image.capture_success.is_(True)).count()
            )
            images_failed = (
                session.query(Image).filter(Image.capture_success.is_(False)).count()
            )
            stats["images"] = {
                "total": stats["total_images"],
                "successful": images_successful,
                "failed": images_failed,
                "success_rate": (
                    round(images_successful / stats["total_images"] * 100, 2)
                    if stats["total_images"] > 0
                    else 0.0
                ),
            }

            # Image file size statistics
            image_size_stats = (
                session.query(
                    func.avg(Image.file_size).label("avg_size"),
                    func.min(Image.file_size).label("min_size"),
                    func.max(Image.file_size).label("max_size"),
                    func.sum(Image.file_size).label("total_size"),
                )
                .filter(Image.file_size.isnot(None))
                .first()
            )
            if image_size_stats and image_size_stats.avg_size:
                stats["image_sizes"] = {
                    "avg_bytes": int(image_size_stats.avg_size),
                    "min_bytes": int(image_size_stats.min_size or 0),
                    "max_bytes": int(image_size_stats.max_size or 0),
                    "total_bytes": int(image_size_stats.total_size or 0),
                    "total_mb": round(image_size_stats.total_size / (1024 * 1024), 2)
                    if image_size_stats.total_size
                    else 0.0,
                }

            # ============================================================
            # Detection Statistics
            # ============================================================
            detections_successful = (
                session.query(Detection)
                .filter(Detection.detection_success.is_(True))
                .count()
            )
            detections_failed = (
                session.query(Detection)
                .filter(Detection.detection_success.is_(False))
                .count()
            )
            detections_with_bench = (
                session.query(Detection).filter(Detection.has_bench.is_(True)).count()
            )
            stats["detections"] = {
                "total": stats["total_detections"],
                "successful": detections_successful,
                "failed": detections_failed,
                "with_bench": detections_with_bench,
                "success_rate": (
                    round(detections_successful / stats["total_detections"] * 100, 2)
                    if stats["total_detections"] > 0
                    else 0.0
                ),
                "bench_detection_rate": (
                    round(detections_with_bench / stats["total_detections"] * 100, 2)
                    if stats["total_detections"] > 0
                    else 0.0
                ),
            }

            # Detection source breakdown
            detection_source_counts = (
                session.query(Detection.source, func.count(Detection.id))
                .group_by(Detection.source)
                .all()
            )
            stats["detection_sources"] = {
                str(source): count for source, count in detection_source_counts
            }

            # Confidence statistics
            confidence_stats = (
                session.query(
                    func.avg(Detection.max_confidence).label("avg_confidence"),
                    func.min(Detection.max_confidence).label("min_confidence"),
                    func.max(Detection.max_confidence).label("max_confidence"),
                )
                .filter(Detection.max_confidence > 0)
                .first()
            )
            if confidence_stats and confidence_stats.avg_confidence:
                stats["confidence"] = {
                    "avg": round(confidence_stats.avg_confidence, 3),
                    "min": round(confidence_stats.min_confidence or 0.0, 3),
                    "max": round(confidence_stats.max_confidence or 0.0, 3),
                }

            # Bench count statistics
            bench_count_stats = (
                session.query(
                    func.avg(Detection.bench_count).label("avg_count"),
                    func.max(Detection.bench_count).label("max_count"),
                )
                .filter(Detection.bench_count > 0)
                .first()
            )
            if bench_count_stats and bench_count_stats.avg_count:
                stats["bench_counts"] = {
                    "avg_per_detection": round(bench_count_stats.avg_count, 2),
                    "max_per_detection": int(bench_count_stats.max_count or 0),
                }

            # ============================================================
            # Processed Bench Statistics
            # ============================================================
            processed_detected = (
                session.query(ProcessedBench)
                .filter(ProcessedBench.detection_status == "detected")
                .count()
            )
            processed_no_bench = (
                session.query(ProcessedBench)
                .filter(ProcessedBench.detection_status == "no_bench")
                .count()
            )
            stats["processed_benches"] = {
                "total": stats["total_processed_benches"],
                "detected": processed_detected,
                "no_bench": processed_no_bench,
                "detection_rate": (
                    round(
                        processed_detected / stats["total_processed_benches"] * 100, 2
                    )
                    if stats["total_processed_benches"] > 0
                    else 0.0
                ),
            }

            # ============================================================
            # Foreign Key Relationship Statistics
            # ============================================================
            # Candidates without ProcessedBench records
            candidates_without_processed = (
                session.query(BenchCandidate)
                .outerjoin(
                    ProcessedBench,
                    BenchCandidate.id == ProcessedBench.bench_candidate_id,
                )
                .filter(ProcessedBench.id.is_(None))
                .count()
            )

            # Candidates without Images
            candidates_without_images = (
                session.query(BenchCandidate)
                .outerjoin(Image, BenchCandidate.id == Image.bench_candidate_id)
                .filter(Image.id.is_(None))
                .count()
            )

            # Candidates with images count
            candidates_with_images = (
                session.query(BenchCandidate)
                .join(Image, BenchCandidate.id == Image.bench_candidate_id)
                .distinct()
                .count()
            )

            # Images without Detections
            images_without_detections = (
                session.query(Image)
                .outerjoin(Detection, Image.id == Detection.image_id)
                .filter(Detection.id.is_(None))
                .count()
            )

            # Images with detections count
            images_with_detections = (
                session.query(Image)
                .join(Detection, Image.id == Detection.image_id)
                .distinct()
                .count()
            )

            # Detections without DetectionItems
            detections_without_items = (
                session.query(Detection)
                .outerjoin(DetectionItem, Detection.id == DetectionItem.detection_id)
                .filter(DetectionItem.id.is_(None))
                .count()
            )

            # Detections with items count
            detections_with_items = (
                session.query(Detection)
                .join(DetectionItem, Detection.id == DetectionItem.detection_id)
                .distinct()
                .count()
            )

            # ProcessedBenches with null best_image_id (detected status should have this)
            processed_with_null_image = (
                session.query(ProcessedBench)
                .filter(
                    ProcessedBench.detection_status == "detected",
                    ProcessedBench.best_image_id.is_(None),
                )
                .count()
            )

            # ProcessedBenches with null best_detection_id (detected status should have this)
            processed_with_null_detection = (
                session.query(ProcessedBench)
                .filter(
                    ProcessedBench.detection_status == "detected",
                    ProcessedBench.best_detection_id.is_(None),
                )
                .count()
            )

            # Images with null filepath
            images_without_filepath = (
                session.query(Image).filter(Image.filepath.is_(None)).count()
            )

            # Images with filepath but file doesn't exist
            images_with_missing_files = 0
            if stats["total_images"] > 0:
                all_images = (
                    session.query(Image).filter(Image.filepath.isnot(None)).all()
                )
                for img in all_images:
                    if img.filepath and not os.path.exists(img.filepath):
                        images_with_missing_files += 1

            stats["foreign_keys"] = {
                "candidates_without_processed": candidates_without_processed,
                "candidates_with_images": candidates_with_images,
                "candidates_without_images": candidates_without_images,
                "images_with_detections": images_with_detections,
                "images_without_detections": images_without_detections,
                "detections_with_items": detections_with_items,
                "detections_without_items": detections_without_items,
                "processed_with_null_image": processed_with_null_image,
                "processed_with_null_detection": processed_with_null_detection,
                "images_without_filepath": images_without_filepath,
                "images_with_missing_files": images_with_missing_files,
            }

            # Calculate percentages
            if stats["total_bench_candidates"] > 0:
                stats["foreign_keys"]["candidates_without_processed_pct"] = round(
                    candidates_without_processed
                    / stats["total_bench_candidates"]
                    * 100,
                    2,
                )
                stats["foreign_keys"]["candidates_without_images_pct"] = round(
                    candidates_without_images / stats["total_bench_candidates"] * 100, 2
                )
            else:
                stats["foreign_keys"]["candidates_without_processed_pct"] = 0.0
                stats["foreign_keys"]["candidates_without_images_pct"] = 0.0

            if stats["total_images"] > 0:
                stats["foreign_keys"]["images_without_detections_pct"] = round(
                    images_without_detections / stats["total_images"] * 100, 2
                )
            else:
                stats["foreign_keys"]["images_without_detections_pct"] = 0.0

            if stats["total_detections"] > 0:
                stats["foreign_keys"]["detections_without_items_pct"] = round(
                    detections_without_items / stats["total_detections"] * 100, 2
                )
            else:
                stats["foreign_keys"]["detections_without_items_pct"] = 0.0

            # ============================================================
            # Bench Report Statistics
            # ============================================================
            report_type_counts = (
                session.query(BenchReport.report_type, func.count(BenchReport.id))
                .group_by(BenchReport.report_type)
                .all()
            )
            stats["bench_reports"] = {
                "total": stats["total_bench_reports"],
                "by_type": {str(rtype): count for rtype, count in report_type_counts},
            }

            report_status_counts = (
                session.query(BenchReport.status, func.count(BenchReport.id))
                .group_by(BenchReport.status)
                .all()
            )
            stats["bench_reports"]["by_status"] = {
                str(status): count for status, count in report_status_counts
            }

            # ============================================================
            # Missing Bench Report Statistics
            # ============================================================
            missing_report_status_counts = (
                session.query(
                    MissingBenchReport.status, func.count(MissingBenchReport.id)
                )
                .group_by(MissingBenchReport.status)
                .all()
            )
            stats["missing_bench_reports"] = {
                "total": stats["total_missing_bench_reports"],
                "by_status": {
                    str(status): count for status, count in missing_report_status_counts
                },
            }

            # ============================================================
            # Recent Activity
            # ============================================================
            latest_search = (
                session.query(Search).order_by(Search.created_at.desc()).first()
            )
            stats["recent_activity"] = {}
            if latest_search:
                stats["recent_activity"]["latest_search"] = {
                    "id": latest_search.id,
                    "query": latest_search.query,
                    "status": str(latest_search.status),
                    "created_at": latest_search.created_at.isoformat()
                    if latest_search.created_at
                    else None,
                    "candidates": session.query(BenchCandidate)
                    .filter(BenchCandidate.search_id == latest_search.id)
                    .count(),
                }

            latest_candidate = (
                session.query(BenchCandidate)
                .order_by(BenchCandidate.created_at.desc())
                .first()
            )
            if latest_candidate:
                stats["recent_activity"]["latest_candidate"] = {
                    "id": latest_candidate.id,
                    "source": str(latest_candidate.source),
                    "status": str(latest_candidate.status),
                    "created_at": latest_candidate.created_at.isoformat()
                    if latest_candidate.created_at
                    else None,
                }

            latest_image = (
                session.query(Image).order_by(Image.created_at.desc()).first()
            )
            if latest_image:
                stats["recent_activity"]["latest_image"] = {
                    "id": latest_image.id,
                    "success": latest_image.capture_success,
                    "file_size": latest_image.file_size,
                    "created_at": latest_image.created_at.isoformat()
                    if latest_image.created_at
                    else None,
                }

            latest_detection = (
                session.query(Detection).order_by(Detection.created_at.desc()).first()
            )
            if latest_detection:
                stats["recent_activity"]["latest_detection"] = {
                    "id": latest_detection.id,
                    "has_bench": latest_detection.has_bench,
                    "confidence": latest_detection.max_confidence,
                    "source": str(latest_detection.source),
                    "created_at": latest_detection.created_at.isoformat()
                    if latest_detection.created_at
                    else None,
                }

        # Display statistics
        if format == "json":
            import json

            console.print(json.dumps(stats, indent=2))
        else:
            _display_statistics_table(stats)

    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Operation cancelled by user[/bold yellow]")
        raise typer.Exit(130) from None
    except Exception as e:
        console.print(f"[bold red]💥 Unexpected error: {e}[/bold red]")
        logger.exception("Unexpected error")
        raise typer.Exit(1) from e


def _display_statistics_table(stats: dict):
    """Display statistics in a formatted table."""
    console.print("[bold blue]📊 Database Statistics[/bold blue]\n")

    # Overall counts
    table = Table(title="Overall Counts", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green", justify="right")
    table.add_row("Searches", str(stats["total_searches"]))
    table.add_row("Bench Candidates", str(stats["total_bench_candidates"]))
    table.add_row("Images", str(stats["total_images"]))
    table.add_row("Detections", str(stats["total_detections"]))
    table.add_row("Detection Items", str(stats["total_detection_items"]))
    table.add_row("Processed Benches", str(stats["total_processed_benches"]))
    table.add_row("Bench Reports", str(stats["total_bench_reports"]))
    table.add_row("Missing Bench Reports", str(stats["total_missing_bench_reports"]))
    console.print(table)
    console.print()

    # Search breakdown
    if stats.get("search_status"):
        table = Table(title="Searches by Status", show_header=True)
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="green", justify="right")
        for status, count in sorted(stats["search_status"].items()):
            table.add_row(status, str(count))
        console.print(table)
        console.print()

    # Bench candidate breakdowns
    if stats.get("candidate_status"):
        table = Table(title="Bench Candidates by Status", show_header=True)
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="green", justify="right")
        for status, count in sorted(stats["candidate_status"].items()):
            table.add_row(status, str(count))
        console.print(table)
        console.print()

    if stats.get("candidate_source"):
        table = Table(title="Bench Candidates by Source", show_header=True)
        table.add_column("Source", style="cyan")
        table.add_column("Count", style="green", justify="right")
        for source, count in sorted(stats["candidate_source"].items()):
            table.add_row(source, str(count))
        console.print(table)
        console.print()

    # Image statistics
    if stats.get("images"):
        img_stats = stats["images"]
        table = Table(title="Image Statistics", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")
        table.add_row("Total Images", str(img_stats["total"]))
        table.add_row("Successful", str(img_stats["successful"]))
        table.add_row("Failed", str(img_stats["failed"]))
        table.add_row("Success Rate", f"{img_stats['success_rate']}%")
        console.print(table)

        if stats.get("image_sizes"):
            size_stats = stats["image_sizes"]
            table = Table(title="Image Storage", show_header=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green", justify="right")
            table.add_row("Total Size", f"{size_stats['total_mb']} MB")
            table.add_row("Average Size", f"{size_stats['avg_bytes']:,} bytes")
            table.add_row("Min Size", f"{size_stats['min_bytes']:,} bytes")
            table.add_row("Max Size", f"{size_stats['max_bytes']:,} bytes")
            console.print(table)
        console.print()

    # Detection statistics
    if stats.get("detections"):
        det_stats = stats["detections"]
        table = Table(title="Detection Statistics", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")
        table.add_row("Total Detections", str(det_stats["total"]))
        table.add_row("Successful", str(det_stats["successful"]))
        table.add_row("Failed", str(det_stats["failed"]))
        table.add_row("With Bench", str(det_stats["with_bench"]))
        table.add_row("Success Rate", f"{det_stats['success_rate']}%")
        table.add_row("Bench Detection Rate", f"{det_stats['bench_detection_rate']}%")
        console.print(table)

        if stats.get("detection_sources"):
            table = Table(title="Detections by Source", show_header=True)
            table.add_column("Source", style="cyan")
            table.add_column("Count", style="green", justify="right")
            for source, count in sorted(stats["detection_sources"].items()):
                table.add_row(source, str(count))
            console.print(table)

        if stats.get("confidence"):
            conf_stats = stats["confidence"]
            table = Table(title="Confidence Statistics", show_header=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green", justify="right")
            table.add_row("Average", f"{conf_stats['avg']:.3f}")
            table.add_row("Minimum", f"{conf_stats['min']:.3f}")
            table.add_row("Maximum", f"{conf_stats['max']:.3f}")
            console.print(table)

        if stats.get("bench_counts"):
            bench_stats = stats["bench_counts"]
            table = Table(title="Bench Count per Detection", show_header=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green", justify="right")
            table.add_row("Average", f"{bench_stats['avg_per_detection']:.2f}")
            table.add_row("Maximum", str(bench_stats["max_per_detection"]))
            console.print(table)
        console.print()

    # Processed bench statistics
    if stats.get("processed_benches"):
        proc_stats = stats["processed_benches"]
        table = Table(title="Processed Benches", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")
        table.add_row("Total", str(proc_stats["total"]))
        table.add_row("Detected", str(proc_stats["detected"]))
        table.add_row("No Bench", str(proc_stats["no_bench"]))
        table.add_row("Detection Rate", f"{proc_stats['detection_rate']}%")
        console.print(table)
        console.print()

    # Foreign key relationship statistics
    if stats.get("foreign_keys"):
        fk_stats = stats["foreign_keys"]
        table = Table(title="Foreign Key Relationships", show_header=True)
        table.add_column("Relationship", style="cyan")
        table.add_column("Count", style="green", justify="right")
        table.add_column("Percentage", style="yellow", justify="right")

        # Candidates relationships
        table.add_row(
            "Candidates WITHOUT ProcessedBench",
            str(fk_stats["candidates_without_processed"]),
            f"{fk_stats.get('candidates_without_processed_pct', 0.0)}%",
        )
        table.add_row(
            "Candidates WITH Images",
            str(fk_stats["candidates_with_images"]),
            "-",
        )
        table.add_row(
            "Candidates WITHOUT Images",
            str(fk_stats["candidates_without_images"]),
            f"{fk_stats.get('candidates_without_images_pct', 0.0)}%",
        )

        # Images relationships
        table.add_row(
            "Images WITH Detections",
            str(fk_stats["images_with_detections"]),
            "-",
        )
        table.add_row(
            "Images WITHOUT Detections",
            str(fk_stats["images_without_detections"]),
            f"{fk_stats.get('images_without_detections_pct', 0.0)}%",
        )

        # Detections relationships
        table.add_row(
            "Detections WITH Items",
            str(fk_stats["detections_with_items"]),
            "-",
        )
        table.add_row(
            "Detections WITHOUT Items",
            str(fk_stats["detections_without_items"]),
            f"{fk_stats.get('detections_without_items_pct', 0.0)}%",
        )

        console.print(table)

        # Data integrity issues
        issues = []
        if fk_stats["processed_with_null_image"] > 0:
            issues.append(
                f"  ⚠️  {fk_stats['processed_with_null_image']} ProcessedBenches with 'detected' status but NULL best_image_id"
            )
        if fk_stats["processed_with_null_detection"] > 0:
            issues.append(
                f"  ⚠️  {fk_stats['processed_with_null_detection']} ProcessedBenches with 'detected' status but NULL best_detection_id"
            )
        if fk_stats["images_without_filepath"] > 0:
            issues.append(
                f"  ⚠️  {fk_stats['images_without_filepath']} Images without filepath"
            )
        if fk_stats["images_with_missing_files"] > 0:
            issues.append(
                f"  ⚠️  {fk_stats['images_with_missing_files']} Images with filepath but file doesn't exist"
            )

        if issues:
            console.print("\n[bold yellow]Data Integrity Issues:[/bold yellow]")
            for issue in issues:
                console.print(issue)
            console.print()

    # Bench reports
    if stats.get("bench_reports") and stats["bench_reports"]["total"] > 0:
        report_stats = stats["bench_reports"]
        table = Table(title="Bench Reports", show_header=True)
        table.add_column("Type/Status", style="cyan")
        table.add_column("Count", style="green", justify="right")
        table.add_row("Total", str(report_stats["total"]))
        if report_stats.get("by_type"):
            for rtype, count in sorted(report_stats["by_type"].items()):
                table.add_row(f"Type: {rtype}", str(count))
        if report_stats.get("by_status"):
            for status, count in sorted(report_stats["by_status"].items()):
                table.add_row(f"Status: {status}", str(count))
        console.print(table)
        console.print()

    # Missing bench reports
    if (
        stats.get("missing_bench_reports")
        and stats["missing_bench_reports"]["total"] > 0
    ):
        missing_stats = stats["missing_bench_reports"]
        table = Table(title="Missing Bench Reports", show_header=True)
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="green", justify="right")
        table.add_row("Total", str(missing_stats["total"]))
        if missing_stats.get("by_status"):
            for status, count in sorted(missing_stats["by_status"].items()):
                table.add_row(status, str(count))
        console.print(table)
        console.print()

    # Recent activity
    if stats.get("recent_activity"):
        console.print("[bold]Recent Activity:[/bold]")
        recent = stats["recent_activity"]
        if recent.get("latest_search"):
            ls = recent["latest_search"]
            console.print(
                f"  Latest Search: ID {ls['id']} - '{ls['query']}' ({ls['status']}) - "
                f"{ls['candidates']} candidates - {ls['created_at']}"
            )
        if recent.get("latest_candidate"):
            lc = recent["latest_candidate"]
            console.print(
                f"  Latest Candidate: ID {lc['id']} - {lc['source']} ({lc['status']}) - "
                f"{lc['created_at']}"
            )
        if recent.get("latest_image"):
            li = recent["latest_image"]
            status_str = "✅" if li["success"] else "❌"
            size_str = f"{li['file_size']:,} bytes" if li["file_size"] else "N/A"
            console.print(
                f"  Latest Image: ID {li['id']} - {status_str} ({size_str}) - {li['created_at']}"
            )
        if recent.get("latest_detection"):
            ld = recent["latest_detection"]
            bench_str = "✅ Bench" if ld["has_bench"] else "❌ No Bench"
            console.print(
                f"  Latest Detection: ID {ld['id']} - {bench_str} (conf: {ld['confidence']:.3f}, "
                f"source: {ld['source']}) - {ld['created_at']}"
            )
        console.print()


@app.command("stitch-lookaround")
def stitch_lookaround(
    images_dir: str = typer.Option(
        None,
        "--images-dir",
        help="Directory containing images (defaults to IMAGES_DIR from config)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without creating stitched images",
    ),
    stitch_method: str = typer.Option(
        "net",
        "--method",
        help="Stitching method: net (cube net) or row (horizontal row) - DEPRECATED, now uses to_equirectangular",
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
):
    """
    Stitch Apple Look Around face images into equirectangular panoramas.

    Scans the images directory for lookaround face images (6 faces per bench),
    and creates stitched equirectangular images for any bench that has all 6 faces
    but no existing stitched image.

    Uses streetlevel.lookaround.to_equirectangular() to create proper equirectangular
    projections from the cubemap faces.

    Face files follow the pattern: bench_{id}_lookaround_face_{face}.jpg
    where face is one of: back, left, front, right, top, bottom

    Stitched output: bench_{id}_lookaround_stitched.jpg
    """
    import json
    import re
    from collections import defaultdict
    from pathlib import Path

    from PIL import Image as PILImage
    from streetlevel import lookaround

    from bench_finder.config import IMAGES_DIR

    # Increase PIL limit for large images
    PILImage.MAX_IMAGE_PIXELS = 300_000_000

    # Setup logging
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)

    # Get images directory
    images_path = Path(images_dir) if images_dir else Path(IMAGES_DIR)
    if not images_path.exists():
        console.print(f"[red]Images directory not found: {images_path}[/red]")
        raise typer.Exit(1)

    console.print(
        f"[bold blue]🔍 Scanning for lookaround faces in: {images_path}[/bold blue]"
    )

    # Note: stitch_method parameter is kept for backward compatibility but ignored
    # We now always use to_equirectangular from streetlevel.lookaround

    # Face names in our file naming convention
    # Our order: back=0, left=1, front=2, right=3, top=4, bottom=5
    # to_equirectangular expects faces in order: [0, 1, 2, 3, 4, 5] (back, left, front, right, top, bottom)
    face_names = ["back", "left", "front", "right", "top", "bottom"]

    # Pattern to match lookaround face files
    # bench_{id}_lookaround_face_{face}.jpg
    face_pattern = re.compile(
        r"^bench_(.+)_lookaround_face_(back|left|front|right|top|bottom)\.jpg$"
    )

    # Group faces by bench ID
    bench_faces: dict[str, dict[str, Path]] = defaultdict(dict)

    for file_path in images_path.glob("bench_*_lookaround_face_*.jpg"):
        match = face_pattern.match(file_path.name)
        if match:
            bench_id = match.group(1)
            face_name = match.group(2)
            bench_faces[bench_id][face_name] = file_path

    console.print(f"[dim]Found {len(bench_faces)} benches with lookaround faces[/dim]")

    # Find benches with all 6 faces but no stitched image
    benches_to_stitch = []
    benches_already_stitched = 0
    benches_incomplete = 0

    for bench_id, faces in bench_faces.items():
        stitched_path = images_path / f"bench_{bench_id}_lookaround_stitched.jpg"

        if stitched_path.exists():
            benches_already_stitched += 1
            continue

        if len(faces) == 6:
            benches_to_stitch.append((bench_id, faces, stitched_path))
        else:
            benches_incomplete += 1
            missing = set(face_names) - set(faces.keys())
            logger.debug(f"Bench {bench_id} missing faces: {missing}")

    console.print(f"[dim]  • Already stitched: {benches_already_stitched}[/dim]")
    console.print(f"[dim]  • Incomplete (missing faces): {benches_incomplete}[/dim]")
    console.print(f"[dim]  • Ready to stitch: {len(benches_to_stitch)}[/dim]")

    if not benches_to_stitch:
        console.print("[green]✅ No benches need stitching[/green]")
        return

    if dry_run:
        console.print("\n[yellow]🔍 DRY RUN - Would stitch the following:[/yellow]")
        for bench_id, faces, stitched_path in benches_to_stitch[:20]:
            console.print(f"  • {bench_id} -> {stitched_path.name}")
        if len(benches_to_stitch) > 20:
            console.print(f"  ... and {len(benches_to_stitch) - 20} more")
        return

    # Stitch the images
    console.print(
        f"\n[bold blue]🧵 Stitching {len(benches_to_stitch)} lookaround panoramas...[/bold blue]"
    )

    stitched_count = 0
    error_count = 0

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
            "🧵 Stitching lookaround faces",
            total=len(benches_to_stitch),
        )

        for bench_id, faces, stitched_path in benches_to_stitch:
            try:
                # Load metadata file if it exists
                metadata_path = images_path / f"bench_{bench_id}_lookaround_metadata.json"
                metadata = None
                if metadata_path.exists():
                    try:
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                        logger.debug(f"Loaded metadata for bench {bench_id} from {metadata_path.name}")
                    except Exception as e:
                        logger.warning(f"Failed to load metadata from {metadata_path.name}: {e}")

                # Try to get panorama metadata from database if not in file
                if not metadata or not metadata.get("pano_id"):
                    try:
                        from bench_finder.services.database import BenchDatabase
                        db = BenchDatabase()
                        with db.get_session() as session:
                            from bench_finder.models.unified_models import Image
                            # Look for an image with this bench_id pattern in panorama_metadata
                            # bench_id might be a string identifier, try to find matching images
                            images = (
                                session.query(Image)
                                .filter(
                                    Image.image_source == "apple_streetlevel",
                                    Image.panorama_metadata.isnot(None),
                                )
                                .all()
                            )
                            # Find image with matching bench_id in metadata or filename
                            for img in images:
                                if img.panorama_metadata and img.panorama_metadata.get("pano_id"):
                                    # Check if this image's bench_candidate might match
                                    # We'll use the first one we find with panorama metadata
                                    if not metadata:
                                        metadata = {
                                            "pano_id": img.panorama_metadata.get("pano_id"),
                                            "panorama_lat": img.panorama_lat,
                                            "panorama_lng": img.panorama_lng,
                                        }
                                        logger.debug(f"Found metadata for bench {bench_id} from database")
                                        break
                    except Exception as e:
                        logger.debug(f"Could not get metadata from database: {e}")

                # If we still don't have metadata, we can't proceed
                if not metadata or not metadata.get("pano_id"):
                    logger.warning(
                        f"Bench {bench_id}: No panorama metadata found. "
                        "Cannot use to_equirectangular without pano_id. "
                        "Skipping this bench."
                    )
                    error_count += 1
                    progress.update(task, advance=1)
                    continue

                # Load faces in order: back, left, front, right, top, bottom
                face_images = []
                for face_name in face_names:
                    img = PILImage.open(faces[face_name])
                    face_images.append(img)

                # Re-fetch panorama to get camera_metadata
                panorama_lat = metadata.get("panorama_lat")
                panorama_lng = metadata.get("panorama_lng")
                pano_id = metadata.get("pano_id")

                if not panorama_lat or not panorama_lng:
                    logger.warning(
                        f"Bench {bench_id}: Missing panorama coordinates in metadata. "
                        "Cannot re-fetch panorama for camera_metadata."
                    )
                    error_count += 1
                    for img in face_images:
                        img.close()
                    progress.update(task, advance=1)
                    continue

                logger.debug(
                    f"Re-fetching panorama {pano_id} at ({panorama_lat}, {panorama_lng}) "
                    f"for bench {bench_id}"
                )

                # Get coverage tile and find panorama
                tile = lookaround.get_coverage_tile_by_latlon(panorama_lat, panorama_lng)
                if not tile or not tile.panos:
                    logger.warning(
                        f"Bench {bench_id}: Could not get coverage tile for panorama"
                    )
                    error_count += 1
                    for img in face_images:
                        img.close()
                    progress.update(task, advance=1)
                    continue

                # Find panorama by ID
                pano = None
                for candidate_pano in tile.panos:
                    if hasattr(candidate_pano, "id") and candidate_pano.id == pano_id:
                        pano = candidate_pano
                        break

                if not pano:
                    logger.warning(
                        f"Bench {bench_id}: Could not find panorama {pano_id} in coverage tile"
                    )
                    error_count += 1
                    for img in face_images:
                        img.close()
                    progress.update(task, advance=1)
                    continue

                # Get camera_metadata from panorama
                if not hasattr(pano, "camera_metadata") or not pano.camera_metadata:
                    logger.warning(
                        f"Bench {bench_id}: Panorama {pano_id} has no camera_metadata"
                    )
                    error_count += 1
                    for img in face_images:
                        img.close()
                    progress.update(task, advance=1)
                    continue

                # Use to_equirectangular to create equirectangular projection
                logger.debug(f"Creating equirectangular projection for bench {bench_id}")
                stitched = lookaround.to_equirectangular(face_images, pano.camera_metadata)

                # Save
                stitched.save(stitched_path, "JPEG", quality=95, options={"quality": 95})
                stitched_count += 1

                logger.debug(f"Stitched {bench_id} -> {stitched_path.name}")

                # Close images to free memory
                for img in face_images:
                    img.close()
                stitched.close()

            except Exception as e:
                error_count += 1
                logger.warning(f"Failed to stitch {bench_id}: {e}", exc_info=True)

            progress.update(task, advance=1)

    # Summary
    console.print("\n[bold green]✅ Stitching complete![/bold green]")
    console.print(f"[green]  • Successfully stitched: {stitched_count}[/green]")
    if error_count > 0:
        console.print(f"[yellow]  • Errors: {error_count}[/yellow]")


@app.command("backfill-panorama-heading")
def backfill_panorama_heading(
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview changes without updating database"
    ),
    limit: int | None = typer.Option(
        None, "--limit", help="Limit the number of images to process"
    ),
    batch_size: int = typer.Option(
        50, "--batch-size", help="Number of images to process in parallel"
    ),
):
    """
    Backfill panorama_heading for streetlevel and lookaround images.

    This command:
    1. Finds images with image_source = streetview_streetlevel or apple_streetlevel
    2. Re-fetches panorama data from the streetlevel API using pano_id (async batches)
    3. Extracts the heading from the API response
    4. Updates the panorama_heading field in the database

    Use --dry-run to preview changes without updating the database.
    Use --batch-size to control parallelism (default: 50).
    """
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)

    console.print(
        "[bold blue]🔄 Backfilling panorama_heading for streetlevel/lookaround images[/bold blue]\n"
    )

    try:
        import asyncio

        # Import streetlevel libraries
        from streetlevel import lookaround
        from streetlevel import streetview as streetlevel_streetview

        database = BenchDatabase()

        # Query images that need backfilling
        with database.get_session() as session:
            from sqlmodel import select

            from bench_finder.models.enums import ImageSource
            from bench_finder.models.unified_models import Image

            # Find images from streetlevel/lookaround sources that don't have panorama_heading yet
            statement = select(Image).where(
                Image.image_source.in_(
                    [
                        ImageSource.STREETVIEW_STREETLEVEL.value,
                        ImageSource.APPLE_STREETLEVEL.value,
                    ]
                ),
                Image.panorama_heading == None,
            )

            if limit:
                statement = statement.limit(limit)

            images = list(session.exec(statement).all())

        if not images:
            console.print(
                "[yellow]No streetlevel or lookaround images without panorama_heading found.[/yellow]"
            )
            return

        console.print(f"Found {len(images)} images to process\n")
        console.print(f"[dim]Processing in batches of {batch_size}...[/dim]\n")

        # Async function to process a single image
        async def process_image_async(image, session_aio):
            """Process a single image to fetch and update its panorama heading."""
            nonlocal updated_count, error_count, no_pano_id_count
            
            try:
                # Check if panorama_metadata has heading already (from new data)
                if (
                    image.panorama_metadata
                    and "heading" in image.panorama_metadata
                    and image.panorama_metadata["heading"] is not None
                ):
                    heading = image.panorama_metadata["heading"]
                    if not dry_run:
                        with database.get_session() as session:
                            db_image = session.get(Image, image.id)
                            if db_image:
                                db_image.panorama_heading = heading
                                session.add(db_image)
                                session.commit()
                    logger.debug(
                        f"Image {image.id}: Found heading in metadata: {heading}"
                    )
                    updated_count += 1
                    return True

                # Check if we have pano_id to re-fetch
                if not image.panorama_metadata or "pano_id" not in image.panorama_metadata:
                    logger.debug(f"Image {image.id}: No pano_id in metadata, skipping")
                    no_pano_id_count += 1
                    return False

                pano_id = image.panorama_metadata["pano_id"]
                if not pano_id:
                    logger.debug(f"Image {image.id}: Empty pano_id, skipping")
                    no_pano_id_count += 1
                    return False

                # Re-fetch panorama from API based on image_source
                heading = None
                if image.image_source == ImageSource.STREETVIEW_STREETLEVEL.value:
                    # Fetch from Google Street View (async)
                    try:
                        pano = await streetlevel_streetview.find_panorama_by_id_async(
                            pano_id, session_aio
                        )
                        if pano and hasattr(pano, "heading"):
                            heading = pano.heading
                            logger.debug(
                                f"Image {image.id}: Fetched heading from Street View: {heading}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Image {image.id}: Failed to fetch Street View panorama {pano_id}: {e}"
                        )
                        error_count += 1
                        return False

                elif image.image_source == ImageSource.APPLE_STREETLEVEL.value:
                    # Fetch from Apple Look Around (async)
                    if not image.panorama_lat or not image.panorama_lng:
                        logger.debug(
                            f"Image {image.id}: No panorama coordinates for Look Around, skipping"
                        )
                        no_pano_id_count += 1
                        return False

                    try:
                        tile = await lookaround.get_coverage_tile_by_latlon_async(
                            image.panorama_lat, image.panorama_lng, session=session_aio
                        )
                        if tile and tile.panos:
                            # Find the panorama with matching ID
                            for pano in tile.panos:
                                if hasattr(pano, "id") and pano.id == pano_id:
                                    if hasattr(pano, "heading"):
                                        heading = pano.heading
                                        logger.debug(
                                            f"Image {image.id}: Fetched heading from Look Around: {heading}"
                                        )
                                    break
                    except Exception as e:
                        logger.warning(
                            f"Image {image.id}: Failed to fetch Look Around panorama {pano_id}: {e}"
                        )
                        error_count += 1
                        return False

                # Update database if we got a heading
                if heading is not None:
                    if not dry_run:
                        with database.get_session() as session:
                            db_image = session.get(Image, image.id)
                            if db_image:
                                db_image.panorama_heading = heading
                                # Also update the metadata to include heading
                                if db_image.panorama_metadata:
                                    db_image.panorama_metadata["heading"] = heading
                                session.add(db_image)
                                session.commit()
                    else:
                        logger.info(
                            f"[DRY RUN] Would update image {image.id} with panorama_heading: {heading}"
                        )
                    updated_count += 1
                    return True
                else:
                    logger.debug(
                        f"Image {image.id}: Could not get heading from API for pano_id {pano_id}"
                    )
                    error_count += 1
                    return False

            except Exception as e:
                logger.exception(f"Error processing image {image.id}: {e}")
                error_count += 1
                return False

        # Async function to process a batch of images
        async def process_batch_async(batch):
            """Process a batch of images in parallel."""
            import aiohttp

            async with aiohttp.ClientSession() as session_aio:
                tasks = [process_image_async(image, session_aio) for image in batch]
                return await asyncio.gather(*tasks, return_exceptions=True)

        # Process images in batches
        updated_count = 0
        error_count = 0
        no_pano_id_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Processing images...", total=len(images)
            )

            for i in range(0, len(images), batch_size):
                batch = images[i : i + batch_size]
                
                # Process batch asynchronously
                asyncio.run(process_batch_async(batch))
                
                # Update progress
                progress.update(task, advance=len(batch))

        # Summary
        console.print("\n[bold green]✅ Backfill complete![/bold green]")
        if dry_run:
            console.print("[yellow]  (DRY RUN - no changes made)[/yellow]")
        console.print(f"[green]  • Updated: {updated_count}[/green]")
        console.print(f"[dim]  • No pano_id in metadata: {no_pano_id_count}[/dim]")
        if error_count > 0:
            console.print(f"[yellow]  • Errors: {error_count}[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Unexpected error during backfill")
        raise typer.Exit(1) from e


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    app()
