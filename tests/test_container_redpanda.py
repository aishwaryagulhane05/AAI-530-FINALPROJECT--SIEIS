"""Test Redpanda (Kafka) container functionality."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import time
from kafka import KafkaProducer, KafkaConsumer
from kafka.admin import KafkaAdminClient, NewTopic
from tests.test_config import KAFKA_BROKER, KAFKA_TOPIC


def test_redpanda_container():
    """Test 1: Verify Redpanda container is running and accessible."""
    print("\n" + "="*80)
    print("TEST 1: Redpanda Container Health Check")
    print("="*80)
    
    try:
        admin = KafkaAdminClient(
            bootstrap_servers=[KAFKA_BROKER],
            client_id='test_admin',
            request_timeout_ms=5000
        )
        
        cluster_metadata = admin.list_topics()
        print(f"✅ Connected to Redpanda at {KAFKA_BROKER}")
        print(f"✅ Available topics: {list(cluster_metadata)}")
        
        admin.close()
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Redpanda: {e}")
        return False


def test_topic_creation():
    """Test 2: Verify topic creation and management."""
    print("\n" + "="*80)
    print("TEST 2: Topic Creation and Management")
    print("="*80)
    
    try:
        admin = KafkaAdminClient(
            bootstrap_servers=[KAFKA_BROKER],
            request_timeout_ms=5000
        )
        
        test_topic = "test_sensor_readings"
        existing_topics = admin.list_topics()
        
        if test_topic not in existing_topics:
            topic = NewTopic(
                name=test_topic,
                num_partitions=3,
                replication_factor=1
            )
            admin.create_topics([topic])
            print(f"✅ Created topic: {test_topic}")
        else:
            print(f"✅ Topic already exists: {test_topic}")
        
        if KAFKA_TOPIC in existing_topics:
            print(f"✅ Main topic exists: {KAFKA_TOPIC}")
        else:
            print(f"⚠️  Main topic not found: {KAFKA_TOPIC} (will be auto-created)")
        
        admin.close()
        return True
    except Exception as e:
        print(f"❌ Topic management failed: {e}")
        return False


def test_producer_consumer():
    """Test 3: Verify message production and consumption."""
    print("\n" + "="*80)
    print("TEST 3: Message Production and Consumption")
    print("="*80)
    
    test_topic = "test_sensor_readings"
    test_messages = [
        {"mote_id": 999, "temperature": 20.5, "timestamp": "2025-02-16T10:00:00"},
        {"mote_id": 999, "temperature": 21.0, "timestamp": "2025-02-16T10:01:00"},
    ]
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BROKER],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: str(k).encode('utf-8') if k is not None else None,
            request_timeout_ms=5000
        )
        
        print(f"📤 Sending {len(test_messages)} test messages...")
        for msg in test_messages:
            future = producer.send(test_topic, value=msg)
            future.get(timeout=5)
            print(f"  ✅ Sent: {msg}")
        
        producer.flush()
        producer.close()
        
        print(f"\n📥 Consuming messages from {test_topic}...")
        consumer = KafkaConsumer(
            test_topic,
            bootstrap_servers=[KAFKA_BROKER],
            auto_offset_reset='earliest',
            consumer_timeout_ms=5000,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        received_messages = []
        for message in consumer:
            received_messages.append(message.value)
            print(f"  ✅ Received: {message.value}")
            if len(received_messages) >= len(test_messages):
                break
        
        consumer.close()
        
        if len(received_messages) >= len(test_messages):
            print(f"\n✅ Successfully sent and received {len(test_messages)} messages")
            return True
        else:
            print(f"\n⚠️  Sent {len(test_messages)}, received {len(received_messages)}")
            return False
    except Exception as e:
        print(f"❌ Producer/Consumer test failed: {e}")
        return False


def main():
    """Run all Redpanda container tests."""
    print("\n" + "🔥" * 40)
    print("REDPANDA (KAFKA) CONTAINER TEST SUITE")
    print("🔥" * 40)
    print(f"\nTarget: {KAFKA_BROKER}")
    print(f"Topic: {KAFKA_TOPIC}")
    
    results = []
    
    results.append(("Container Health", test_redpanda_container()))
    results.append(("Topic Management", test_topic_creation()))
    results.append(("Producer/Consumer", test_producer_consumer()))
    
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
        print("\n🎉 All Redpanda tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
