"""Check Kafka message format."""
from kafka import KafkaConsumer
import json
import pprint

consumer = KafkaConsumer(
    'sensor_readings',
    bootstrap_servers='localhost:19092',
    auto_offset_reset='earliest',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    consumer_timeout_ms=2000
)

print("Reading first few messages from Kafka...")
msgs = []
for msg in consumer:
    msgs.append(msg.value)
    if len(msgs) >= 5:
        break

print(f"\nReceived {len(msgs)} messages in 5 seconds")

if msgs:
    print("\n" + "=" * 80)
    print("SAMPLE MESSAGE FROM KAFKA:")
    print("=" * 80)
    pprint.pprint(msgs[0])
    print("=" * 80)
else:
    print("No messages received")
