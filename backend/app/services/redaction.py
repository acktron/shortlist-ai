import re
EMAIL=r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}'; PHONE=r'(?:\+?91[\s-]?)?[6-9]\d{9}|(?:0\d{2,4}[\s-]?)?\d{6,8}'
URL=r'https?://[^\s]+|(?:www\.)?linkedin\.com/[^\s]+|(?:www\.)?github\.com/[^\s]+'; HONORIFICS=r'\b(?:mr|mrs|ms|miss|shri|smt)\.?\b'
PERSONAL_LINE=re.compile(r'^\s*(?:dob|date of birth|age|gender|sex|marital status|father.?s name|mother.?s name|spouse.?s name|husband.?s name|religion|caste|nationality|passport)\s*:',re.I)
def _remove_personal_sections(lines:list[str])->list[str]:
    out=[];inside=False
    for line in lines:
        if re.match(r'^\s*personal (?:details|information|profile)\s*$',line,re.I): inside=True;continue
        if inside and re.match(r'^\s*(?:experience|education|skills|projects|employment|work history)\b',line,re.I): inside=False
        if not inside and not PERSONAL_LINE.match(line): out.append(line)
    return out
def redact(text:str,full_name:str='')->str:
    lines=_remove_personal_sections(text.splitlines());value='\n'.join(lines)
    value=re.sub(r'(?im)^.*?\b\d{6}\b.*$', ' ', value)
    value=re.sub(URL,' ',value,flags=re.I);value=re.sub(EMAIL,' ',value,flags=re.I);value=re.sub(PHONE,' ',value)
    value=re.sub(r'\b\d{6}\b',' ',value);value=re.sub(r'\bCND-\d{5}\b',' ',value,flags=re.I);value=re.sub(HONORIFICS,' ',value,flags=re.I)
    if full_name:
        for token in sorted(set(full_name.split()),key=len,reverse=True): value=re.sub(rf'\b{re.escape(token)}\b',' ',value,flags=re.I)
    object_context={'to','for','with','about','from','by','at','saw','helped','met','called','told','asked','invited','followed','thanked','gave','sent','emailed'}
    pronouns={'he':'they','she':'they','him':'them','his':'their','hers':'theirs'}
    def neutralize(match:re.Match[str])->str:
        word=match.group(0).lower()
        if word=='her':
            before=value[:match.start()].rstrip().split()
            return 'them' if before and before[-1].lower().strip('.,;:') in object_context else 'their'
        return pronouns[word]
    value=re.sub(r'\b(?:he|she|him|her|his|hers)\b',neutralize,value,flags=re.I)
    return '\n'.join(re.sub(r'[ \t]+',' ',line).strip() for line in value.splitlines() if line.strip()).strip()
