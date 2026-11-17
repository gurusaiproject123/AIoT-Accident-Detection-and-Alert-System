from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services import accident_inference as inference


@pytest.mark.parametrize('score, expected', [(0.0199, 0), (0.02, 1), (0.0201, 1)])
def test_configured_cutoff(monkeypatch, score, expected):
    features = inference.extract_features(np.zeros((1600, 3)), np.zeros((1600, 3)))
    model = SimpleNamespace(classes_=np.array([0, 1]),
                            predict_proba=lambda frame: np.array([[1-score, score]]))
    monkeypatch.setattr(inference, 'load_model_bundle', lambda: {
        'settings': {'sampling_hz': 100, 'samples_per_event': 1600},
        'feature_names': list(features), 'model': model, 'threshold': 0.55,
        'model_labels': {'0': 'non_crash', '1': 'crash'},
    })
    monkeypatch.setattr(inference, 'get_settings', lambda: SimpleNamespace(detection_threshold=0.02))
    samples = [dict.fromkeys(['accel_x','accel_y','accel_z','gyro_x','gyro_y','gyro_z'], 0)] * 1600
    result = inference.predict_window(samples, sampling_hz=100)
    assert result['threshold'] == 0.02
    assert result['predicted_class'] == expected


@pytest.mark.parametrize('value', [-0.01, 1.01, float('nan'), float('inf')])
def test_invalid_threshold_rejected(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, detection_threshold=value)
