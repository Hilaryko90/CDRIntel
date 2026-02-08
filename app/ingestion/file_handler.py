import os

def identify_file_type(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.csv']:
        return 'csv'
    elif ext in ['.xls', '.xlsx']:
        return 'excel'
    elif ext == '.pdf':
        return 'pdf'
    elif ext == '.html':
        return 'html'
    elif ext == '.zip':
        return 'zip'
    else:
        return 'unsupported'

import pandas as pd
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup
import zipfile

def parse_csv(file_path):
    return pd.read_csv(file_path)

def parse_excel(file_path):
    return pd.read_excel(file_path)

def parse_pdf(file_path):
    reader = PdfReader(file_path)
    text_data = []
    for page in reader.pages:
        text_data.append(page.extract_text())
    # Convert to DataFrame as needed
    return pd.DataFrame(text_data, columns=["raw_text"])

def parse_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    tables = soup.find_all('table')
    df_list = [pd.read_html(str(table))[0] for table in tables]
    return pd.concat(df_list, ignore_index=True)

def extract_zip(file_path):
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall("temp_extracted")
    # Return list of extracted file paths
    return zip_ref.namelist()
