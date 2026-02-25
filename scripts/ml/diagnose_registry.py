import pickle, json, pandas as pd
from pathlib import Path
from datetime import datetime

reg = json.load(open('src/app/ml/models/model_registry.json'))
print('Full registry:')
print(json.dumps(reg, indent=2))
