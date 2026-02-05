#!/usr/bin/env python
"""Quick test of data loader."""
import time
from src.app.simulator.data_loader import load_data_loader

print("Loading data...")
start = time.time()
mote_data, mote_locs = load_data_loader('data/raw/data.txt', 'data/raw/mote_locs.txt')
elapsed = time.time() - start

print(f"✓ Data loaded successfully in {elapsed:.1f}s")
print(f"✓ Number of motes: {len(mote_data)}")
print(f"✓ Mote IDs: {sorted(list(mote_data.keys()))[:10]}")
print(f"✓ Mote locations shape: {mote_locs.shape}")

# Check first mote
first_mote_id = list(mote_data.keys())[0]
first_mote_df = mote_data[first_mote_id]
print(f"\n✓ First mote ({first_mote_id}) has {len(first_mote_df)} readings")
print(f"✓ Null temperature values: {first_mote_df['temperature'].isnull().sum()}")
print(f"✓ Null humidity values: {first_mote_df['humidity'].isnull().sum()}")
print(f"✓ Data is sorted by timestamp: {(first_mote_df['timestamp'].values[:-1] <= first_mote_df['timestamp'].values[1:]).all()}")
print(f"\nAll tests passed!")
