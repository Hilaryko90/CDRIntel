def standardize_columns(df):
    column_map = {
        "phone": "MSISDN",
        "msisdn": "MSISDN",
        "imei": "IMEI",
        "imsi": "IMSI",
        "call_time": "timestamp",
        "tower_id": "cell_tower"
    }
    df = df.rename(columns=lambda x: column_map.get(x.lower(), x))
    return df
