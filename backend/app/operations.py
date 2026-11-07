import os,secrets
from fastapi import Depends,HTTPException,Header
from fastapi.responses import Response
from pydantic import BaseModel,Field
from sqlalchemy import select
from .models import Job,Source,MonitorState,GeneratedReport,Setting,Document,now
from .security import session
from .jobs import enqueue,run_one,schedule

def mount(app,read,write,admin,owned,allrows,data,save):
    @app.post('/api/demo/expand')
    def add_demo(user=Depends(admin),db=Depends(session)):
        if os.getenv('DEMO_MODE','true')!='true':raise HTTPException(403,'Demo expansion disabled')
        from .demo import expand
        return expand(db,user)
    @app.get('/api/jobs')
    def jobs(user=Depends(read),db=Depends(session)):return [data(j) for j in allrows(db,Job,user)]
    class JobBody(BaseModel):
        kind:str
        document_id:str=''
        source_id:str=''
    @app.post('/api/jobs')
    def queue(body:JobBody,user=Depends(write),db=Depends(session)):
        if body.kind=='analyze':owned(db,Document,body.document_id,user)
        elif body.kind=='monitor':
            if user.role!='admin':raise HTTPException(403,'Administrator required')
            owned(db,Source,body.source_id,user)
        elif body.kind!='report':raise HTTPException(422,'Unknown job kind')
        return data(enqueue(db,user,body.kind,body.model_dump()))
    @app.post('/api/jobs/process')
    def process(user=Depends(admin)):
        return {'result':run_one(user.institution_id)}
    @app.get('/api/monitoring')
    def monitoring(user=Depends(read),db=Depends(session)):
        return [{**data(source),'monitor':next((data(s) for s in allrows(db,MonitorState,user) if s.source_id==source.id),None)} for source in allrows(db,Source,user)]
    class MonitorBody(BaseModel):
        enabled:bool
        interval_hours:int=Field(default=24,ge=24,le=720)
    @app.patch('/api/sources/{id}/monitoring')
    def configure(id:str,body:MonitorBody,user=Depends(admin),db=Depends(session)):
        from .monitoring import validate_url
        source=owned(db,Source,id,user)
        if body.enabled:
            try:validate_url(source.url)
            except ValueError as e:raise HTTPException(422,str(e))
        source.enabled=body.enabled
        state=db.scalar(select(MonitorState).where(MonitorState.source_id==id))
        if not state:state=MonitorState(institution_id=user.institution_id,source_id=id,interval_hours=body.interval_hours);db.add(state)
        else:state.interval_hours=body.interval_hours;state.next_check=now()
        save(db,user,'monitor.configured',id,body.model_dump())
        return data(state)
    @app.get('/api/ml/status')
    def ml_status(user=Depends(read)):
        from .ml import artifact
        m=artifact();return {k:m[k] for k in ['version','notice','metrics','classes']}
    class PredictBody(BaseModel):text:str=Field(min_length=10,max_length=30000)
    @app.post('/api/ml/predict')
    def ml_predict(body:PredictBody,user=Depends(read),db=Depends(session)):
        from .ml import predict
        result=predict(body.text);save(db,user,'ml.classified','',{'category':result['category'],'version':result['version']});return result
    @app.get('/api/scheduled-reports')
    def reports(user=Depends(read),db=Depends(session)):return [{k:v for k,v in data(r).items() if k!='content'} for r in allrows(db,GeneratedReport,user)]
    @app.get('/api/scheduled-reports/{id}')
    def report(id:str,user=Depends(read),db=Depends(session)):
        r=owned(db,GeneratedReport,id,user);return Response(r.content.encode('utf-8-sig'),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="scheduled-compliance.csv"'})
    @app.post('/api/report-schedule')
    def report_schedule(body:MonitorBody,user=Depends(admin),db=Depends(session)):
        s=db.scalar(select(Setting).where(Setting.institution_id==user.institution_id,Setting.key=='report_schedule'))
        value={'enabled':body.enabled,'next_run':now(),'interval_hours':24}
        if s:s.value=value
        else:db.add(Setting(institution_id=user.institution_id,key='report_schedule',value=value))
        save(db,user,'report.schedule_changed','',value);return value
    @app.get('/api/cron')
    def cron(authorization:str=Header(default=''),db=Depends(session)):
        secret=os.getenv('CRON_SECRET')
        if not secret or not secrets.compare_digest(authorization,'Bearer '+secret):raise HTTPException(401,'Invalid scheduler credentials')
        queued=schedule(db);results=[]
        for _ in range(3):
            result=run_one()
            if not result:break
            results.append(result)
        return {'queued':queued,'processed':results}
