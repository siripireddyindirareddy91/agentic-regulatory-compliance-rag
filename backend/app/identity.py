"""Administrator-issued, expiring, single-use invitation and recovery grants."""
import secrets,hashlib
from datetime import datetime,timedelta,timezone
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from .models import User,AccessGrant,RefreshSession,now
from .security import session,passwords
def mount(app,admin,owned,allrows,data,save):
    @app.get('/api/admin/users')
    def users(user=Depends(admin),db=Depends(session)):return [data(u) for u in allrows(db,User,user)]
    class Invite(BaseModel):
        email:str=Field(min_length=3,max_length=240)
        role:str='viewer'
    def grant(db,user,email,purpose,role):
        token=secrets.token_urlsafe(40)
        db.add(AccessGrant(institution_id=user.institution_id,email=email,role=role,purpose=purpose,token_hash=hashlib.sha256(token.encode()).hexdigest(),expires_at=(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat()))
        save(db,user,'account.'+purpose+'_issued','',{'email':email,'role':role})
        return {'token':token,'expires_in_hours':24,'purpose':purpose,'notice':'Share this single-use link privately with the intended account holder.'}
    @app.post('/api/admin/invitations')
    def invite(body:Invite,user=Depends(admin),db=Depends(session)):
        email=body.email.lower().strip()
        if '@' not in email or body.role not in ['admin','reviewer','analyst','viewer']:raise HTTPException(422,'Invalid email or role')
        if db.scalar(select(User).where(User.email==email)):raise HTTPException(409,'Account already exists')
        return grant(db,user,email,'invite',body.role)
    @app.post('/api/admin/users/{id}/recovery')
    def recovery(id:str,user=Depends(admin),db=Depends(session)):
        target=owned(db,User,id,user)
        return grant(db,user,target.email,'recovery',target.role)
    class Redeem(BaseModel):
        token:str=Field(min_length=20,max_length=200)
        password:str=Field(min_length=12,max_length=200)
        name:str=Field(default='Account holder',min_length=2,max_length=100)
    @app.post('/api/auth/redeem')
    def redeem(body:Redeem,db=Depends(session)):
        row=db.scalar(select(AccessGrant).where(AccessGrant.token_hash==hashlib.sha256(body.token.encode()).hexdigest()).with_for_update())
        if not row or row.consumed or row.expires_at<=now():raise HTTPException(401,'Invalid, expired or already used account link')
        account=db.scalar(select(User).where(User.email==row.email))
        if row.purpose=='invite':
            if account:raise HTTPException(409,'Account already exists')
            account=User(institution_id=row.institution_id,email=row.email,name=body.name,role=row.role,password_hash=passwords.hash(body.password));db.add(account);db.flush()
        else:
            if not account or account.institution_id!=row.institution_id:raise HTTPException(401,'Invalid account link')
            account.password_hash=passwords.hash(body.password)
            for refresh in db.scalars(select(RefreshSession).where(RefreshSession.user_id==account.id)):refresh.revoked=True
        row.consumed=True;save(db,account,'account.'+row.purpose+'_completed',account.id)
        return {'completed':True,'email':account.email,'notice':'Sign in with your new password. Previously issued access tokens expire within 30 minutes.'}
