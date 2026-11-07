import os, hashlib
from sqlalchemy import select
from .models import User, Document, Source, Setting, Action
from .security import passwords
from .rag import index
from .workflow import execute
from .audit import log

REGULATION='''DEMONSTRATION ONLY — Synthetic Financial Controls Circular 2026. Not an RBI, SEBI, or other official mandate.
Section 1. Customer identity: The institution must verify customer identity before opening an account and retain documentary evidence of verification.
Section 2. Suspicious activity: The institution shall monitor suspicious transactions daily and escalate unresolved alerts to the compliance officer within 24 hours.
Section 3. Access security: The institution must encrypt sensitive customer information and review privileged access every quarter.
Section 4. Control assurance: The risk committee shall review operational controls every quarter and maintain signed evidence of remediation decisions.
Section 5. Training: The compliance department must provide annual regulatory training and maintain attendance records for all relevant employees.
Section 6. Incident response: The institution must ensure incident escalation procedures are documented and tested every six months.'''
POLICIES=[('Customer Due Diligence Policy','Customer Operations','We verify customer identity before opening accounts. Identity documents are stored in the customer file. Periodic verification is performed for high risk customers.'),('Information Access Standard','Information Security','Sensitive customer information is encrypted at rest. Privileged access is reviewed annually. Security incidents are sent to the helpdesk.'),('Operational Risk Framework','Risk Management','The risk committee reviews operational controls quarterly. Signed minutes document remediation decisions. Annual regulatory training is offered, but attendance tracking is not defined.')]
def seed(db):
    if os.getenv('DEMO_MODE','true').lower()!='true' or db.scalar(select(User).where(User.email=='admin@complyintel.demo')): return
    pw=os.getenv('DEMO_PASSWORD','Demo-Compliance-2026!')
    users=[]
    for email,name,role in [('admin','Aanya Sharma','admin'),('reviewer','Arjun Mehta','reviewer'),('analyst','Priya Rao','analyst'),('viewer','Demo Viewer','viewer')]:
        u=User(email=email+'@complyintel.demo',name=name,role=role,password_hash=passwords.hash(pw)); db.add(u); users.append(u)
    db.flush(); user=users[0]
    for title,department,text in POLICIES:
        d=Document(title=title,kind='policy',authority='Internal',department=department,text=text,content_hash=hashlib.sha256(text.encode()).hexdigest(),verification='Demo / simulated',demo=True,status='Under Review'); db.add(d); db.flush(); index(db,d)
    d=Document(title='Financial Controls & Customer Protection · 2026',authority='Synthetic authority',category='AML & Operational Resilience',text=REGULATION,content_hash=hashlib.sha256(REGULATION.encode()).hexdigest(),identifier='DEMO-FC-2026-001',publication_date='2026-10-01',effective_date='2026-12-31',verification='Demo / simulated',demo=True)
    db.add(d); db.flush(); index(db,d)
    for name,url in [('RBI','https://www.rbi.org.in'),('SEBI','https://www.sebi.gov.in'),('IRDAI','https://irdai.gov.in'),('FIU-IND','https://fiuindia.gov.in'),('FATF','https://www.fatf-gafi.org'),('Basel Committee','https://www.bis.org/bcbs/')]: db.add(Source(name=name,url=url,jurisdiction='India' if name not in ('FATF','Basel Committee') else 'International',enabled=False))
    db.add(Setting(key='institution',value={'name':'Meridian Financial Group','jurisdiction':'India','departments':['Banking Operations','Risk Management','Finance','Information Security','Customer Operations','Legal and Compliance'],'applicable_authorities':['RBI'],'monitoring':'Manual uploads only; live monitoring disabled'}))
    log(db,user,'demo.seeded',d.id,{'notice':'All documents and results are synthetic demonstration data'})
    db.commit(); execute(db,user,d)
