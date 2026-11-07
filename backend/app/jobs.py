"""Database queue: leased, fenced, retryable jobs; PostgreSQL SKIP LOCKED workers."""
import io,csv,uuid
from datetime import datetime,timedelta,timezone
from sqlalchemy import select,or_,and_
from .models import Session,Job,User,Source,Document,Finding,GeneratedReport,MonitorState,now
from .audit import log
def later(seconds): return (datetime.now(timezone.utc)+timedelta(seconds=seconds)).isoformat()
def enqueue(db,user,kind,payload,key=None):
    key=key or uuid.uuid4().hex
    previous=db.scalar(select(Job).where(Job.institution_id==user.institution_id,Job.dedupe_key==key))
    if previous:return previous
    job=Job(institution_id=user.institution_id,actor_id=user.id,kind=kind,payload=payload,dedupe_key=key)
    db.add(job);db.flush();log(db,user,'job.queued',job.id,{'kind':kind});db.commit();return job
def run_one(tenant=None):
    worker=uuid.uuid4().hex
    with Session() as db:
        stmt=select(Job).where(or_(and_(Job.status.in_(['Queued','Retry']),Job.available_at<=now()),and_(Job.status=='Running',Job.lease_until<now()))).order_by(Job.available_at).limit(1)
        if tenant:stmt=stmt.where(Job.institution_id==tenant)
        if db.bind.dialect.name=='postgresql':stmt=stmt.with_for_update(skip_locked=True)
        job=db.scalar(stmt)
        if not job:return None
        job.status='Running';job.lease_owner=worker;job.lease_until=later(180);job.attempts+=1;db.commit();id=job.id;attempts=job.attempts;user=db.get(User,job.actor_id)
        try:
            if job.kind=='monitor':
                from .monitoring import monitor
                source=db.get(Source,job.payload['source_id'])
                if not source or source.institution_id!=job.institution_id or not source.enabled:raise ValueError('Source missing or disabled')
                result=monitor(db,user,source)
            elif job.kind=='analyze':
                from .workflow import execute
                doc=db.get(Document,job.payload['document_id'])
                if not doc or doc.institution_id!=job.institution_id:raise ValueError('Document not found')
                run=execute(db,user,doc)
                if run.status=='Failed':raise ValueError('; '.join(run.errors))
                result={'workflow_id':run.id,'status':run.status}
            elif job.kind=='report':
                rows=db.scalars(select(Finding).where(Finding.institution_id==job.institution_id)).all();stream=io.StringIO();w=csv.writer(stream);w.writerow(['DEMO / UNVERIFIED compliance report',now()]);w.writerow(['Finding','Department','Risk','Score','Review'])
                for f in rows:w.writerow([("'" if f.title.startswith(('=','+','-','@')) else '')+f.title,f.department,f.risk_level,f.risk_score,f.review_status])
                report=db.scalar(select(GeneratedReport).where(GeneratedReport.job_id==id))
                if not report:report=GeneratedReport(institution_id=user.institution_id,title='Scheduled compliance report',content=stream.getvalue(),job_id=id);db.add(report);db.flush()
                result={'report_id':report.id,'rows':len(rows)}
            else:raise ValueError('Unknown job kind')
            db.commit();db.refresh(job)
            if job.lease_owner!=worker:return {'id':id,'status':'Lease lost'}
            job.status='Completed';job.result=result;job.lease_until='';log(db,user,'job.completed',id,result);db.commit()
        except Exception as exc:
            db.rollback();job=db.get(Job,id)
            if job.lease_owner!=worker:return {'id':id,'status':'Lease lost'}
            job.status='Failed' if attempts>=3 else 'Retry';job.error=str(exc)[:1000];job.available_at=later(30*2**(attempts-1));job.lease_until='';log(db,user,'job.'+job.status.lower(),id,{'attempt':attempts,'error':job.error});db.commit()
        return {'id':id,'status':job.status}
def schedule(db):
    from .models import Setting
    count=0
    for state in db.scalars(select(MonitorState).where(MonitorState.next_check<=now())).all():
        source=db.get(Source,state.source_id)
        if not source or not source.enabled:continue
        user=db.scalar(select(User).where(User.institution_id==source.institution_id,User.role=='admin'))
        if not user:continue
        enqueue(db,user,'monitor',{'source_id':source.id},'monitor:'+source.id+':'+state.next_check)
        state.next_check=later(state.interval_hours*3600);db.commit();count+=1
    for setting in db.scalars(select(Setting).where(Setting.key=='report_schedule')).all():
        if not setting.value.get('enabled') or setting.value.get('next_run','')>now():continue
        user=db.scalar(select(User).where(User.institution_id==setting.institution_id,User.role=='admin'))
        if user:
            enqueue(db,user,'report',{},'report:'+setting.institution_id+':'+setting.value.get('next_run','initial'))
            setting.value={**setting.value,'next_run':later(86400)};db.commit();count+=1
    return count
