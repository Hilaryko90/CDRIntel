from sqlalchemy.orm import Session
from app.models import CDR, AnalysisLog
from datetime import datetime
import pandas as pd

LONG_CALL_THRESHOLD = 3600  # 1 hour
BURST_CALL_THRESHOLD = 20    # 20 calls/hour

def analyze_cdr(db: Session):
    # Load all CDRs
    cdrs = db.query(CDR).all()
    df = pd.DataFrame([{
        "caller": c.caller,
        "callee": c.callee,
        "duration": c.duration,
        "timestamp": c.timestamp,
        "imei": c.imei,
        "imsi": c.imsi,
        "subscriber_id": c.subscriber_id
    } for c in cdrs])

    intelligence = {}

    # Top communicators
    top_callers = df['caller'].value_counts().head(10).to_dict()
    intelligence['top_callers'] = top_callers

    # Long calls
    long_calls = df[df['duration'] >= LONG_CALL_THRESHOLD]
    intelligence['long_calls'] = long_calls.to_dict(orient='records')

    # Burst calls
    df['hour'] = df['timestamp'].apply(lambda x: x.replace(minute=0, second=0, microsecond=0))
    bursts = df.groupby(['caller','hour']).size().reset_index(name='call_count')
    burst_calls = bursts[bursts['call_count'] >= BURST_CALL_THRESHOLD]
    intelligence['burst_calls'] = burst_calls.to_dict(orient='records')

    # SIM swaps
    sim_swaps = df.groupby('imsi')['imei'].nunique().reset_index()
    sim_swaps = sim_swaps[sim_swaps['imei'] > 1]
    intelligence['sim_swaps'] = sim_swaps.to_dict(orient='records')

    # Burner phones
    imei_usage = df.groupby('imei')['subscriber_id'].nunique().reset_index()
    burner_phones = imei_usage[imei_usage['subscriber_id'] > 1]
    intelligence['burner_phones'] = burner_phones.to_dict(orient='records')

    # Save anomalies to AnalysisLog
    for anomaly_type, records in intelligence.items():
        if isinstance(records, list):
            for record in records:
                log = AnalysisLog(subscriber_id=record.get('caller', 'N/A'),
                                  anomaly_type=anomaly_type,
                                  details=record)
                db.add(log)
        else:  # dictionary
            log = AnalysisLog(subscriber_id="N/A", anomaly_type=anomaly_type, details=records)
            db.add(log)
    db.commit()

    return intelligence
