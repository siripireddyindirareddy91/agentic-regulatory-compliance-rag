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
    assert client.get('/api/documents/'+doc['id']+'/original',headers=h).content==text
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
def test_policy_mapping_weights_and_evidence(client):
    h=auth(client)
    req=client.get('/api/requirements',headers=h).json()[0]
    policy=client.get('/api/policies',headers=h).json()[0]
    r=client.post('/api/policies/'+policy['id']+'/map',headers=h,json={'requirement_id':req['id'],'notes':'Human mapped control evidence'})
    assert r.status_code==200,r.text
    assert client.get('/api/policies/'+policy['id']+'/mappings',headers=h).json()
    invalid=client.patch('/api/settings/risk_weights',headers=h,json={'value':{'severity':1}})
    assert invalid.status_code==422
    weights={'severity':.4,'likelihood':.2,'regulatory_impact':.2,'operational_impact':.2}
    assert client.patch('/api/settings/risk_weights',headers=h,json={'value':weights}).status_code==200
    action=client.get('/api/actions',headers=h).json()[0]
    r=client.post('/api/actions/'+action['id']+'/evidence',headers=h,files={'file':('signed-evidence.txt',b'Signed review evidence for testing','text/plain')})
    assert r.status_code==200,r.text
    assert 'content' not in r.json()
    evidence=client.get('/api/evidence/'+r.json()['id']+'/download',headers=h)
    assert evidence.content==b'Signed review evidence for testing'
    assert client.get('/api/health/ready').json()['ready']

def test_durable_queue_and_reports(client):
    h=auth(client)
    queued=client.post('/api/jobs',headers=h,json={'kind':'report'})
    assert queued.status_code==200,queued.text
    id=queued.json()['id']
    result=client.post('/api/jobs/process',headers=h)
    assert result.status_code==200,result.text
    assert result.json()['result']['status']=='Completed',result.text
    job=next(j for j in client.get('/api/jobs',headers=h).json() if j['id']==id)
    assert job['attempts']==1
    report=client.get('/api/scheduled-reports/'+job['result']['report_id'],headers=h)
    assert report.status_code==200 and b'Finding' in report.content
    assert client.post('/api/jobs/process',headers=auth(client,'viewer')).status_code==403
    assert client.get('/api/cron').status_code==401

def test_trained_models(client):
    h=auth(client)
    status=client.get('/api/ml/status',headers=h)
    assert status.status_code==200,status.text
    assert status.json()['metrics']['test_rows']>0
    response=client.post('/api/ml/predict',headers=h,json={'text':'encryption access security cyber incident response'})
    assert response.status_code==200,response.text
    assert response.json()['category']=='Cybersecurity'
    assert 0<=response.json()['anomaly_score']<=1
def test_refresh_rotation_and_revocation(client):
    login=client.post('/api/auth/login',json={'email':'admin@complyintel.demo','password':'Demo-Compliance-2026!'}).json()
    first=login['refresh_token']
    rotated=client.post('/api/auth/refresh',json={'refresh_token':first})
    assert rotated.status_code==200
    assert client.post('/api/auth/refresh',json={'refresh_token':first}).status_code==401
    value=rotated.json()
    h={'Authorization':'Bearer '+value['access_token']}
    assert client.post('/api/auth/logout',headers=h,json={'refresh_token':value['refresh_token']}).status_code==200
    assert client.post('/api/auth/refresh',json={'refresh_token':value['refresh_token']}).status_code==401

def test_monitoring_boundaries_and_fetch(client,monkeypatch):
    import httpx
    from urllib.parse import urlparse
    from backend.app import monitoring
    from backend.app.models import Source,User
    with pytest.raises(ValueError):monitoring.validate_url('https://127.0.0.1/private')
    with pytest.raises(ValueError):monitoring.validate_url('http://www.rbi.org.in')
    real_client=httpx.Client
    def handler(request):
        if request.url.path=='/robots.txt':return httpx.Response(200,text='User-agent: *\nAllow: /')
        return httpx.Response(200,text='<html><script>untrusted()</script><h1>Official source snapshot</h1><p>Publication listing, not a verified mandate.</p></html>')
    monkeypatch.setattr(monitoring,'validate_url',lambda url:urlparse(url))
    monkeypatch.setattr(monitoring.httpx,'Client',lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs))
    with Session() as db:
        user=db.query(User).filter(User.email=='admin@complyintel.demo').first()
        source=Source(institution_id=user.institution_id,name='Test official source',url='https://www.bis.org/list',jurisdiction='International',enabled=True)
        db.add(source);db.commit()
        result=monitoring.monitor(db,user,source)
        assert result['document_id']
        from backend.app.models import Document
        doc=db.get(Document,result['document_id'])
        assert 'untrusted()' not in doc.text
        assert doc.verification!='Verified official'
        assert monitoring.monitor(db,user,source)['document_id']==doc.id

def test_native_checkpoint_resume(client):
    h=auth(client)
    doc=client.post('/api/regulations/upload',headers=h,data={'title':'Native checkpoint example'},files={'file':('checkpoint.txt',b'DEMO ONLY. The institution must review access controls and retain signed evidence.','text/plain')}).json()
    run=client.post('/api/regulations/'+doc['id']+'/analyze',headers=h).json()
    assert run['state']['native_checkpoint'] is True
    assert run['status']=='Awaiting human review'
    findings=[f for f in client.get('/api/compliance/findings',headers=h).json() if f['workflow_id']==run['id']]
    for f in findings:
        r=client.post('/api/reviews/'+f['id']+'/approve',headers=h,json={'confirmed':True,'comment':'Synthetic native checkpoint test review'})
        assert r.status_code==200,r.text
    assert client.get('/api/agents/executions/'+run['id'],headers=h).json()['status']=='Completed'

def test_identity_and_targeted_notifications(client):
    h=auth(client)
    invitation=client.post('/api/admin/invitations',headers=h,json={'email':'invited@example.com','role':'viewer'})
    assert invitation.status_code==200,invitation.text
    body={'token':invitation.json()['token'],'name':'Invited User','password':'Invited-password-2026!'}
    assert client.post('/api/auth/redeem',json=body).status_code==200
    assert client.post('/api/auth/redeem',json=body).status_code==401
    assert client.post('/api/admin/invitations',headers=auth(client,'viewer'),json={'email':'bad@example.com','role':'admin'}).status_code==403
    viewers=client.get('/api/notifications',headers=auth(client,'viewer')).json()
    reviewers=client.get('/api/notifications',headers=auth(client,'reviewer')).json()
    assert len(reviewers)>len(viewers)

def test_rbi_published_feed(client,monkeypatch):
    import httpx
    from urllib.parse import urlparse
    from backend.app import monitoring
    from backend.app.models import Source,User
    real=httpx.Client;requested=[]
    def handler(request):
        requested.append(str(request.url))
        return httpx.Response(200,headers={'content-type':'text/xml'},text='<rss><channel><item><title>Official notice metadata</title><link>https://www.rbi.org.in/notice</link><description>Test feed entry</description></item></channel></rss>')
    monkeypatch.setattr(monitoring,'validate_url',lambda url:urlparse(url))
    monkeypatch.setattr(monitoring.httpx,'Client',lambda **kwargs:real(transport=httpx.MockTransport(handler),**kwargs))
    with Session() as db:
        user=db.query(User).filter(User.email=='admin@complyintel.demo').first()
        source=Source(institution_id=user.institution_id,name='RBI feed test',url='https://www.rbi.org.in',jurisdiction='India',enabled=True)
        db.add(source);db.commit();result=monitoring.monitor(db,user,source)
        assert result['document_id']
        assert requested==['https://www.rbi.org.in/notifications_rss.xml']

def test_audit_tampering(client):
    h=auth(client)
    assert client.get('/api/audit/verify',headers=h).json()['valid']
    with Session() as db:
        row=db.query(Audit).filter(Audit.institution_id=='demo-bank').first(); row.event='tampered'; db.commit()
    assert not client.get('/api/audit/verify',headers=h).json()['valid']
