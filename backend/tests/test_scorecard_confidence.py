from app.services.scorecard_confidence import confirm_field
def test_extracted_values_confirmed_in_jd_even_when_model_confidence_is_low():
    jd='Senior Java Developer, Noida, 5-8 years experience, notice period 60 days, budget up to 28 LPA.'
    assert confirm_field('location','Noida',jd,'low')==(True,'confirmed')
    assert confirm_field('experience','5-8',jd,'low')[0]
    assert confirm_field('notice',60,jd,'low')[0]
    assert confirm_field('ctc',28,jd,'low')[0]
def test_missing_and_unconfirmed_fields_are_distinct():
    jd='Senior Developer, Pune, 3 years experience.'
    assert confirm_field('location','Noida',jd,'low')[1]=='low_confidence'
    assert confirm_field('ctc',None,jd,'high')[1]=='empty'
