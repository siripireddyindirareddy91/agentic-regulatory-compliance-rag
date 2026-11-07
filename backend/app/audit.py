import hashlib, json
from sqlalchemy import select
from .models import Audit, uid, now

def digest(row):
    payload={k:getattr(row,k) for k in ('id','institution_id','created_at','actor','event','entity_id','detail','previous_hash','sequence')}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',',':')).encode()).hexdigest()
def log(db, user, event, entity_id='', detail=None):
    tenant=user.institution_id if hasattr(user,'institution_id') else user
    # Serialize audit writers in PostgreSQL; SQLite serializes write transactions.
    if db.bind.dialect.name == 'postgresql':
        from sqlalchemy import text
        db.execute(text('SELECT pg_advisory_xact_lock(hashtext(:tenant))'), {'tenant':tenant})
    last=db.scalar(select(Audit).where(Audit.institution_id==tenant).order_by(Audit.sequence.desc()).limit(1))
    row=Audit(id=uid(), institution_id=tenant, created_at=now(), actor=getattr(user,'email','system'), event=event, entity_id=entity_id, detail=detail or {}, previous_hash=last.hash if last else '0'*64, sequence=last.sequence+1 if last else 1)
    row.hash=digest(row); db.add(row); db.flush(); return row
def verify(db, tenant):
    rows=db.scalars(select(Audit).where(Audit.institution_id==tenant).order_by(Audit.sequence)).all()
    previous='0'*64
    for i,r in enumerate(rows,1):
        if r.sequence!=i or r.previous_hash!=previous or digest(r)!=r.hash: return {'valid':False,'events':len(rows),'broken_at':r.id}
        previous=r.hash
    return {'valid':True,'events':len(rows),'head':previous,'note':'Application-level tamper evidence, not legal immutability.'}
