"""Optional embedding, FAISS and reranking adapters. Local hashing remains free."""
import os,math
from functools import lru_cache
def name():return os.getenv('EMBEDDING_PROVIDER','local')+':'+os.getenv('EMBEDDING_MODEL','default')
@lru_cache(maxsize=2048)
def embedding(text):
    provider=os.getenv('EMBEDDING_PROVIDER','local')
    if provider=='openai':
        from openai import OpenAI
        return OpenAI(timeout=20,max_retries=1).embeddings.create(model=os.getenv('EMBEDDING_MODEL','text-embedding-3-small'),input=text,dimensions=256).data[0].embedding
    if provider=='sentence-transformers':
        values=sentence_model().encode(text,normalize_embeddings=True).tolist()[:256]
        values+=(256-len(values))*[0.0];norm=math.sqrt(sum(v*v for v in values)) or 1
        return [v/norm for v in values]
    if provider!='local':raise ValueError('Unknown EMBEDDING_PROVIDER')
    from .rag import local_embed
    return local_embed(text)
@lru_cache
def sentence_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(os.getenv('EMBEDDING_MODEL','sentence-transformers/all-MiniLM-L6-v2'))
@lru_cache
def cross_encoder():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(os.getenv('RERANKER_MODEL','cross-encoder/ms-marco-MiniLM-L-6-v2'))
def rerank(query,results):
    if os.getenv('RERANKER_PROVIDER','none')!='cross-encoder' or not results:return results
    scores=cross_encoder().predict([(query,r['excerpt']) for r in results])
    return sorted([{**r,'rerank_score':float(score)} for r,score in zip(results,scores)],key=lambda r:r['rerank_score'],reverse=True)
def faiss_scores(query,vectors):
    import faiss,numpy as np
    if not vectors:return {}
    ids=list(vectors);array=np.asarray([vectors[k] for k in ids],dtype='float32');index=faiss.IndexFlatIP(256);index.add(array)
    scores,positions=index.search(np.asarray([query],dtype='float32'),len(ids))
    return {ids[i]:float(score) for i,score in zip(positions[0],scores[0]) if i>=0}
