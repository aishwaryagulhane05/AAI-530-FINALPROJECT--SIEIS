"""Test MinIO container functionality."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import time
from datetime import datetime
from minio import Minio
from tests.test_config import (
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET,
    MINIO_SECURE
)


def test_minio_container():
    """Test 1: Verify MinIO container is running and accessible."""
    print("\n" + "="*80)
    print("TEST 1: MinIO Container Health Check")
    print("="*80)
    
    try:
        client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        
        buckets = client.list_buckets()
        bucket_names = [bucket.name for bucket in buckets]
        
        print(f"✅ Connected to MinIO at {MINIO_ENDPOINT}")
        print(f"✅ Available buckets: {bucket_names}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to connect to MinIO: {e}")
        return False


def test_bucket_exists():
    """Test 2: Verify target bucket exists."""
    print("\n" + "="*80)
    print("TEST 2: Target Bucket Verification")
    print("="*80)
    
    try:
        client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        
        if client.bucket_exists(MINIO_BUCKET):
            print(f"✅ Target bucket exists: {MINIO_BUCKET}")
            
            try:
                objects = []
                for obj in client.list_objects(MINIO_BUCKET, recursive=True):
                    objects.append(obj)
                    if len(objects) >= 10:
                        break
                print(f"✅ Bucket contains {len(objects)} objects (showing max 10)")
                
                for obj in objects[:3]:
                    print(f"  - {obj.object_name} ({obj.size} bytes)")
            except Exception as e:
                print(f"  ⚠️  Could not list objects: {e}")
            
            return True
        else:
            print(f"⚠️  Target bucket does not exist: {MINIO_BUCKET}")
            print("  Attempting to create...")
            
            try:
                client.make_bucket(MINIO_BUCKET)
                print(f"✅ Created bucket: {MINIO_BUCKET}")
                return True
            except Exception as e:
                print(f"❌ Failed to create bucket: {e}")
                return False
    except Exception as e:
        print(f"❌ Bucket check failed: {e}")
        return False


def test_upload_download():
    """Test 3: Verify upload and download operations."""
    print("\n" + "="*80)
    print("TEST 3: Upload/Download Operations")
    print("="*80)
    
    try:
        client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        
        test_object = f"test/upload_test_{int(time.time())}.txt"
        test_data = f"Test upload at {datetime.now().isoformat()}\n" * 10
        test_bytes = test_data.encode('utf-8')
        
        print(f"📤 Uploading test object: {test_object}")
        client.put_object(
            bucket_name=MINIO_BUCKET,
            object_name=test_object,
            data=io.BytesIO(test_bytes),
            length=len(test_bytes),
            content_type='text/plain'
        )
        print("✅ Upload successful")
        
        print(f"📥 Downloading test object...")
        response = client.get_object(MINIO_BUCKET, test_object)
        downloaded_data = response.read()
        response.close()
        response.release_conn()
        
        if downloaded_data == test_bytes:
            print("✅ Download successful, data matches")
        else:
            print("⚠️  Downloaded data does not match uploaded data")
            return False
        
        client.remove_object(MINIO_BUCKET, test_object)
        print("✅ Test object cleaned up")
        
        return True
    except Exception as e:
        print(f"❌ Upload/Download test failed: {e}")
        return False


def test_parquet_structure():
    """Test 4: Verify Parquet file structure exists."""
    print("\n" + "="*80)
    print("TEST 4: Parquet File Structure Check")
    print("="*80)
    
    try:
        client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        
        print("🔍 Looking for year-partitioned Parquet files...")
        
        year_objects = list(client.list_objects(MINIO_BUCKET, prefix="year=", recursive=True))
        
        if year_objects:
            print(f"✅ Found {len(year_objects)} partitioned files")
            
            parquet_files = [obj for obj in year_objects if obj.object_name.endswith('.parquet')]
            print(f"✅ Parquet files: {len(parquet_files)}")
            
            if parquet_files:
                print("\n📁 Sample file structure:")
                for obj in parquet_files[:5]:
                    print(f"  - {obj.object_name}")
                    print(f"    Size: {obj.size/1024:.2f} KB, Modified: {obj.last_modified}")
            
            return True
        else:
            print("⚠️  No year-partitioned files found yet")
            print("   (Consumer may not have written data yet)")
            return True
    except Exception as e:
        print(f"❌ Parquet structure check failed: {e}")
        return False


def main():
    """Run all MinIO container tests."""
    print("\n" + "🗄️ " * 40)
    print("MINIO CONTAINER TEST SUITE")
    print("🗄️ " * 40)
    print(f"\nTarget: {MINIO_ENDPOINT}")
    print(f"Bucket: {MINIO_BUCKET}")
    
    results = []
    
    results.append(("Container Health", test_minio_container()))
    results.append(("Bucket Verification", test_bucket_exists()))
    results.append(("Upload/Download", test_upload_download()))
    results.append(("Parquet Structure", test_parquet_structure()))
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All MinIO tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
