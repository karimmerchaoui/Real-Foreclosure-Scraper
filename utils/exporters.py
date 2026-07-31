import os
import time
import pandas as pd
from openpyxl import Workbook

def save_to_excel(data, path):
    timestamp = time.strftime("%Y%m%d_%H_%M")
    filename = f"Foreclosures_Result_{timestamp}.xlsx"
    file_path = os.path.join(path, filename)
    df = pd.DataFrame(data)
    df.to_excel(file_path, index=False, engine='openpyxl')

def save_final_dict_to_excel(final_dict, file_dir):
    try:
        timestamp = time.strftime("%Y%m%d_%H_%M")
        filename = f"realforeclose_report_{timestamp}.xlsx"
        filepath = os.path.join(file_dir, filename)
        df = pd.DataFrame.from_dict(final_dict, orient='index')
        df.to_excel(filepath, engine='openpyxl')
        print(f"Saved {len(final_dict)} records to {filepath}")
    except Exception as e:
        print(e)