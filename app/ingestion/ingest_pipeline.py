import pandas as pd
from ingestion.file_handler import identify_file_type, parse_csv, parse_excel, parse_pdf, parse_html, extract_zip
from ingestion.column_standardizer import standardize_columns
from ingestion.data_normalizer import normalize_data

def ingest_cdr_files(file_paths):
    combined_df = pd.DataFrame()
    for file in file_paths:
        file_type = identify_file_type(file)
        if file_type == 'csv':
            df = parse_csv(file)
        elif file_type == 'excel':
            df = parse_excel(file)
        elif file_type == 'pdf':
            df = parse_pdf(file)
        elif file_type == 'html':
            df = parse_html(file)
        elif file_type == 'zip':
            extracted_files = extract_zip(file)
            df_list = [ingest_cdr_files([f"temp_extracted/{f}"]) for f in extracted_files]
            df = pd.concat(df_list, ignore_index=True)
        else:
            continue
        
        df = standardize_columns(df)
        df = normalize_data(df)
        combined_df = pd.concat([combined_df, df], ignore_index=True)
    
    return combined_df
