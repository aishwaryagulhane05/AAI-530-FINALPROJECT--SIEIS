"""Check the latest updated_timestamp values in realtime_data.txt"""

import pandas as pd
from pathlib import Path

# Read data file
data_file = Path(__file__).parent.parent / "data" / "processed" / "realtime_data.txt"

print(f"\n📁 Reading: {data_file.name}\n")

df = pd.read_csv(
    data_file,
    sep=r'\s+',
    header=None,
    names=['date', 'time', 'epoch', 'moteid', 'temperature', 
           'humidity', 'light', 'voltage', 'updated_timestamp']
)

# Parse timestamps
df['updated_timestamp'] = pd.to_datetime(df['updated_timestamp'], format='ISO8601')

# Sort by timestamp descending
df_sorted = df.sort_values('updated_timestamp', ascending=False)

print("="*80)
print("LATEST UPDATED_TIMESTAMP VALUES")
print("="*80)

print("\n🔝 Last 20 timestamps (most recent first):\n")
print(df_sorted[['moteid', 'updated_timestamp']].head(20).to_string(index=False))

latest = df_sorted['updated_timestamp'].iloc[0]
oldest = df_sorted['updated_timestamp'].iloc[-1]

print(f"\n{'='*80}")
print(f"📊 TIMESTAMP SUMMARY")
print(f"{'='*80}")
print(f"   Latest timestamp:  {latest}")
print(f"   Oldest timestamp:  {oldest}")
print(f"   Date range:        {oldest.date()} to {latest.date()}")
print(f"   Total records:     {len(df):,}")
print()
