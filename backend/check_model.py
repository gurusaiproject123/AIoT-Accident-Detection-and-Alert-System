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
from app.core.config import get_settings
print('Training threshold:',bundle.get('threshold'))
override = get_settings().detection_threshold
print('Effective threshold:',bundle.get('threshold') if override is None else override)
print('Feature count:',len(bundle.get('feature_names',[])))
print('Settings:',bundle.get('settings'))
if bundle.get('sklearn_version')!=version('scikit-learn'):raise SystemExit('Match the training scikit-learn version before inference.')
for package in ('numpy', 'pandas'):
    expected = (bundle.get('versions') or {}).get(package)
    if expected and expected != version(package):
        raise SystemExit(f'Match training {package} {expected} before inference.')
