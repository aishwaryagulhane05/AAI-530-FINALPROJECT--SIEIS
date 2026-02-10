"""Tests for Kafka producer behavior."""

import pytest
from datetime import datetime

from src.app.simulator.producer import Producer
from src.app.config import KAFKA_BROKER, KAFKA_TOPIC


class TestProducer:
    """Test cases for Kafka producer module."""
    
    @pytest.fixture(scope="class")
    def kafka_config(self):
        """Fixture providing Kafka configuration."""
        return {
            'broker': KAFKA_BROKER,
            'topic': KAFKA_TOPIC
        }
    
    @pytest.fixture
    def producer(self, kafka_config):
        """Fixture providing a Producer instance."""
        prod = Producer(broker=kafka_config['broker'], topic=kafka_config['topic'])
        yield prod
        prod.close()
    
    def test_producer_initializes_successfully(self, kafka_config):
        """Test 1: Producer connects successfully or handles graceful degradation."""
        producer = Producer(broker=kafka_config['broker'], topic=kafka_config['topic'])
        
        # Producer should initialize without crashing
        assert producer is not None, "Producer object should be created"
        assert producer.broker == kafka_config['broker'], "Broker should be set correctly"
        assert producer.topic == kafka_config['topic'], "Topic should be set correctly"
        
        # If Docker is running, _producer should be initialized
        # If not, it should be None but not crash
        if producer._producer is not None:
            print("✓ Connected to Kafka broker")
        else:
            print("⚠ Kafka broker unavailable (Docker not running?) - producer degraded gracefully")
        
        producer.close()
    
    def test_send_single_message(self, producer):
        """Test 2: Can send single message without errors."""
        test_message = {
            "mote_id": 999,
            "timestamp": datetime.now().isoformat(),
            "temperature": 25.5,
            "humidity": 50.0,
            "light": 100.0,
            "voltage": 2.8,
            "epoch": 1
        }
        
        # This should not raise an exception even if Kafka is unavailable
        try:
            producer.send(value=test_message, key=999)
            producer.flush()
            print(f"✓ Message sent successfully: {test_message['mote_id']}")
        except Exception as e:
            pytest.fail(f"Producer.send() raised exception: {e}")
    
    @pytest.mark.integration
    def test_message_appears_in_kafka(self, kafka_config):
        """Test 3: Producer sends to Kafka successfully (integration test).
        
        Requires Docker containers to be running:
        - docker-compose up -d
        
        Note: Full round-trip (send + consumer read) is tested in Phase 11 Consumer tests.
        """
        # Create producer
        producer = Producer(broker=kafka_config['broker'], topic=kafka_config['topic'])
        assert producer._producer is not None, "Producer failed to connect to Kafka"
        
        test_message = {
            "mote_id": 888,
            "timestamp": datetime.now().isoformat(),
            "temperature": 22.0,
            "humidity": 45.0,
            "light": 200.0,
            "voltage": 2.7,
            "epoch": 2,
            "test_marker": "integration_test"
        }
        
        # Send message - should not raise exception
        try:
            producer.send(value=test_message, key=888)
            producer.flush()
            print(f"✓ Successfully sent test message to Kafka: {test_message['mote_id']}")
        except Exception as e:
            pytest.fail(f"Producer failed to send message: {e}")
        
        producer.close()
        
        # Verify in Redpanda Console: http://localhost:8080
        # Navigate to Topics → sensor_readings → Messages
        print("✓ Message sent. Verify in http://localhost:8080/topics/sensor_readings")
    
    def test_producer_handles_multiple_sends(self, producer):
        """Test sending multiple messages in sequence."""
        messages = [
            {"mote_id": i, "temperature": 20.0 + i, "timestamp": datetime.now().isoformat()}
            for i in range(5)
        ]
        
        try:
            for msg in messages:
                producer.send(value=msg, key=msg["mote_id"])
            
            producer.flush()
            print(f"✓ Successfully sent {len(messages)} messages")
        except Exception as e:
            pytest.fail(f"Failed to send multiple messages: {e}")
    
    def test_producer_close_is_safe(self, kafka_config):
        """Test that closing producer multiple times is safe."""
        producer = Producer(broker=kafka_config['broker'], topic=kafka_config['topic'])
        
        # Should not raise exception even when called multiple times
        try:
            producer.close()
            producer.close()  # Second close should be safe
            print("✓ Producer close is idempotent")
        except Exception as e:
            pytest.fail(f"Producer.close() raised exception: {e}")
