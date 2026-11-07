"""Ten-stage LangGraph workflow with bounded retrieval and persisted human gate."""
import re
from typing import TypedDict
from sqlalchemy import select
from langgraph.graph import StateGraph, START, END
from .models import Document, Chunk, Requirement, Finding, Workflow, Notification, now
from .rag import search, citation, words
from .risk import assess, configured_weights
from .audit import log

AGENTS=[('ingestion','Regulatory Ingestion','Validate document identity and indexed content'),('changes','Change Detection','Compare previous document versions'),('requirements','Requirement Extraction','Extract obligations with exact evidence'),('retrieval','Evidence Retrieval','Hybrid search across internal policies'),('gaps','Compliance Gap Analysis','Compare obligations with policy evidence'),('risk','Risk Assessment','Explainable weighted risk factors'),('recommendations','Recommendation','Draft evidence-linked corrective actions'),('validation','Validation & Reflection','Check citations and retry weak retrieval once'),('escalation','Human Escalation','Pause findings for authorized human decisions'),('audit','Audit & Reporting','Record an integrity-linked investigation trail')]
class State(TypedDict, total=False):
    workflow_id:str
    document_id:str
    tenant:str
    requirements:list
    findings:list
    evidence:dict
    changes:dict
    attempts:int
    insufficient:bool
    paused:bool
    errors:list

def build_graph(db, user, run, checkpointer=None):
    def step(name, fn):
        def execute(state):
            result=fn(state)
            run.stage=name
            run.steps=[*run.steps,{'agent':name,'at':now(),'status':'Completed'}]
            log(db,user,'agent.'+name,run.id,{'document_id':run.document_id})
            db.flush(); return result
        return execute
    def ingestion(s):
        d=db.get(Document,s['document_id'])
        if not d or not d.text.strip(): raise ValueError('Document contains no extractable text')
        return {'attempts':0,'errors':[]}
    def changes(s):
        import difflib
        doc=db.get(Document,s['document_id']); previous=db.get(Document,doc.previous_id) if doc.previous_id else None
        diff=list(difflib.unified_diff(previous.text.splitlines() if previous else [],doc.text.splitlines(),lineterm=''))
        return {'changes':{'previous_id':doc.previous_id,'added':[x[1:] for x in diff if x.startswith('+') and not x.startswith('+++')],'removed':[x[1:] for x in diff if x.startswith('-') and not x.startswith('---')]}}
    def requirements(s):
        doc=db.get(Document,s['document_id']); chunks=db.scalars(select(Chunk).where(Chunk.document_id==doc.id)).all(); ids=[]; seen=set()
        for c in chunks:
            for sentence in re.split(r'(?<=[.!?])\s+|\n',c.text):
                sentence=sentence.strip()
                if len(sentence)<30 or not re.search(r'\b(shall|must|required|ensure|prohibit)\b',sentence,re.I) or sentence in seen: continue
                seen.add(sentence)
                department='Information Security' if re.search(r'cyber|security|access|encrypt',sentence,re.I) else 'Customer Operations' if re.search(r'customer|kyc|identity',sentence,re.I) else 'Risk Management' if re.search(r'risk|monitor|suspicious',sentence,re.I) else 'Legal and Compliance'
                req=Requirement(institution_id=user.institution_id,document_id=doc.id,chunk_id=c.id,title=sentence[:150],description=sentence,department=department,confidence=.65,effective_date=doc.effective_date)
                db.add(req); db.flush(); ids.append(req.id)
        return {'requirements':ids}
    def retrieval(s):
        evidence={}
        for rid in s['requirements']:
            req=db.get(Requirement,rid); evidence[rid]=search(db,user.institution_id,req.description,kind='policy',limit=5 if s['attempts'] else 3)
        return {'evidence':evidence,'attempts':s['attempts']+1}
    def gaps(s):
        results=[]
        for rid in s['requirements']:
            req=db.get(Requirement,rid); ev=s['evidence'].get(rid,[])
            results.append({'requirement_id':rid,'policies':ev,'coverage':max([e['score'] for e in ev],default=0)})
        return {'findings':results}
    def risk(s):
        results=[]
        for f in s['findings']:
            req=db.get(Requirement,f['requirement_id']); critical=bool(re.search('suspicious|encrypt|incident|prohibit',req.description,re.I))
            factors={'severity':5 if critical else 3,'likelihood':4 if f['coverage']<.25 else 2,'regulatory_impact':5 if critical else 3,'operational_impact':4 if critical else 2}
            score,level=assess(factors,configured_weights(db,user.institution_id)); results.append({**f,'factors':factors,'score':score,'level':level})
        return {'findings':results}
    def recommendations(s):
        return {'findings':[{**f,'recommendation':'Human verification required. Review the cited obligation, validate existing controls, document the control owner and evidence, and propose a dated policy update where a gap is confirmed.'} for f in s['findings']]}
    def validation(s):
        # Citations derive exclusively from stored chunks; no generated clause identifiers.
        insufficient=any(not f['policies'] for f in s['findings'])
        return {'insufficient':insufficient}
    def escalation(s):
        doc=db.get(Document,s['document_id'])
        for f in s['findings']:
            req=db.get(Requirement,f['requirement_id']); chunk=db.get(Chunk,req.chunk_id)
            record=Finding(institution_id=user.institution_id,requirement_id=req.id,workflow_id=run.id,title=req.title,description='Heuristic interpretation: policy retrieval does not establish control effectiveness. A compliance officer must verify this potential gap.',department=req.department,status='Requires human verification',risk_score=f['score'],risk_level=f['level'],factors=f['factors'],evidence=[citation(chunk,doc)],policy_evidence=f['policies'],recommendation=f['recommendation'],confidence=.65,review_status='Pending')
            db.add(record)
        if s['findings']:
            notification=Notification(institution_id=user.institution_id,title=f'{len(s["findings"])} findings await human review');db.add(notification)
            from .notifications import deliver
            deliver(db,notification)
        return {'paused':bool(s['findings'])}
    def audit(s):
        run.status='Awaiting human review' if s.get('paused') else 'Completed'
        run.state={**{k:v for k,v in s.items() if k not in ('evidence','findings')},'native_checkpoint':True}
        log(db,user,'workflow.paused' if s.get('paused') else 'workflow.completed',run.id,{'findings':len(s['findings'])})
        return {}
    graph=StateGraph(State)
    def human_gate(s):
        if s.get('paused'):
            from langgraph.types import interrupt
            interrupt({'workflow_id':run.id,'reason':'Authorized human review required for all findings'})
            pending=db.scalar(select(Finding).where(Finding.workflow_id==run.id,Finding.review_status.not_in(['Approved','Rejected'])).limit(1))
            if pending:raise ValueError('All findings require final human decisions before resume')
            run.status='Completed';run.stage='Human review complete';run.state={**run.state,'paused':False,'resumed_by':user.id,'resumed_at':now()}
            log(db,user,'workflow.native_resumed',run.id)
        return {'paused':False}
    graph.add_node('human_gate',human_gate)
    for name,fn in [('ingestion',ingestion),('changes',changes),('requirements',requirements),('retrieval',retrieval),('gaps',gaps),('risk',risk),('recommendations',recommendations),('validation',validation),('escalation',escalation),('audit',audit)]: graph.add_node(name,step(name,fn))
    graph.add_edge(START,'ingestion')
    for a,b in [('ingestion','changes'),('changes','requirements'),('requirements','retrieval'),('retrieval','gaps'),('gaps','risk'),('risk','recommendations'),('recommendations','validation'),('escalation','audit'),('audit','human_gate'),('human_gate',END)]: graph.add_edge(a,b)
    graph.add_conditional_edges('validation',lambda s:'retrieval' if s['insufficient'] and s['attempts']<2 else 'escalation',{'retrieval':'retrieval','escalation':'escalation'})
    return graph.compile(checkpointer=checkpointer)

def execute(db,user,doc):
    if doc.kind!='regulation': raise ValueError('Analyze a regulatory document; policies provide comparison evidence')
    existing=db.scalar(select(Workflow).where(Workflow.document_id==doc.id,Workflow.status.in_(['Running','Awaiting human review','Completed'])))
    if existing: return existing
    run=Workflow(institution_id=user.institution_id,document_id=doc.id,steps=[],state={},errors=[]); db.add(run); db.flush()
    try:
        from .checkpoints import saver
        with saver() as checkpoint:
            build_graph(db,user,run,checkpoint).invoke({'workflow_id':run.id,'document_id':doc.id,'tenant':user.institution_id},config={'configurable':{'thread_id':run.id}})
        doc.status='Analyzed'; db.commit()
    except Exception as exc:
        db.rollback()
        run=Workflow(institution_id=user.institution_id,document_id=doc.id,status='Failed',stage='Failed',steps=[],state={},errors=[str(exc)[:500]])
        db.add(run); log(db,user,'workflow.failed',doc.id,{'error':str(exc)[:500]}); db.commit()
    return run
def resume(db,user,run):
    from .checkpoints import saver
    from langgraph.types import Command
    with saver() as checkpoint:
        graph=build_graph(db,user,run,checkpoint)
        config={'configurable':{'thread_id':run.id}}
        if not graph.get_state(config).next:raise ValueError('No interrupted checkpoint found')
        graph.invoke(Command(resume={'reviewed_by':user.id}),config=config)
    db.commit()
