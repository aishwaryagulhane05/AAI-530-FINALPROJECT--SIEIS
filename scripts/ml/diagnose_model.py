import pickle, json, pandas as pd
from pathlib import Path
from datetime import datetime

reg = json.load(open('src/app/ml/models/model_registry.json'))
print('Full registry:')
print(json.dumps(reg, indent=2))

# Find the model path from whatever structure exists
model_path = None

# Structure 1: reg['models'][version]['path']
if 'models' in reg:
    models = reg['models']
    latest_key = reg.get('latest')
    print('Latest key:', latest_key)
    if latest_key and latest_key in models:
        model_path = models[latest_key]['path']
    else:
        # Get last model
        last = sorted(models.keys())[-1]
        model_path = models[last]['path']
        print('Using last model:', last)

# Structure 2: reg[version]['path']
elif any('path' in v for v in reg.values() if isinstance(v, dict)):
    for k, v in sorted(reg.items()):
        if isinstance(v, dict) and 'path' in v:
            model_path = v['path']
            print('Found model path:', model_path)

print('Model path:', model_path)

if not model_path:
    print('ERROR: Could not find model path in registry')
    exit(1)

# Try both relative and absolute
p = Path(model_path)
if not p.exists():
    p = Path('src/app/ml/models') / p.name
    print('Trying relative path:', p)

if not p.exists():
    print('ERROR: Model file not found at', p)
    # List all pkl files
    print('Available pkl files:')
    for f in Path('src/app/ml/models').glob('*.pkl'):
        print(' ', f)
    exit(1)

print('Loading model from:', p)
with open(p, 'rb') as f:
    artifact = pickle.load(f)

print('Artifact type:', type(artifact))
if isinstance(artifact, dict):
    print('Artifact keys:', list(artifact.keys()))
    pipeline = artifact['pipeline']
    print('Metrics:', json.dumps(artifact.get('metrics'), indent=2))
else:
    pipeline = artifact

now = datetime.utcnow()
test_data = pd.DataFrame([
    {'temperature': 22.5, 'humidity': 55.0, 'light': 300.0, 'voltage': 2.9,  'hour': now.hour, 'day_of_week': now.weekday()},
    {'temperature': 20.0, 'humidity': 60.0, 'light': 200.0, 'voltage': 3.0,  'hour': now.hour, 'day_of_week': now.weekday()},
    {'temperature': 25.0, 'humidity': 50.0, 'light': 400.0, 'voltage': 2.8,  'hour': now.hour, 'day_of_week': now.weekday()},
    {'temperature':  0.0, 'humidity':  0.0, 'light':   0.0, 'voltage': 0.0,  'hour': now.hour, 'day_of_week': now.weekday()},
    {'temperature': 95.0, 'humidity':  2.0, 'light':   0.0, 'voltage': 0.1,  'hour': now.hour, 'day_of_week': now.weekday()},
])

preds  = pipeline.predict(test_data)
scores = pipeline.decision_function(test_data)

print('\n--- Predictions ---')
labels = ['normal_22.5', 'normal_20.0', 'normal_25.0', 'ZEROS', 'EXTREME']
for label, pred, score in zip(labels, preds, scores):
    flag = 'ANOMALY ❌' if pred == -1 else 'normal  ✅'
    print(f'  {label:15s}  pred={pred:+d}  score={score:+.4f}  -> {flag}')