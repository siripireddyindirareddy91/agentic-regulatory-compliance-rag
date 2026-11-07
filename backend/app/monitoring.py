"""Bounded official-source monitoring; no assumption that a changed page is a mandate."""
import os, socket, ipaddress, hashlib
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from html.parser import HTMLParser
import httpx
from sqlalchemy import select
from .models import Document, Source, MonitorState, Notification, now
from .rag import index, extract
from .audit import log
DEFAULT_HOSTS=['rbi.org.in','www.rbi.org.in','sebi.gov.in','www.sebi.gov.in','irdai.gov.in','fiuindia.gov.in','www.fatf-gafi.org','www.bis.org','financialservices.gov.in']
def validate_url(url):
    p=urlparse(url); allowed=os.getenv('MONITOR_ALLOWED_HOSTS',','.join(DEFAULT_HOSTS)).split(',')
    if p.scheme!='https' or p.hostname not in allowed or p.username or p.password or p.port not in (None,443): raise ValueError('Monitoring requires an allowlisted official HTTPS host')
    for addr in socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(addr[4][0]).is_global: raise ValueError('Non-public source address blocked')
    return p
def bounded_fetch(client,url,limit=2*1024*1024):
    for _ in range(4):
        validate_url(url)
        with client.stream('GET',url) as response:
            if response.status_code in (301,302,303,307,308): url=urljoin(url,response.headers['location']); continue
            response.raise_for_status(); parts=[]; size=0
            for chunk in response.iter_bytes():
                size+=len(chunk)
                if size>limit: raise ValueError('Source exceeds monitoring download limit')
                parts.append(chunk)
            return b''.join(parts),response.headers.get('content-type',''),url
    raise ValueError('Too many redirects')
class PageText(HTMLParser):
    def __init__(self): super().__init__(); self.hidden=0; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript'): self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'): self.hidden=max(self.hidden-1,0)
    def handle_data(self,data):
        if not self.hidden and data.strip(): self.parts.append(data.strip())
def monitor(db,user,source):
    p=validate_url(source.url)
    state=db.scalar(select(MonitorState).where(MonitorState.source_id==source.id))
    if not state: state=MonitorState(institution_id=source.institution_id,source_id=source.id);db.add(state);db.flush()
    with httpx.Client(timeout=10,follow_redirects=False,headers={'User-Agent':'ComplyIntelMonitor/1.0 (+manual compliance review)'}) as client:
        robots_url=p.scheme+'://'+p.netloc+'/robots.txt'
        try:
            robots,_,_=bounded_fetch(client,robots_url,65536)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code!=404: raise ValueError('Cannot establish source access rules')
            robots=b''
        parser=RobotFileParser();parser.parse(robots.decode('utf-8','replace').splitlines())
        if not parser.can_fetch('ComplyIntelMonitor',source.url): raise ValueError('Source robots.txt disallows monitoring')
        delay=parser.crawl_delay('ComplyIntelMonitor') or 0
        if delay>0 and state.last_checked:
            from datetime import datetime,timezone
            if (datetime.now(timezone.utc)-datetime.fromisoformat(state.last_checked)).total_seconds()<delay: raise ValueError('Source crawl-delay has not elapsed')
        blob,ctype,url=bounded_fetch(client,source.url)
    if 'pdf' in ctype: pages=extract(blob,'source.pdf'); text='\n'.join(t for _,t in pages)
    else:
        html=PageText();html.feed(blob.decode('utf-8','replace'));text='\n'.join(html.parts);pages=[(1,text)]
    if not text.strip(): raise ValueError('No extractable source text')
    digest=hashlib.sha256(text.encode()).hexdigest(); changed=bool(state.last_hash and state.last_hash!=digest)
    doc=db.scalar(select(Document).where(Document.institution_id==user.institution_id,Document.content_hash==digest))
    if not doc:
        previous=db.scalar(select(Document).where(Document.institution_id==user.institution_id,Document.source_url==url).order_by(Document.created_at.desc()))
        doc=Document(institution_id=user.institution_id,title=source.name+' · monitored source snapshot',authority=source.name,jurisdiction=source.jurisdiction,text=text,content_hash=digest,source_url=url,verification='Retrieved official host / content unverified',kind='regulation',previous_id=previous.id if previous else None,version=previous.version+1 if previous else 1)
        db.add(doc);db.flush();index(db,doc,pages)
        db.add(Notification(institution_id=user.institution_id,title=source.name+(': source content changed; human review required' if changed else ': initial source snapshot collected')))
    state.last_checked=now();state.last_hash=digest;state.status='Changed' if changed else 'Fetched';state.detail={'document_id':doc.id,'source_url':url,'notice':'A source-page change is not a verified new regulatory mandate.'}
    log(db,user,'monitor.fetched',source.id,{'changed':changed,'document_id':doc.id});db.commit()
    return state.detail
