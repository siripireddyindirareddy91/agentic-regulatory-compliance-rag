"""Policy mappings and durable remediation evidence."""
import base64, hashlib, os
from fastapi import Depends, File, UploadFile, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from .models import Document, Requirement, Finding, PolicyMapping, Attachment, Action, Workflow, Notification, now
from .security import session

def mount(app,read,write,reviewer,owned,allrows,data,save):
    @app.get('/api/requirements')
    def requirements(user=Depends(read),db=Depends(session)):
        return [data(r) for r in allrows(db,Requirement,user)]
    class MappingBody(BaseModel):
        requirement_id:str
        notes:str=Field(default='',max_length=4000)
    @app.get('/api/policies/{id}/mappings')
    def mappings(id:str,user=Depends(read),db=Depends(session)):
        owned(db,Document,id,user)
        return [data(m) for m in allrows(db,PolicyMapping,user) if m.policy_id==id]
    @app.post('/api/policies/{id}/map')
    def map_policy(id:str,body:MappingBody,user=Depends(reviewer),db=Depends(session)):
        policy=owned(db,Document,id,user); owned(db,Requirement,body.requirement_id,user)
        if policy.kind!='policy': raise HTTPException(422,'Expected an internal policy')
        mapping=db.scalar(select(PolicyMapping).where(PolicyMapping.policy_id==id,PolicyMapping.requirement_id==body.requirement_id))
        if mapping: mapping.notes=body.notes
        else:
            mapping=PolicyMapping(institution_id=user.institution_id,policy_id=id,requirement_id=body.requirement_id,notes=body.notes,mapped_by=user.id); db.add(mapping); db.flush()
        save(db,user,'policy.mapped',id,{'requirement_id':body.requirement_id,'notes':body.notes})
        return data(mapping)
    @app.get('/api/actions/{id}/evidence')
    def attachments(id:str,user=Depends(read),db=Depends(session)):
        owned(db,Action,id,user)
        return [{k:v for k,v in data(a).items() if k!='content'} for a in allrows(db,Attachment,user) if a.action_id==id]
    @app.post('/api/actions/{id}/evidence')
    async def attach(id:str,file:UploadFile=File(...),user=Depends(write),db=Depends(session)):
        owned(db,Action,id,user)
        blob=await file.read(5*1024*1024+1)
        if not blob or len(blob)>5*1024*1024: raise HTTPException(413,'Evidence files must be between 1 byte and 5 MB')
        name=os.path.basename((file.filename or 'evidence.bin').replace('\\','/'))[:240]
        if name.rsplit('.',1)[-1].lower() not in ['pdf','docx','txt','csv','png','jpg','jpeg','xlsx']: raise HTTPException(415,'Unsupported evidence type')
        a=Attachment(institution_id=user.institution_id,action_id=id,filename=name,content_type='application/octet-stream',content=base64.b64encode(blob).decode(),sha256=hashlib.sha256(blob).hexdigest(),uploaded_by=user.id)
        db.add(a); db.flush(); save(db,user,'action.evidence_attached',id,{'attachment_id':a.id,'sha256':a.sha256,'filename':name})
        return {k:v for k,v in data(a).items() if k!='content'}
    @app.get('/api/evidence/{id}/download')
    def download_attachment(id:str,user=Depends(read),db=Depends(session)):
        from urllib.parse import quote
        a=owned(db,Attachment,id,user)
        save(db,user,'evidence.downloaded',a.id)
        return Response(base64.b64decode(a.content),media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(a.filename),'X-Content-Type-Options':'nosniff'})
    @app.post('/api/actions/escalate-overdue')
    def overdue(user=Depends(write),db=Depends(session)):
        count=0
        for a in allrows(db,Action,user):
            if a.status not in ['Completed','Overdue'] and a.due_date<now()[:10]:
                a.status='Overdue'; count+=1
                db.add(Notification(institution_id=user.institution_id,title='Overdue corrective action: '+a.title))
                save(db,user,'action.overdue',a.id,{'due_date':a.due_date})
        return {'escalated':count}
    @app.post('/api/agents/executions/{id}/retry')
    def retry(id:str,user=Depends(write),db=Depends(session)):
        from .workflow import execute
        run=owned(db,Workflow,id,user)
        if run.status!='Failed': raise HTTPException(409,'Only failed workflows can be retried')
        return data(execute(db,user,owned(db,Document,run.document_id,user)))
