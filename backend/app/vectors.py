"""Native PostgreSQL pgvector storage with tenant-filtered cosine retrieval."""
import json
from sqlalchemy import text

def initialize(connection):
    if connection.dialect.name!='postgresql': return
    connection.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    connection.execute(text('''CREATE TABLE IF NOT EXISTS document_embeddings (
        chunk_id VARCHAR(36) PRIMARY KEY REFERENCES document_chunks(id) ON DELETE CASCADE,
        institution_id VARCHAR(36) NOT NULL,
        embedding vector(256) NOT NULL,
        provider VARCHAR(80) NOT NULL DEFAULT 'local-hash-v1'
    )'''))
    connection.execute(text('CREATE INDEX IF NOT EXISTS ix_embeddings_tenant ON document_embeddings(institution_id)'))
    connection.execute(text('CREATE INDEX IF NOT EXISTS ix_embeddings_cosine ON document_embeddings USING hnsw (embedding vector_cosine_ops)'))
def upsert(db,chunk):
    if db.bind.dialect.name!='postgresql': return
    from .providers import name
    db.execute(text('''INSERT INTO document_embeddings(chunk_id,institution_id,embedding,provider)
      VALUES (:id,:tenant,CAST(:vector AS vector),:provider)
      ON CONFLICT(chunk_id) DO UPDATE SET embedding=EXCLUDED.embedding,provider=EXCLUDED.provider'''),{'id':chunk.id,'tenant':chunk.institution_id,'vector':json.dumps(chunk.vector),'provider':name()[:80]})
def nearest(db,tenant,vector,limit=100):
    if db.bind.dialect.name!='postgresql': return None
    from .providers import name
    rows=db.execute(text('''SELECT chunk_id, 1-(embedding <=> CAST(:vector AS vector)) AS similarity
      FROM document_embeddings WHERE institution_id=:tenant AND (provider=:provider OR (:provider='local:default' AND provider='local-hash-v1'))
      ORDER BY embedding <=> CAST(:vector AS vector) LIMIT :limit'''),{'tenant':tenant,'vector':json.dumps(vector),'limit':limit,'provider':name()[:80]})
    return {r.chunk_id:float(r.similarity) for r in rows}
