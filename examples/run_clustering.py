#!/usr/bin/env python3
"""
Script to run bench clustering and test the implementation.

This script demonstrates how to use the clustering system and provides
utilities for testing and managing clustered data.
"""

import sys
import logging
from clustering import BenchClusterer
from clustered_bench_service import ClusteredBenchService

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_clustering():
    """Run the clustering process on all benches."""
    print("🚀 Starting bench clustering...")
    
    try:
        # Initialize clusterer with 5m distance (default)
        clusterer = BenchClusterer(cluster_distance_meters=5.0)
        
        # Run clustering with minimum confidence of 0.5
        cluster_count = clusterer.cluster_all_benches(min_confidence=0.0)
        
        print(f"✅ Clustering completed successfully!")
        print(f"   Created {cluster_count} clusters")
        
        # Display statistics
        stats = clusterer.get_clustering_stats()
        print("\n📊 Clustering Statistics:")
        print(f"   Total benches in database: {stats['total_benches']}")
        print(f"   Benches included in clustering: {stats['clustered_benches']}")
        print(f"   Benches excluded (low confidence): {stats['unclustered_benches']}")
        print(f"   Total clusters created: {stats['total_clusters']}")
        print(f"   Average benches per cluster: {stats['avg_benches_per_cluster']}")
        print(f"   Largest cluster size: {stats['max_benches_per_cluster']} benches")
        print(f"   Overall average confidence: {stats['overall_avg_confidence']}")
        print(f"   Average cluster radius: {stats['avg_cluster_radius_meters']:.1f} meters")
        print(f"   Clustering distance threshold: {stats['clustering_distance_meters']} meters")
        
        return True
        
    except Exception as e:
        print(f"❌ Clustering failed: {e}")
        return False


def test_clustered_service():
    """Test the clustered bench service."""
    print("\n🧪 Testing clustered bench service...")
    
    try:
        service = ClusteredBenchService()
        
        # Check if clustering is available
        if not service.is_clustering_available():
            print("❌ No clustering data available. Run clustering first.")
            return False
        
        print("✅ Clustering data is available")
        
        # Test getting clustered benches
        print("\n📍 Testing clustered bench retrieval:")
        
        # Get first page of clustered benches
        result = service.get_clustered_benches_filtered(
            page=0,
            page_size=5,  # Small page for testing
            min_confidence=0.7,
            start_lat=52.3613577,  # Amsterdam
            start_lng=4.8666322,
            sort_by='distance'
        )
        
        print(f"   Retrieved {len(result.clustered_benches)} clustered benches")
        print(f"   Total available: {result.pagination.total_count}")
        print(f"   Clustering enabled: {result.clustering_info.get('clustering_enabled', False)}")
        
        # Display some cluster details
        for i, cluster_data in enumerate(result.clustered_benches[:3], 1):
            cluster = cluster_data.cluster
            rep_bench = cluster_data.representative_bench
            
            print(f"\n   Cluster {i}:")
            print(f"      Center: ({cluster.center_lat:.6f}, {cluster.center_lng:.6f})")
            print(f"      Benches: {cluster.bench_count}")
            print(f"      Sources: {cluster.sources}")
            print(f"      Avg confidence: {cluster.avg_confidence:.3f}")
            print(f"      Representative bench: ID {rep_bench.id} (confidence: {rep_bench.best_confidence:.3f})")
            print(f"      Distance from Amsterdam: {cluster_data.distance_to_cluster_center:.0f}m")
        
        # Test bounding box query
        print(f"\n🗺️  Testing bounding box query:")
        bbox_result = service.get_clustered_benches_in_bbox(
            north=52.4,
            south=52.3,
            east=4.9,
            west=4.8,
            min_confidence=0.7,
            limit=10
        )
        
        print(f"   Found {len(bbox_result.clustered_benches)} clusters in bounding box")
        
        return True
        
    except Exception as e:
        print(f"❌ Testing failed: {e}")
        return False


def print_usage():
    """Print usage information."""
    print("Usage: python run_clustering.py [command]")
    print("")
    print("Commands:")
    print("  cluster    - Run clustering on all benches (default)")
    print("  test       - Test the clustered bench service")
    print("  stats      - Show clustering statistics only")
    print("  help       - Show this help message")


def main():
    """Main entry point."""
    command = sys.argv[1] if len(sys.argv) > 1 else "cluster"
    
    if command == "help":
        print_usage()
        return
    
    print("🔧 Bench Finder Clustering System")
    print("=" * 40)
    
    if command == "stats":
        # Just show statistics
        try:
            clusterer = BenchClusterer()
            stats = clusterer.get_clustering_stats()
            
            if stats['total_clusters'] == 0:
                print("❌ No clustering data available. Run clustering first.")
                return
            
            print("📊 Current Clustering Statistics:")
            for key, value in stats.items():
                print(f"   {key.replace('_', ' ').title()}: {value}")
                
        except Exception as e:
            print(f"❌ Failed to get statistics: {e}")
            
    elif command == "test":
        # Just run tests
        if not test_clustered_service():
            sys.exit(1)
            
    elif command == "cluster":
        # Run clustering and then test
        if not run_clustering():
            sys.exit(1)
        
        print("\n" + "=" * 40)
        if not test_clustered_service():
            sys.exit(1)
            
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()
        sys.exit(1)
    
    print("\n🎉 All operations completed successfully!")
    print("\nNext steps:")
    print("1. Start the FastAPI server: python -m uvicorn fastapi_server:app --reload")
    print("2. Test the API endpoints with clustering enabled")
    print("3. Check the new clustered responses in your frontend")


if __name__ == "__main__":
    main()
