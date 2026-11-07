"""Deterministic signed feature hashing + lexical retrieval; no paid API required."""
import re, math, hashlib, io, csv, os
from fastapi import HTTPException
from sqlalchemy import select
from .models import Chunk, Document
STOP=set('the a an of to and or in for is be shall must with by as on at all it are that this'.split())
def words(text): return [w for w in re.findall(r'[a-z0-9]+', text.lower()) if w not in STOP and len(w)>1]
def local_embed(text, dimensions=256):
    v=[0.0]*dimensions
    terms=words(text)
    terms += [a+'_'+b for a,b in zip(terms,terms[1:])]
    for word in terms:
        h=hashlib.sha256(word.encode()).digest(); v[int.from_bytes(h[:4],'little')%dimensions] += 1 if h[4]%2 else -1
    norm=math.sqrt(sum(x*x for x in v)) or 1
    return [x/norm for x in v]
def embed(text,dimensions=256):
    from .providers import embedding
    return embedding(text)
def extract(data, filename):
    suffix=filename.rsplit('.',1)[-1].lower()
    try:
        if suffix=='pdf':
            import pymupdf
            with pymupdf.open(stream=data,filetype='pdf') as doc:
                if len(doc)>500: raise HTTPException(422,'Maximum 500 PDF pages')
                pages=[]
                for i,p in enumerate(doc):
                    text=p.get_text()
                    if not text.strip() and os.getenv('OCR_ENABLED','false')=='true':
                        try:text=p.get_text(textpage=p.get_textpage_ocr(language=os.getenv('OCR_LANGUAGE','eng'),dpi=150,full=True))
                        except Exception as exc:raise HTTPException(422,'OCR unavailable: install Tesseract and configure TESSDATA_PREFIX on the backend') from exc
                    pages.append((i+1,text))
                return pages
        if suffix=='docx':
            import zipfile
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if sum(f.file_size for f in z.infolist())>40*1024*1024: raise HTTPException(413,'Expanded DOCX too large')
            from docx import Document as Word
            doc=Word(io.BytesIO(data)); return [(1,'\n'.join([p.text for p in doc.paragraphs]+[' | '.join(c.text for c in r.cells) for t in doc.tables for r in t.rows]))]
        if suffix in ('txt','csv'): return [(1,data.decode('utf-8-sig'))]
    except HTTPException: raise
    except Exception: raise HTTPException(422,'Could not extract document. Use a text PDF, DOCX, UTF-8 TXT or CSV.')
    raise HTTPException(415,'Supported file types: PDF, DOCX, TXT, CSV')
def index(db, doc, pages=None):
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter=RecursiveCharacterTextSplitter(chunk_size=1000,chunk_overlap=150)
    for page,text in pages or [(1,doc.text)]:
        for part in splitter.split_text(text):
            section=next((s.strip() for s in part.splitlines() if s.strip()),'Extracted text')[:180]
            db.add(Chunk(institution_id=doc.institution_id, document_id=doc.id, page=page,section=section,text=part,vector=embed(part)))
    db.flush()
    from .models import EmbeddingProfile
    from .providers import name
    for chunk in db.scalars(select(Chunk).where(Chunk.document_id==doc.id)):
        profile=db.scalar(select(EmbeddingProfile).where(EmbeddingProfile.chunk_id==chunk.id))
        if profile:profile.provider=name()
        else:db.add(EmbeddingProfile(institution_id=doc.institution_id,chunk_id=chunk.id,provider=name()))
    db.flush()
    from .vectors import upsert
    for chunk in db.scalars(select(Chunk).where(Chunk.document_id==doc.id)): upsert(db,chunk)
def citation(chunk, doc, score=1):
    return {'chunk_id':chunk.id,'document_id':doc.id,'document':doc.title,'authority':doc.authority,'page':chunk.page,'section':chunk.section,'excerpt':chunk.text,'source_url':doc.source_url,'version':doc.version,'jurisdiction':doc.jurisdiction,'publication_date':doc.publication_date,'verification':doc.verification,'demo':doc.demo,'score':round(score,4)}
def search(db, tenant, query, kind=None, authority=None, limit=6):
    stmt=select(Chunk,Document).join(Document,Chunk.document_id==Document.id).where(Document.institution_id==tenant)
    if kind: stmt=stmt.where(Document.kind==kind)
    if authority: stmt=stmt.where(Document.authority==authority)
    qvec=embed(query); qwords=set(words(query)); ranked=[]
    from .vectors import nearest
    semantic=nearest(db,tenant,qvec)
    from .models import EmbeddingProfile
    from .providers import name,faiss_scores
    profiles={p.chunk_id:p.provider for p in db.scalars(select(EmbeddingProfile).where(EmbeddingProfile.institution_id==tenant))}
    if os.getenv('VECTOR_STORE')=='faiss':
        semantic=faiss_scores(qvec,{c.id:c.vector for c,d in db.execute(stmt) if profiles.get(c.id,'local:default')==name()})
    for c,d in db.execute(stmt):
        lex=len(qwords & set(words(c.text)))/max(len(qwords),1)
        compatible=profiles.get(c.id,'local:default')==name()
        cosine=(semantic.get(c.id,0) if semantic is not None else sum(a*b for a,b in zip(qvec,c.vector))) if compatible else 0
        score=.55*max(cosine,0)+.45*lex
        if score>.04: ranked.append(citation(c,d,score))
    from .providers import rerank
    return rerank(query,sorted(ranked,key=lambda x:x['score'],reverse=True)[:max(limit,20)])[:limit]
