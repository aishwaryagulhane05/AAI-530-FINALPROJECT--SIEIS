#!/usr/bin/env python
"""Test data loader - simpler version."""
import pandas as pd

print("Loading CSV...")
df = pd.read_csv(
    'data/raw/data.txt',
    sep=r'\s+',
    header=None,
    names=['datetime', 'epoch', 'moteid', 'temperature', 'humidity', 'light', 'voltage'],
    na_values=['?'],
    dtype={
        'epoch': float,
        'moteid': float,
        'temperature': float,
        'humidity': float,
        'light': float,
        'voltage': float
    }
)

print(f"CSV loaded: {len(df)} rows")
print(f"Columns: {list(df.columns)}")
print(f"Sample row:\n{df.iloc[0]}")

# Try timestamp conversion
print("\nConverting timestamps...")
df['timestamp'] = pd.to_datetime(df['datetime'], format='%Y-%m-%d %H:%M:%S.%f', errors='coerce')
print(f"Timestamps converted")
print(f"Sample timestamp: {df.iloc[0]['timestamp']}")
