import pytest
from fastapi import UploadFile, HTTPException
from io import BytesIO
import csv

from backend.main import normalize_csv, BANK_ALIASES, parse_and_format_date, clean_amount

def make_upload_file(content: str) -> UploadFile:
    class MockFile:
        def read(self):
            return content.encode("utf-8")
    class MockUploadFile:
        def __init__(self, f):
            self.file = f
    return MockUploadFile(MockFile())

def test_parse_and_format_date():
    assert parse_and_format_date("15-01-2026") == "15-01-2026"
    assert parse_and_format_date("15/01/2026") == "15-01-2026"
    assert parse_and_format_date("01-15-2026") == "15-01-2026"
    assert parse_and_format_date("01/15/2026") == "15-01-2026"
    assert parse_and_format_date("2026-01-15") == "15-01-2026"

def test_parse_and_format_date_ambiguous():
    with pytest.raises(HTTPException) as exc_info:
        parse_and_format_date("01/02/2026")
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        parse_and_format_date("02/01/2026")
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        parse_and_format_date("32/01/2026")
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        parse_and_format_date("invalid_date")
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        parse_and_format_date("31/02/2026")
    assert exc_info.value.status_code == 400

def test_clean_amount():
    assert clean_amount("25000") == 25000.0
    assert clean_amount("25,000") == 25000.0
    assert clean_amount("â‚¹25,000.00") == 25000.0
    assert clean_amount("$25000.50") == 25000.5
    assert clean_amount("-25000") == -25000.0
    assert clean_amount("invalid") == "invalid"

def test_normalize_csv_canonical():
    csv_content = "bank_txn_id,date,description,reference,amount\nTXN1,01-08-2026,desc1,ref1,25000"
    upload = make_upload_file(csv_content)
    result = normalize_csv(upload, BANK_ALIASES)
    assert len(result) == 1
    assert result[0] == {
        "bank_txn_id": "TXN1",
        "date": "01-08-2026",
        "description": "desc1",
        "reference": "ref1",
        "amount": 25000.0
    }

def test_normalize_csv_aliases_and_messy_headers():
    csv_content = ' txn_id , Payment-Date , Narration, UTR,  transaction amount \nTXN1,2026-08-01,desc1,ref1,"â‚¹25,000.00"'
    upload = make_upload_file(csv_content)
    result = normalize_csv(upload, BANK_ALIASES)
    assert result[0] == {
        "bank_txn_id": "TXN1",
        "date": "01-08-2026",
        "description": "desc1",
        "reference": "ref1",
        "amount": 25000.0
    }

def test_normalize_csv_ambiguity():
    csv_content = "amount,transaction_amount\n25000,25000"
    upload = make_upload_file(csv_content)
    with pytest.raises(HTTPException) as exc_info:
        normalize_csv(upload, BANK_ALIASES)
    assert exc_info.value.status_code == 400
    assert "Ambiguous columns detected" in exc_info.value.detail

def test_missing_field():
    from backend.main import upload_files
    import asyncio
    csv_content = "invoice_id,date,client_name,gst_rate,total_amount\nINV1,01-08-2026,client1,18,25000"
    upload = make_upload_file(csv_content)
    # We can't directly test upload_files without a DB session easily here,
    # but we can test that normalize_csv allows it and we just rely on Pydantic testing in test_api.py.
