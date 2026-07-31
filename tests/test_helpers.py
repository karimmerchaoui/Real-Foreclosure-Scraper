import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helpers import build_url, get_base_url, is_us_ip


# --- Tests for build_url ---
def test_build_url():
    expected_url = "https://broward.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=DAYLIST&AUCTIONDATE=05/15/2026"
    assert build_url("broward", datetime(2026, 5, 15)) == expected_url


# --- Tests for get_base_url ---
def test_get_base_url():
    full_url = "https://broward.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=DAYLIST"
    assert get_base_url(full_url) == "https://broward.realforeclose.com"


# --- Tests for is_us_ip ---
@patch("requests.get")
def test_is_us_ip_true(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"country": "US"}
    mock_get.return_value = mock_response

    assert is_us_ip() is True


@patch("requests.get")
def test_is_us_ip_false(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"country": "CA"}
    mock_get.return_value = mock_response

    assert is_us_ip() is False


@patch("requests.get", side_effect=Exception("Network error"))
def test_is_us_ip_exception(mock_get):
    # Gracefully handles connection drops or errors
    assert is_us_ip() is False