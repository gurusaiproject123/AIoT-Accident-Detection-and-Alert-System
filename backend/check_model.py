"""Inspect YOUR TRUSTED Colab model only. Never load untrusted pickle/joblib files."""
from pathlib import Path
from importlib.metadata import version
import joblib
path=Path(__file__).resolve().parent/'models'/'accident_model.joblib'
bundle=joblib.load(path)
if not isinstance(bundle,dict):raise SystemExit('Expected the saved model bundle dictionary.')
print('Training sklearn:',bundle.get('sklearn_version'))
print('Recorded versions:',bundle.get('versions'))
for name in ['scikit-learn','joblib','numpy','pandas']:print('Installed',name,version(name))
print('Threshold:',bundle.get('threshold'))
print('Feature count:',len(bundle.get('feature_names',[])))
print('Settings:',bundle.get('settings'))
if bundle.get('sklearn_version')!=version('scikit-learn'):raise SystemExit('Match the training scikit-learn version before inference.')
