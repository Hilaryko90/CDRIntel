
import pandas as pd

def temporal_alerts(df):
    alerts = {}
    alerts['night_calls'] = df[df['start_time'].dt.hour.between(0,5)].shape[0]
    alerts['burst_activity'] = df.groupby('caller').size().max()
    return alerts

def red_flag_scores(df):
    scores = {}
    for caller, g in df.groupby('caller'):
        score = 0
        score += g[g['duration'] > g['duration'].mean()*2].shape[0]
        score += g[g['start_time'].dt.hour.between(0,5)].shape[0]
        scores[caller] = score
    return scores
def compute_top_callers(case_id: str):
    """
    Wrapper for FastAPI compatibility.
    Replace internals later with real DB logic.
    """
    return {
        "case_id": case_id,
        "top_callers": [
            {"msisdn": "254700000001", "calls": 42},
            {"msisdn": "254700000002", "calls": 31},
            {"msisdn": "254700000003", "calls": 18}
        ]
    }

