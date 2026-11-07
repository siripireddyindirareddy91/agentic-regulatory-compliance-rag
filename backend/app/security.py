import os, secrets, jwt, hashlib
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pwdlib import PasswordHash
from .models import Session, User, RefreshSession

passwords = PasswordHash.recommended()
SECRET = os.getenv('JWT_SECRET_KEY') or secrets.token_urlsafe(48)
if os.getenv('APP_ENV') == 'production' and not os.getenv('JWT_SECRET_KEY'):
    raise RuntimeError('Production requires a stable JWT_SECRET_KEY')
bearer = HTTPBearer(auto_error=False)
def session():
    with Session() as db: yield db
def token(user, kind='access'):
    return jwt.encode({'sub':user.id, 'type':kind, 'jti':secrets.token_hex(16), 'exp':datetime.now(timezone.utc)+timedelta(minutes=30 if kind=='access' else 1440)}, SECRET, algorithm='HS256')
def decode(value, kind='access'):
    try:
        claims=jwt.decode(value, SECRET, algorithms=['HS256'])
        if claims.get('type') != kind: raise ValueError()
        return claims['sub']
    except Exception: raise HTTPException(401, 'Invalid or expired token')
def issue_refresh(db,user):
    value=token(user,'refresh')
    db.add(RefreshSession(institution_id=user.institution_id,user_id=user.id,token_hash=hashlib.sha256(value.encode()).hexdigest(),expires_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()))
    db.commit();return value
def rotate_refresh(db,value):
    from sqlalchemy import select
    user_id=decode(value,'refresh')
    row=db.scalar(select(RefreshSession).where(RefreshSession.token_hash==hashlib.sha256(value.encode()).hexdigest()).with_for_update())
    if not row or row.revoked or row.user_id!=user_id:raise HTTPException(401,'Refresh session revoked or already rotated')
    row.revoked=True;user=db.get(User,user_id)
    if not user:raise HTTPException(401,'User not found')
    replacement=issue_refresh(db,user)
    return {'access_token':token(user),'refresh_token':replacement}
def current(auth: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(session)):
    if not auth: raise HTTPException(401, 'Sign in required')
    user=db.get(User, decode(auth.credentials))
    if not user: raise HTTPException(401, 'User no longer exists')
    return user
def roles(*allowed):
    def check(user=Depends(current)):
        if user.role not in allowed: raise HTTPException(403, 'Your role cannot perform this operation')
        return user
    return check
