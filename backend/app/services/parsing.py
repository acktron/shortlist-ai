from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import io
import re
import unicodedata
import pdfplumber
from docx import Document
from pypdf import PdfReader

MAX_FILE_BYTES=10*1024*1024
ALLOWED_EXTENSIONS={'.pdf','.docx'}
@dataclass
class ParsedDocument:
    text:str; parse_method:str; parse_confidence:str='high'; review_reasons:list[str]=None
    def __post_init__(self): self.review_reasons=self.review_reasons or []
class ParseError(ValueError):
    def __init__(self,code:str,message:str): self.code=code;super().__init__(message)
def _normalise(text:str)->str:
    text=unicodedata.normalize('NFKC',text).replace('\ufb00','ff').replace('\ufb01','fi').replace('\ufb02','fl').replace('\ufb03','ffi').replace('\ufb04','ffl')
    return '\n'.join(re.sub(r'[ \t]+',' ',line).strip() for line in text.splitlines() if line.strip()).strip()
def validate_file(path:Path|str,data:bytes|None=None)->bytes:
    path=Path(path); raw=path.read_bytes() if data is None else data
    if len(raw)>MAX_FILE_BYTES: raise ParseError('too_large','File exceeds the 10 MB limit.')
    if path.suffix.lower() not in ALLOWED_EXTENSIONS: raise ParseError('unsupported_type','Unsupported file type. Save legacy .doc files as DOCX or PDF.')
    if path.suffix.lower()=='.pdf' and not raw.startswith(b'%PDF'): raise ParseError('corrupt','Invalid PDF magic bytes.')
    if path.suffix.lower()=='.docx':
        try:
            with ZipFile(io.BytesIO(raw)) as archive:
                if 'word/document.xml' not in archive.namelist(): raise ParseError('corrupt','DOCX is missing word/document.xml.')
        except BadZipFile as exc: raise ParseError('corrupt','Invalid DOCX archive.') from exc
    return raw
def _parse_pdf(raw:bytes)->ParsedDocument:
    try: reader=PdfReader(io.BytesIO(raw))
    except Exception as exc: raise ParseError('corrupt','Unreadable PDF.') from exc
    if reader.is_encrypted:
        try:
            if not reader.decrypt(''): raise ParseError('password_protected','PDF is password protected.')
        except ParseError: raise
        except Exception as exc: raise ParseError('password_protected','PDF is password protected.') from exc
    pages=[]
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages:
                text=page.extract_text(layout=False) or ''
                if len(text.strip())<40:
                    words=page.extract_words(x_tolerance=2,y_tolerance=3,keep_blank_chars=False)
                    text=' '.join(w['text'] for w in sorted(words,key=lambda w:(round(w['top']/8),w['x0'])))
                pages.append(text)
    except ParseError: raise
    except Exception as exc: raise ParseError('corrupt','Could not extract PDF text.') from exc
    text=_normalise('\n'.join(pages)); avg=sum(len(p.strip()) for p in pages)/max(1,len(pages))
    if not text: return ParsedDocument('', 'ocr_ai', 'low', ['Scanned CV — check details'])
    if avg<200: return ParsedDocument(text,'ocr_ai','low',['Scanned CV — check details'])
    return ParsedDocument(text,'pdf_text','high',[])
def _parse_docx(raw:bytes)->ParsedDocument:
    try: document=Document(io.BytesIO(raw))
    except Exception as exc: raise ParseError('corrupt','Unreadable DOCX.') from exc
    chunks=[p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows: chunks.append(' | '.join(cell.text for cell in row.cells))
    for section in document.sections:
        chunks.extend(p.text for p in section.header.paragraphs);chunks.extend(p.text for p in section.footer.paragraphs)
    text=_normalise('\n'.join(chunks))
    if not text: raise ParseError('empty','The document contains no readable text.')
    return ParsedDocument(text,'docx','high',[])
def parse_file(path:Path|str,data:bytes|None=None)->ParsedDocument:
    path=Path(path);raw=validate_file(path,data)
    return _parse_pdf(raw) if path.suffix.lower()=='.pdf' else _parse_docx(raw)
