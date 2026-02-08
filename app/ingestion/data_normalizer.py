import pandas as pd

def normalize_data(df):
    # Remove duplicates
    df = df.drop_duplicates()

    # Standardize phone numbers
    df['MSISDN'] = df['MSISDN'].astype(str).str.replace(r'\D', '', regex=True)

    # Convert timestamps
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

    return df
