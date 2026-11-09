import re
def confirm_field(field:str,value:object,jd:str,model_confidence:str|None=None)->tuple[bool,str]:
    text=jd.lower(); raw=str(value or '').strip().lower()
    if not raw:return False,'empty'
    if field=='location': found=raw in text
    elif field=='experience': found=bool(re.search(rf'{re.escape(str(value))}[^\n]{{0,30}}(?:yr|year)',text)) or bool(re.search(r'\d+\s*[-–]\s*\d+\s*(?:yr|year)',text))
    elif field=='notice': found=bool(re.search(r'notice[^\d]{0,30}'+re.escape(str(value)),text))
    elif field=='ctc': found=bool(re.search(r'(?:budget|up to)[^\d]{0,30}'+re.escape(str(value))+r'\s*lpa',text))
    else: found=raw in text
    return found, 'confirmed' if found else ('low_confidence' if model_confidence=='low' else 'missing')
