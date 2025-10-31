"""
Cleanup script to remove OSM bench candidates that have been deleted from OpenStreetMap.

This script:
1. Fetches all OSM bench candidates from the database
2. Checks if they still exist in OSM using the OSM Direct API (api.openstreetmap.org)
3. Deletes candidates and their ProcessedBench entries if they've been removed from OSM
"""

import logging
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import requests
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn


# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bench_finder.models.enums import DataSource  # noqa: E402
from bench_finder.models.unified_models import (  # noqa: E402
    BenchCandidate,
    ProcessedBench,
)
from bench_finder.services.database import BenchDatabase  # noqa: E402


logger = logging.getLogger(__name__)
console = Console()

# OSM Direct API configuration
OSM_API_BASE_URL = "https://api.openstreetmap.org/api/0.6"
OSM_API_TIMEOUT = 30  # seconds
# OSM API has a limit of ~725 items per request, so we use 700 to be safe
OSM_API_MAX_IDS_PER_REQUEST = 700


def check_osm_elements_bulk(
    osm_ids_by_type: dict[str, list[int]], timeout: int = OSM_API_TIMEOUT
) -> set[str]:
    """
    Check which OSM elements still exist using the OSM Direct API.

    Args:
        osm_ids_by_type: Dictionary mapping OSM type ("node", "way", "relation") to list of IDs
        timeout: Request timeout in seconds

    Returns:
        Set of provider_ids (format: "{osm_id}_{osm_type}") that still exist in OSM
    """
    existing_provider_ids = set()

    # Process each type separately
    for osm_type, osm_ids in osm_ids_by_type.items():
        if not osm_ids:
            continue

        # Split into chunks to respect OSM API limit
        for i in range(0, len(osm_ids), OSM_API_MAX_IDS_PER_REQUEST):
            chunk = osm_ids[i : i + OSM_API_MAX_IDS_PER_REQUEST]

            try:
                # OSM Direct API format: /api/0.6/nodes?nodes=id1,id2,id3
                ids_str = ",".join(str(osm_id) for osm_id in chunk)
                url = f"{OSM_API_BASE_URL}/{osm_type}s?{osm_type}s={ids_str}"

                logger.debug(
                    f"Checking {len(chunk)} {osm_type} elements via OSM Direct API"
                )

                response = requests.get(url, timeout=timeout)
                response.raise_for_status()

                # Parse XML response
                root = ET.fromstring(response.text)

                # Extract existing IDs from XML
                existing_in_chunk = 0
                for element in root:
                    # Elements are like <node id="123" ... />, <way id="456" ... />, etc.
                    osm_id_attr = element.get("id")
                    if osm_id_attr:
                        try:
                            osm_id = int(osm_id_attr)
                            provider_id = f"{osm_id}_{osm_type}"
                            existing_provider_ids.add(provider_id)
                            existing_in_chunk += 1
                        except ValueError:
                            logger.warning(
                                f"Invalid OSM ID format in response: {osm_id_attr}"
                            )

                logger.debug(
                    f"Found {existing_in_chunk} existing {osm_type} elements out of {len(chunk)} checked"
                )

            except requests.exceptions.HTTPError as e:
                # If we get a 404 or other error, it might mean the elements don't exist
                # or there's an API issue. Log and continue - we'll treat missing elements as deleted.
                logger.warning(
                    f"HTTP error checking {osm_type} elements (chunk {i//OSM_API_MAX_IDS_PER_REQUEST + 1}): {e}"
                )
                # Don't add these IDs to existing_provider_ids - they'll be treated as deleted
            except Exception:
                logger.exception(
                    f"Error checking {osm_type} elements (chunk {i//OSM_API_MAX_IDS_PER_REQUEST + 1})"
                )
                # On unexpected error, assume all exist in this chunk to avoid false positives
                # (but log the error so we know something went wrong)
                for osm_id in chunk:
                    provider_id = f"{osm_id}_{osm_type}"
                    existing_provider_ids.add(provider_id)

    return existing_provider_ids


def parse_provider_id(provider_id: str) -> tuple[int, str] | None:
    """
    Parse provider_id to extract OSM ID and type.

    Args:
        provider_id: Provider ID in format "{osm_id}_{osm_type}"

    Returns:
        Tuple of (osm_id, osm_type) or None if invalid format
    """
    try:
        parts = provider_id.split("_")
        if len(parts) < 2:
            return None

        # Handle cases where OSM ID might contain underscores
        # e.g., "123456_node" -> (123456, "node")
        # Try to find the last underscore and split there
        osm_type = parts[-1]
        osm_id_str = "_".join(parts[:-1])

        osm_id = int(osm_id_str)
        return (osm_id, osm_type)
    except (ValueError, IndexError):
        logger.warning(f"Invalid provider_id format: {provider_id}")
        return None


def cleanup_deleted_osm_benches(
    dry_run: bool = True, batch_size: int = 700
) -> dict[str, int]:
    """
    Check all OSM bench candidates and remove those that have been deleted from OSM.

    Args:
        dry_run: If True, only report what would be deleted without actually deleting
        batch_size: Number of candidates to check per batch (default: 700, OSM API limit is ~725)

    Returns:
        Dictionary with statistics about the cleanup operation
    """
    database = BenchDatabase()

    stats = {
        "total_osm_candidates": 0,
        "checked": 0,
        "deleted_candidates": 0,
        "deleted_processed_benches": 0,
        "errors": 0,
    }

    try:
        # Get all OSM bench candidates
        with database.get_session() as session:
            all_candidates = (
                session.query(BenchCandidate)
                .filter(BenchCandidate.source == DataSource.OSM)
                .all()
            )

        stats["total_osm_candidates"] = len(all_candidates)

        if not all_candidates:
            console.print("[yellow]No OSM bench candidates found in database[/yellow]")
            return stats

        console.print(
            f"[bold blue]🔍 Found {len(all_candidates)} OSM bench candidates to check[/bold blue]"
        )

        # Group candidates by OSM type for bulk queries
        osm_ids_by_type: dict[str, list[int]] = defaultdict(list)
        candidate_map: dict[str, BenchCandidate] = {}

        for candidate in all_candidates:
            if not candidate.provider_id:
                logger.warning(f"Candidate {candidate.id} has no provider_id, skipping")
                stats["errors"] += 1
                continue

            parsed = parse_provider_id(candidate.provider_id)
            if not parsed:
                logger.warning(
                    f"Candidate {candidate.id} has invalid provider_id format: {candidate.provider_id}"
                )
                stats["errors"] += 1
                continue

            osm_id, osm_type = parsed
            osm_ids_by_type[osm_type].append(osm_id)
            candidate_map[candidate.provider_id] = candidate

        console.print(
            f"[dim]Grouped into {len(osm_ids_by_type)} OSM types for bulk checking[/dim]\n"
        )

        # Check candidates in batches to respect OSM API limits
        all_candidates_to_check = list(candidate_map.keys())
        deleted_candidate_ids = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Checking OSM candidates...", total=len(all_candidates_to_check)
            )

            # Process in batches
            for i in range(0, len(all_candidates_to_check), batch_size):
                batch = all_candidates_to_check[i : i + batch_size]

                # Rebuild osm_ids_by_type for this batch
                batch_osm_ids_by_type: dict[str, list[int]] = defaultdict(list)
                for provider_id in batch:
                    parsed = parse_provider_id(provider_id)
                    if parsed:
                        osm_id, osm_type = parsed
                        batch_osm_ids_by_type[osm_type].append(osm_id)

                # Check which elements still exist using OSM Direct API
                existing_provider_ids = check_osm_elements_bulk(batch_osm_ids_by_type)

                # Find deleted candidates
                deleted_candidate_ids.extend(
                    candidate_map[provider_id].id
                    for provider_id in batch
                    if provider_id not in existing_provider_ids
                )

                stats["checked"] += len(batch)
                progress.update(task, completed=stats["checked"])

        deleted_count = len(deleted_candidate_ids)

        if deleted_count == 0:
            console.print(
                "\n[bold green]✅ All OSM bench candidates still exist in OpenStreetMap[/bold green]"
            )
            return stats

        console.print(
            f"\n[bold yellow]⚠️  Found {deleted_count} deleted OSM bench candidates[/bold yellow]"
        )

        if dry_run:
            console.print(
                "[yellow][DRY RUN] Would delete the following candidates:[/yellow]"
            )
            with database.get_session() as session:
                for candidate_id in deleted_candidate_ids[:10]:  # Show first 10
                    candidate = (
                        session.query(BenchCandidate)
                        .filter(BenchCandidate.id == candidate_id)
                        .first()
                    )
                    if candidate:
                        console.print(
                            f"  • ID {candidate.id}: {candidate.provider_id} at ({candidate.lat:.6f}, {candidate.lng:.6f})"
                        )
                if deleted_count > 10:
                    console.print(f"  ... and {deleted_count - 10} more")
        else:
            # Actually delete the candidates and their ProcessedBench entries
            console.print(
                f"[bold red]🗑️  Deleting {deleted_count} deleted candidates...[/bold red]"
            )

            with database.get_session() as session:
                # Delete ProcessedBench entries first (due to foreign key constraint)
                processed_benches = (
                    session.query(ProcessedBench)
                    .filter(
                        ProcessedBench.bench_candidate_id.in_(deleted_candidate_ids)
                    )
                    .all()
                )

                for processed_bench in processed_benches:
                    session.delete(processed_bench)
                    stats["deleted_processed_benches"] += 1

                # Delete BenchCandidate entries (cascade will handle related images/detections)
                deleted_candidates = (
                    session.query(BenchCandidate)
                    .filter(BenchCandidate.id.in_(deleted_candidate_ids))
                    .all()
                )

                for candidate in deleted_candidates:
                    console.print(
                        f"[dim]Deleting candidate {candidate.id}: {candidate.provider_id}[/dim]"
                    )
                    session.delete(candidate)
                    stats["deleted_candidates"] += 1

                session.commit()

            console.print("\n[bold green]✅ Cleanup complete![/bold green]")
            console.print(f"  • Deleted {stats['deleted_candidates']} bench candidates")
            console.print(
                f"  • Deleted {stats['deleted_processed_benches']} processed bench entries"
            )

        return stats

    except Exception as e:
        logger.exception("Error during cleanup")
        console.print(f"[bold red]💥 Error during cleanup: {e}[/bold red]")
        stats["errors"] += 1
        return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Cleanup deleted OSM bench candidates")
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually perform deletions (default is dry-run)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=700,
        help="Number of candidates to check per batch (default: 700, OSM API limit is ~725)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )

    args = parser.parse_args()

    # Setup logging
    from bench_finder.utils import setup_logging

    setup_logging(level=args.log_level)

    dry_run = not args.no_dry_run
    if dry_run:
        console.print("[yellow]🔍 DRY RUN MODE - No changes will be made[/yellow]\n")

    stats = cleanup_deleted_osm_benches(dry_run=dry_run, batch_size=args.batch_size)

    console.print("\n[bold]📊 Summary:[/bold]")
    console.print(f"  • Total OSM candidates: {stats['total_osm_candidates']}")
    console.print(f"  • Checked: {stats['checked']}")
    console.print(f"  • Deleted candidates: {stats['deleted_candidates']}")
    console.print(
        f"  • Deleted processed benches: {stats['deleted_processed_benches']}"
    )
    console.print(f"  • Errors: {stats['errors']}")
