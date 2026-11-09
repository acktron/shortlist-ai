from app.services.scoring import compute_score,sort_scores
def test_weighted_score_partial_unknown_and_coverage():
    result=compute_score([{'criterion_id':'a','kind':'must_skill','weight':3,'verdict':'met'},{'criterion_id':'b','kind':'must_skill','weight':1,'verdict':'partial'},{'criterion_id':'c','kind':'notice','weight':2,'verdict':'unknown'}])
    assert result['total']==88 and result['coverage']==.6667 and result['band']=='strong' and result['needs_review']
def test_unverified_is_zero_and_low():
    result=compute_score([{'criterion_id':'a','kind':'must_skill','weight':3,'verdict':'unverified'},{'criterion_id':'b','kind':'must_skill','weight':1,'verdict':'met'}])
    assert result['total']==25 and result['needs_review']
def test_sort_order(): assert [x['id'] for x in sort_scores([{'id':'b','total':80,'coverage':.8},{'id':'a','total':80,'coverage':.9}])]==['a','b']
