"""Explicit, idempotent synthetic scenario expansion; never imports official mandates."""
import hashlib
from sqlalchemy import select
from .models import Document,Finding,Review,User,Action,now
from .rag import index
from .workflow import execute
from .audit import log
SCENARIOS=[('DEMO-CYBER-002','Cyber Resilience · Synthetic scenario','Information Security',['The institution must encrypt sensitive information and conduct quarterly privileged access reviews.','The institution shall test incident response procedures every six months and preserve security exercise evidence.','The security team must report material cyber incidents to the internal risk committee within 24 hours.']),('DEMO-CUSTOMER-003','Customer Protection · Synthetic scenario','Customer Operations',['The institution must acknowledge customer complaints within two working days and track resolution evidence.','The institution shall verify customer consent before processing financial information.','The institution must provide accessible disclosures before account opening.']),('DEMO-RISK-004','Operational Resilience · Synthetic scenario','Risk Management',['The institution must test business continuity plans annually and document recovery results.','The risk committee shall review outsourcing risk controls every quarter.','The institution must maintain evidence of third party due diligence and control ownership.'])]
def expand(db,user):
    created=[]
    for identifier,title,department,obligations in SCENARIOS:
        if db.scalar(select(Document).where(Document.institution_id==user.institution_id,Document.identifier==identifier)):continue
        text='DEMONSTRATION ONLY. Synthetic scenario; not an official regulatory mandate.\n'+'\n'.join('Section '+str(i+1)+'. '+t for i,t in enumerate(obligations))
        doc=Document(institution_id=user.institution_id,title=title,authority='Synthetic authority',identifier=identifier,department=department,text=text,content_hash=hashlib.sha256(text.encode()).hexdigest(),verification='Demo / simulated',demo=True,publication_date='2026-11-01',effective_date='2027-01-31')
        policytext='SYNTHETIC INTERNAL POLICY. '+obligations[0].replace('must','intends to')+' Existing evidence is incomplete and requires human review.'
        policy=Document(institution_id=user.institution_id,title=department+' · Demo control standard',kind='policy',authority='Internal',department=department,text=policytext,content_hash=hashlib.sha256(policytext.encode()).hexdigest(),verification='Demo / simulated',demo=True,status='Under Review')
        db.add_all([doc,policy]);db.flush();index(db,doc);index(db,policy);log(db,user,'demo.scenario_added',doc.id,{'synthetic':True});db.commit();run=execute(db,user,doc);created.append(run.id)
    # Imported demo decisions are explicitly synthetic; agents never execute this seed operation.
    reviewer=db.scalar(select(User).where(User.institution_id==user.institution_id,User.role=='reviewer'))
    if reviewer:
        for identifier,title,department,_ in SCENARIOS[:2]:
            existing=db.scalar(select(Action).where(Action.institution_id==user.institution_id,Action.title=='DEMO remediation: '+department))
            if existing:continue
            finding=db.scalar(select(Finding).where(Finding.institution_id==user.institution_id,Finding.department==department,Finding.review_status=='Pending').order_by(Finding.risk_score))
            if not finding:continue
            reqdoc=next((e for e in finding.evidence if e.get('demo')),None)
            if not reqdoc:continue
            finding.review_status='Approved'
            db.add(Review(institution_id=user.institution_id,finding_id=finding.id,reviewer_id=reviewer.id,decision='Approved',previous_status='Pending',comment='SYNTHETIC DEMO RECORD: imported example reviewer decision, not a real human assessment.'))
            action=Action(institution_id=user.institution_id,finding_id=finding.id,title='DEMO remediation: '+department,description='Synthetic corrective action for demonstration only. Validate controls and attach evidence.',owner=department,priority=finding.risk_level,due_date='2027-01-15',status='In Progress',progress=35)
            db.add(action);log(db,user,'demo.review_and_action_imported',finding.id,{'synthetic':True});db.commit()
    return {'scenarios_added':len(created),'workflow_ids':created,'notice':'Synthetic demonstration records only'}
