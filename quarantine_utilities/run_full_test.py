"""Quick test runner that orchestrates full pipeline test.

This script:
1. Checks configuration
2. Verifies Docker containers are running
3. Runs end-to-end test
4. Provides summary of results
"""

import sys
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


def print_header(text):
    """Print formatted section header."""
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80 + "\n")


def run_docker_check():
    """Check if Docker containers are running."""
    print_header("STEP 1: Checking Docker Containers")
    
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=sieis", "--format", "table {{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print(result.stdout)
            
            if "sieis-redpanda" in result.stdout and "sieis-influxdb" in result.stdout:
                print("✅ Docker containers are running\n")
                return True
            else:
                print("❌ SIEIS containers not found!")
                print("\n💡 Start them with: docker-compose up -d\n")
                return False
        else:
            print("❌ Docker command failed")
            print(result.stderr)
            return False
            
    except FileNotFoundError:
        print("❌ Docker not found! Make sure Docker is installed and in PATH")
        return False
    except Exception as e:
        print(f"❌ Error checking Docker: {e}")
        return False


def run_config_check():
    """Run configuration check script."""
    print_header("STEP 2: Configuration Check")
    
    try:
        result = subprocess.run(
            [sys.executable, "tests/test_config_check.py"],
            cwd=Path(__file__).parent,
            timeout=30
        )
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Configuration check timed out")
        return False
    except Exception as e:
        print(f"❌ Error running config check: {e}")
        return False


def run_end_to_end_test():
    """Run the full end-to-end test."""
    print_header("STEP 3: End-to-End Pipeline Test")
    
    try:
        result = subprocess.run(
            [sys.executable, "tests/test_end_to_end.py"],
            cwd=Path(__file__).parent,
            timeout=60
        )
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("\n❌ Test timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"\n❌ Error running test: {e}")
        return False


def main():
    """Run full test suite."""
    print("\n" + "🚀"*40)
    print("  SIEIS FULL PIPELINE TEST SUITE")
    print("🚀"*40)
    
    # Step 1: Docker check
    docker_ok = run_docker_check()
    if not docker_ok:
        print("\n❌ Docker containers not ready. Start them first:")
        print("   docker-compose up -d")
        return 1
    
    # Step 2: Config check
    config_ok = run_config_check()
    if not config_ok:
        print("\n❌ Configuration check failed. Fix issues above.")
        return 1
    
    # Step 3: End-to-end test
    test_ok = run_end_to_end_test()
    
    # Final summary
    print("\n" + "="*80)
    if test_ok:
        print("✅ ✅ ✅  ALL TESTS PASSED!  ✅ ✅ ✅")
        print("="*80)
        print("\n🎉 Your SIEIS pipeline is fully operational!")
        print("\n📊 View data:")
        print("   • InfluxDB UI: http://localhost:8086")
        print("   • Redpanda Console: http://localhost:8080")
        print()
        return 0
    else:
        print("❌ ❌ ❌  TEST FAILED  ❌ ❌ ❌")
        print("="*80)
        print("\n💡 Troubleshooting:")
        print("   1. Check Docker containers: docker ps")
        print("   2. Check logs: docker logs sieis-redpanda")
        print("   3. Check logs: docker logs sieis-influxdb")
        print("   4. Restart containers: docker-compose restart")
        print()
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
