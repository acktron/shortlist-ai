def test_requisitions_visible_and_scorecard_extract(client):
    token=client.post('/api/auth/login',json={'email':'recruiter@companya.demo','password':'Demo@1234'}).json()['access_token']; h={'Authorization':f'Bearer {token}'}
    rows=client.get('/api/requisitions',headers=h).json(); assert any(r['title']=='Senior Java Developer' for r in rows)
    rid=next(r['id'] for r in rows if r['title']=='Senior Java Developer'); draft=client.post(f'/api/requisitions/{rid}/scorecard/extract',headers=h).json()['draft']; assert draft['must_have_skills']
    previous=client.get(f'/api/requisitions/{rid}/scorecard',headers=h).json()
    criteria=[{'id':f'skill-{i}','kind':'must_skill','label':skill['name'],'weight':3,'params':{'aliases':skill.get('aliases',[])}} for i,skill in enumerate(draft['must_have_skills'])]
    saved=client.put(f'/api/requisitions/{rid}/scorecard',headers=h,json={'criteria':criteria}).json(); assert saved['version'] == previous['version'] + 1
