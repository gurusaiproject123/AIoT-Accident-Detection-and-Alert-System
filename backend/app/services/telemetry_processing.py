"""Resume inference/incident processing on identical packet retries.
Database uniqueness on model_predictions.packet_id and incidents.prediction_id
is required. Existing saved predictions are authoritative on retry.
"""
from uuid import UUID
from app.schemas.telemetry import TelemetryPrediction


def process_packet(db, packet_id, device_id, payload):
    if payload['sample_count'] != 1600 or payload['sampling_hz'] != 100:
        return dict(detection_performed=False, prediction=None, prediction_saved=False, incident_id=None)
    performed = False
    saved = False
    def stored():
        return (db.table('model_predictions').select('id,score,threshold,is_suspected_accident')
                .eq('packet_id', str(packet_id)).eq('device_id', str(device_id)).limit(1).execute().data)
    rows = stored()
    if not rows:
        from app.services.accident_inference import predict_window
        candidate = TelemetryPrediction.model_validate(predict_window(payload['samples'], sampling_hz=payload['sampling_hz']))
        performed = True
        written = db.table('model_predictions').upsert({
            'packet_id': str(packet_id), 'device_id': str(device_id),
            'window_start': payload['recorded_start'], 'window_end': payload['recorded_end'],
            'model_name': 'random_forest', 'model_version': 'vzcrash-full-data-v1',
            'score': candidate.crash_score, 'threshold': candidate.threshold,
            'is_suspected_accident': candidate.predicted_class == 1,
        }, on_conflict='packet_id', ignore_duplicates=True).execute()
        saved = bool(written.data)
        rows = stored()
    if not rows:
        raise RuntimeError('Prediction storage could not be confirmed.')
    row = rows[0]
    crash = row['is_suspected_accident'] is True
    prediction = TelemetryPrediction(crash_score=row['score'], threshold=row['threshold'],
                                    predicted_class=1 if crash else 0, label='crash' if crash else 'non_crash')
    incident_id = None
    if crash:
        result = db.rpc('create_incident_from_prediction', {'p_packet_id': str(packet_id)}).execute()
        if result.data is None:
            raise RuntimeError('Incident creation could not be confirmed.')
        incident_id = UUID(str(result.data))
    return dict(detection_performed=performed, prediction=prediction,
                prediction_saved=saved, incident_id=incident_id)
