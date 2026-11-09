from app.services.redaction import redact
def test_redacts_pii_and_personal_details():
    text='Ritika Bansal\nEmail: ritika.bansal@example.demo\nPhone: +91 9876543210\nLinkedIn: https://linkedin.com/in/ritika\nPersonal Details\nDOB: 12/01/1993\nGender: Female\nMarital Status: Single\nFather\'s Name: Rajesh Bansal\nExperience\nShe built Java and Spring Boot services.'
    result=redact(text,'Ritika Bansal')
    for value in ['ritika.bansal@example.demo','9876543210','linkedin.com','DOB','Gender','Marital Status','Father\'s Name','Ritika','Bansal']: assert value.lower() not in result.lower()
    assert 'Java' in result and 'Spring Boot' in result and 'they built' in result.lower()
def test_preserves_experience_and_removes_urls_and_address():
    result=redact('Mr Arjun Rawat\n12 MG Road, Noida 201301\nhttps://github.com/arjun\nHe has 3 years experience in KYC.', 'Arjun Rawat')
    assert 'KYC' in result and '3 years experience' in result and 'github' not in result.lower() and '201301' not in result and 'they has' in result.lower()

def test_removes_candidate_codes_and_normalizes_gendered_pronouns():
    result=redact('CND-91022\nShe gave him her notes and his report; hers was complete.')
    assert 'CND-91022' not in result
    assert 'they gave them their notes and their report; theirs was complete' in result.lower()
