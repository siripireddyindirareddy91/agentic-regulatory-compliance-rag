import os, tempfile, uuid
os.environ['DATABASE_URL']='sqlite:///'+os.path.join(tempfile.gettempdir(),'complyintel-test-'+uuid.uuid4().hex+'.db').replace('\\','/')
os.environ['JWT_SECRET_KEY']='test-only-secret-key-minimum-32-characters'
os.environ['DEMO_MODE']='true'
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models import Session, Audit
from backend.app.risk import assess
from backend.app.rag import embed

@pytest.fixture(scope='module')
def client():
    with TestClient(app) as c: yield c
def auth(client,role='admin'):
    r=client.post('/api/auth/login',json={'email':role+'@complyintel.demo','password':'Demo-Compliance-2026!'})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['access_token']}
def test_authentication(client):
    assert client.get('/api/documents').status_code==401
    assert client.post('/api/auth/login',json={'email':'admin@complyintel.demo','password':'bad'}).status_code==401
def test_roles(client):
    h=auth(client,'viewer')
    assert client.post('/api/agents/run',headers=h,json={'document_id':'missing'}).status_code==403
    assert client.patch('/api/settings/institution',headers=h,json={'value':{}}).status_code==403
def test_tenant_isolation(client):
    r=client.post('/api/auth/register',json={'email':'isolated@example.com','password':'A-long-secure-password!','name':'Isolated Viewer'})
    h={'Authorization':'Bearer '+r.json()['access_token']}
    assert client.get('/api/documents',headers=h).json()==[]
    docs=client.get('/api/documents',headers=auth(client)).json()
    assert client.get('/api/regulations/'+docs[0]['id'],headers=h).status_code==404
def test_risk_model():
    assert assess({'severity':5,'likelihood':5,'regulatory_impact':5,'operational_impact':5})==(5.0,'Critical')
    assert assess({'severity':1,'likelihood':1,'regulatory_impact':1,'operational_impact':1})==(1.0,'Low')
    with pytest.raises(ValueError): assess({'severity':6})
def test_rag_grounding(client):
    h=auth(client)
    result=client.post('/api/rag/query',headers=h,json={'query':'customer identity verification'}).json()
    assert result['citations']
    assert result['answer'].startswith('Insufficient verified regulatory evidence.')
    assert result['citations'][0]['chunk_id']
    assert embed('customer identity')==embed('customer identity')
def test_upload_workflow_review_action_report(client):
    h=auth(client)
    policy=client.post('/api/policies/upload',headers=h,data={'title':'Test access policy','kind':'policy','authority':'Internal'},files={'file':('policy.txt',b'Access reviews are performed annually and sensitive customer data is encrypted.','text/plain')})
    assert policy.status_code==200,policy.text
    text=b'TEST ONLY synthetic circular.\nSection 1. The institution must encrypt customer data and review privileged access quarterly.\nSection 2. The institution shall monitor suspicious activity every day and preserve alert evidence.'
    r=client.post('/api/regulations/upload',headers=h,data={'title':'Synthetic test circular','authority':'Demo'},files={'file':('test.txt',text,'text/plain')})
    assert r.status_code==200,r.text
    doc=r.json()
    duplicate=client.post('/api/regulations/upload',headers=h,data={'title':'Duplicate'},files={'file':('test.txt',text,'text/plain')})
    assert duplicate.status_code==409
    workflow=client.post('/api/regulations/'+doc['id']+'/analyze',headers=h)
    assert workflow.status_code==200,workflow.text
    w=workflow.json(); assert w['status']=='Awaiting human review',w
    assert len(w['steps'])>=10
    findings=client.get('/api/compliance/findings',headers=h).json(); f=next(f for f in findings if f['workflow_id']==w['id'])
    assert f['review_status']=='Pending'; assert f['evidence'][0]['excerpt'] in text.decode()
    body={'finding_id':f['id'],'title':'Implement quarterly access review','owner':'Security','priority':'High','due_date':'2026-12-31'}
    assert client.post('/api/actions',headers=h,json=body).status_code==409
    assert client.post('/api/reviews/'+f['id']+'/approve',headers=h,json={'comment':'Reviewed exact source evidence','confirmed':False}).status_code==422
    assert client.post('/api/reviews/'+f['id']+'/approve',headers=auth(client,'analyst'),json={'comment':'Reviewed exact source evidence','confirmed':True}).status_code==403
    r=client.post('/api/reviews/'+f['id']+'/approve',headers=h,json={'comment':'Reviewed synthetic source and policy evidence','confirmed':True}); assert r.status_code==200,r.text
    a=client.post('/api/actions',headers=h,json=body); assert a.status_code==200,a.text
    a=client.patch('/api/actions/'+a.json()['id'],headers=h,json={'status':'Completed','progress':100,'evidence':'Quarterly review signed by security lead'}); assert a.status_code==200
    for format,magic in [('csv',b'\xef\xbb\xbf'),('pdf',b'%PDF'),('xlsx',b'PK')]:
        report=client.get('/api/reports/gaps?format='+format,headers=h); assert report.status_code==200; assert report.content.startswith(magic)
    assert client.get('/api/audit/verify',headers=h).json()['valid']
def test_file_validation(client):
    h=auth(client)
    assert client.post('/api/regulations/upload',headers=h,data={'title':'Bad file'},files={'file':('bad.exe',b'not executable actually','application/octet-stream')}).status_code==415
def test_audit_tampering(client):
    h=auth(client)
    assert client.get('/api/audit/verify',headers=h).json()['valid']
    with Session() as db:
        row=db.query(Audit).filter(Audit.institution_id=='demo-bank').first(); row.event='tampered'; db.commit()
    assert not client.get('/api/audit/verify',headers=h).json()['valid']
