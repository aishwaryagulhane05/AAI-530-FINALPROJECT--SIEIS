"""Master test runner for all container tests and full pipeline."""

import sys
import subprocess
from pathlib import Path


def run_test(test_file):
    """Run a single test file and return result."""
    print(f"\n{'='*80}")
    print(f"Running: {test_file.name}")
    print('='*80)
    
    result = subprocess.run(
        [sys.executable, str(test_file)],
        capture_output=False
    )
    
    return result.returncode == 0


def main():
    """Run all container tests and full pipeline test."""
    tests_dir = Path(__file__).parent
    
    tests = [
        tests_dir / "test_container_redpanda.py",
        tests_dir / "test_container_influxdb.py",
        tests_dir / "test_container_minio.py",
        tests_dir / "test_full_pipeline.py"
    ]
    
    print("\n" + "🧪" * 40)
    print("MASTER TEST SUITE - ALL CONTAINERS + FULL PIPELINE")
    print("🧪" * 40)
    print("\nThis will test:")
    print("  1. Redpanda (Kafka) container")
    print("  2. InfluxDB 2.7 container")
    print("  3. MinIO container")
    print("  4. Full end-to-end data pipeline")
    
    results = []
    for test_file in tests:
        if test_file.exists():
            passed = run_test(test_file)
            results.append((test_file.name, passed))
        else:
            print(f"\n⚠️  Test file not found: {test_file}")
            results.append((test_file.name, False))
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY - ALL TESTS")
    print("="*80)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    print(f"\n📊 Overall: {passed_count}/{total_count} test suites passed")
    
    if passed_count == total_count:
        print("\n🎉 🎉 🎉 ALL TESTS PASSED! 🎉 🎉 🎉")
        print("\n✅ All containers are operational")
        print("✅ Full data pipeline is working")
        print("✅ Dual-write pattern (InfluxDB + MinIO) verified")
        print("\nSystem is fully operational and ready for production use!")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test suite(s) failed")
        print("\n📋 Next steps:")
        print("  1. Review failed test output above")
        print("  2. Check Docker containers: docker ps")
        print("  3. Check logs: docker-compose logs -f")
        print("  4. Restart services if needed: docker-compose restart")
        return 1


if __name__ == "__main__":
    sys.exit(main())
