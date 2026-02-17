import base64
import io
import pandas as pd

def parse_cdr(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    # ✅ Save file to disk
    file_path = f"cdr_files/{filename}"
    with open(file_path, "wb") as f:
        f.write(decoded)

    # ✅ Load into pandas for analytics
    data = io.BytesIO(decoded)

    if filename.endswith(".csv"):
        df = pd.read_csv(data)
    elif filename.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data)
    else:
        return pd.DataFrame()

    # ✅ Normalize columns for dashboard
    df = normalize_columns(df)

    return df
