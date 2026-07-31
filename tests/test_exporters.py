import os
import pytest
import pandas as pd
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.exporters import save_to_excel, save_final_dict_to_excel


@pytest.fixture
def sample_data_list():
    return [
        {"Case #:": "2026-001", "Date": "2026-05-15", "Amount": "$150,000"},
        {"Case #:": "2026-002", "Date": "2026-05-16", "Amount": "$200,000"}
    ]


@pytest.fixture
def sample_final_dict():
    return {
        "2026-001": {"Date": "2026-05-15", "County": "broward", "Amount": "$150,000"},
        "2026-002": {"Date": "2026-05-16", "County": "orange", "Amount": "$200,000"}
    }


# --- Tests for save_to_excel ---
def test_save_to_excel_creates_file(tmp_path, sample_data_list):
    save_to_excel(sample_data_list, path=str(tmp_path))
    
    # Verify file was generated in target folder
    generated_files = os.listdir(tmp_path)
    assert len(generated_files) == 1
    assert generated_files[0].endswith(".xlsx")

    # Verify structural integrity of content
    file_path = os.path.join(tmp_path, generated_files[0])
    df = pd.read_excel(file_path)
    assert len(df) == 2
    assert "Case #:" in df.columns


def test_save_to_excel_empty_list(tmp_path, capsys):
    # Tests behavior when scraping returns no results
    save_to_excel([], path=str(tmp_path))

    generated_files = os.listdir(tmp_path)
    assert len(generated_files) == 0  # No file should be generated


# --- Tests for save_final_dict_to_excel ---
def test_save_final_dict_to_excel(tmp_path, sample_final_dict):
    save_final_dict_to_excel(sample_final_dict, file_dir=str(tmp_path))

    generated_files = os.listdir(tmp_path)
    assert len(generated_files) == 1
    assert generated_files[0].startswith("realforeclose_report_")

    file_path = os.path.join(tmp_path, generated_files[0])
    df = pd.read_excel(file_path, index_col=0)
    
    # Verify records and index match dictionary keys
    assert len(df) == 2
    assert "2026-001" in df.index