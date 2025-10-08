#!/usr/bin/env python3
"""
CLI interface for the bench finder application.
"""
import argparse
import logging
import sys
from typing import Optional

from bench_finder.config import SEARCH_RADIUS_METERS
from bench_finder.utils import setup_logging
from bench_finder.main import BenchFinder


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Find benches using OSM data, Street View images, and AI detection (Roboflow or Ultralytics)"
    )
    parser.add_argument(
        'query',
        help='Search query (address, location name, etc.)'
    )
    parser.add_argument(
        '--radius',
        type=int,
        default=SEARCH_RADIUS_METERS,
        help=f'Search radius in meters (default: {SEARCH_RADIUS_METERS})'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    parser.add_argument(
        '--results',
        action='store_true',
        help='Show detailed results for the most recent search'
    )
    parser.add_argument(
        '--backend',
        choices=['roboflow', 'ultralytics', 'multi'],
        default=None,
        help=f'Detection backend to use: roboflow, ultralytics, or multi (default: multi with fallback)'
    )
    parser.add_argument(
        '--disable-fallback',
        action='store_true',
        help='Disable multi-model fallback detection (use single backend only)'
    )
    parser.add_argument(
        '--no-copy-bench-images',
        action='store_true',
        help='Disable copying images with detected benches to bench_images/{model_name}/ directory'
    )
    
    return parser


def main() -> int:
    """Main entry point for the bench finder CLI."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    try:
        # Setup logging
        setup_logging(level=args.log_level)
        logger = logging.getLogger(__name__)
        
        # Initialize bench finder with selected backend and fallback setting
        enable_fallback = not args.disable_fallback
        copy_bench_images = not args.no_copy_bench_images
        bench_finder = BenchFinder(
            detection_backend=args.backend, 
            enable_fallback=enable_fallback,
            copy_bench_images=copy_bench_images
        )
        
        if args.results:
            # Show results for the most recent search (simplified for now)
            logger.info("Results display not implemented yet - check database directly")
            return 0
        
        # Run the bench finding pipeline
        logger.info(f"BenchFinder starting with query: '{args.query}' using {bench_finder.detection_backend} backend")
        
        results = bench_finder.find_benches(args.query, args.radius)
        
        if results.success:
            logger.info(f"✅ {results.message}")
            
            if results.search_id:
                search_results = bench_finder.database.get_search_results(results.search_id)
                logger.info(f"📊 Summary:")
                logger.info(f"   • Search ID: {search_results.search.id}")
                logger.info(f"   • Query: {search_results.search.query}")
                logger.info(f"   • Location: ({search_results.search.start_lat}, {search_results.search.start_lng})")
                logger.info(f"   • Search radius: {search_results.search.search_radius}m")
                logger.info(f"   • Benches found: {search_results.bench_count}")
                logger.info(f"   • Images captured: {search_results.successful_images}/{search_results.total_images}")
                logger.info(f"   • Images with benches detected: {search_results.images_with_benches}")
                logger.info(f"   • Best confidence: {search_results.best_confidence:.2f}")

            if results.stats:
                stats = results.stats
                logger.info(f"   • Processing stats: {stats.benches_detected}/{stats.benches_processed} benches detected")
            
            # Show multi-model detection statistics if available
            if hasattr(bench_finder.detection_client, 'get_detection_stats'):
                detection_stats = bench_finder.detection_client.get_detection_stats()
                if not detection_stats.get('no_data', False):
                    logger.info(f"🔍 Detection Statistics:")
                    logger.info(f"   • Total model attempts: {detection_stats['total_attempts']}")
                    if detection_stats.get('ultralytics_attempts', 0) > 0:
                        success_rate = detection_stats.get('ultralytics_success_rate', 0) * 100
                        logger.info(f"   • Ultralytics: {detection_stats['ultralytics_successes']}/{detection_stats['ultralytics_attempts']} ({success_rate:.1f}%)")
                    if detection_stats.get('roboflow_attempts', 0) > 0:
                        success_rate = detection_stats.get('roboflow_success_rate', 0) * 100
                        logger.info(f"   • Roboflow: {detection_stats['roboflow_successes']}/{detection_stats['roboflow_attempts']} ({success_rate:.1f}%)")
        
        else:
            logger.error(f"❌ {results.error}")
            return 1
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("🛑 Operation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
