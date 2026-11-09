from pathlib import Path
import pytest
from app.services.parsing import ParseError,parse_file
ROOT=Path(__file__).parents[1]/'seed'/'cvs'
def test_pdf_docx_and_table_parsing():
    assert 'Java' in parse_file(ROOT/'ritika_bansal.pdf').text
    assert 'KYC' in parse_file(ROOT/'arjun_rawat.docx').text
    assert 'neha.kapoor@example.demo' in parse_file(ROOT/'tables.docx').text
def test_scan_detection_and_fixtures():
    result=parse_file(ROOT/'scanned.pdf');assert result.parse_method=='ocr_ai';assert result.parse_confidence=='low'
    with pytest.raises(ParseError) as locked: parse_file(ROOT/'locked.pdf')
    assert locked.value.code=='password_protected'
def test_validation_errors():
    with pytest.raises(ParseError) as legacy: parse_file(ROOT/'old_format.doc')
    assert legacy.value.code=='unsupported_type'
    invoice=parse_file(ROOT/'invoice.pdf')
    assert 'INVOICE' in invoice.text
