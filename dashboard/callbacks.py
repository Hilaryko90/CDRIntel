import pandas as pd
import base64
import io

def parse_cdr(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    # Save file
    file_path = f"cdr_files/{filename}"
    with open(file_path, "wb") as f:
        f.write(decoded)

    # Load into pandas
    data = io.BytesIO(decoded)

    if filename.endswith(".csv"):
        df = pd.read_csv(data)
    elif filename.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data)
    else:
        return pd.DataFrame()

    df = normalize_columns(df)
    return df


def normalize_columns(df):
    mapping = {
        "calling_number": "caller",
        "caller_id": "caller",
        "source": "caller",
        "from": "caller",

        "called_number": "receiver",
        "receiver_id": "receiver",
        "destination": "receiver",
        "to": "receiver",

        "call_duration": "duration",
        "duration_sec": "duration",
        "duration_seconds": "duration",

        "call_time": "timestamp",
        "time": "timestamp",
        "date": "timestamp",

        "latitude": "lat",
        "longitude": "lon"
    }

    # normalize column names
    df.columns = [c.lower().strip() for c in df.columns]
    df = df.rename(columns={c: mapping[c] for c in df.columns if c in mapping})

    # ensure required fields exist
    if "duration" not in df.columns:
        df["duration"] = 0

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    else:
        df["timestamp"] = pd.Timestamp.now()

    return df

from dash import callback, Output, Input, State

@callback(
    Output("upload-status", "children"),
    Input("upload-cdr", "contents"),
    State("upload-cdr", "filename")
)
def handle_upload(contents, filename):
    if contents is None:
        return "No file uploaded"

    return f"Uploaded: {filename}"
