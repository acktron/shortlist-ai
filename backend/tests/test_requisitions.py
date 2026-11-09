def test_requisitions_visible_and_scorecard_extract(client):
    token=client.post('/api/auth/login',json={'email':'recruiter@companya.demo','password':'Demo@1234'}).json()['access_token']; h={'Authorization':f'Bearer {token}'}
    rows=client.get('/api/requisitions',headers=h).json(); assert any(r['title']=='Senior Java Developer' for r in rows)
    rid=next(r['id'] for r in rows if r['title']=='Senior Java Developer'); draft=client.post(f'/api/requisitions/{rid}/scorecard/extract',headers=h).json()['draft']; assert draft['must_have_skills']
    previous=client.get(f'/api/requisitions/{rid}/scorecard',headers=h).json()
    criteria=[{'id':f'skill-{i}','kind':'must_skill','label':skill['name'],'weight':3,'params':{'aliases':skill.get('aliases',[])}} for i,skill in enumerate(draft['must_have_skills'])]
    saved=client.put(f'/api/requisitions/{rid}/scorecard',headers=h,json={'criteria':criteria}).json(); assert saved['version'] == previous['version'] + 1
def test_recruiter_can_list_applications(client):
    token=client.post('/api/auth/login',json={'email':'recruiter@companya.demo','password':'Demo@1234'}).json()['access_token']
    headers={'Authorization':f'Bearer {token}'}
    requisition=client.get('/api/requisitions',headers=headers).json()[0]
    response=client.get(f"/api/requisitions/{requisition['id']}/applications",headers=headers)
    assert response.status_code == 200
    assert {'items','total','page'} <= response.json().keys()

def test_scorecard_validates_weights_and_unique_criteria(client):
    token=client.post('/api/auth/login',json={'email':'recruiter@companya.demo','password':'Demo@1234'}).json()['access_token']; headers={'Authorization':f'Bearer {token}'}
    requisition=client.get('/api/requisitions',headers=headers).json()[0]
    invalid_weight=client.put(f"/api/requisitions/{requisition['id']}/scorecard",headers=headers,json={'criteria':[{'id':'java','kind':'must_skill','label':'Java','weight':6,'params':{}}]})
    duplicate_ids=client.put(f"/api/requisitions/{requisition['id']}/scorecard",headers=headers,json={'criteria':[{'id':'same','kind':'must_skill','label':'Java','weight':3,'params':{}},{'id':'same','kind':'nice_skill','label':'Kafka','weight':1,'params':{}}]})
    assert invalid_weight.status_code==422
    assert duplicate_ids.status_code==422
