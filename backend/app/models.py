"""Tenant-scoped relational records; no application routes update audit rows."""
import os, uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Text, Float, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc).isoformat()
URL = os.getenv('DATABASE_URL') or ('sqlite:////tmp/complyintel.db' if os.getenv('VERCEL') else 'sqlite:///./compliance.db')
if URL.startswith('postgres://'): URL = URL.replace('postgres://', 'postgresql+psycopg://', 1)
elif URL.startswith('postgresql://'): URL = URL.replace('postgresql://', 'postgresql+psycopg://', 1)
from sqlalchemy.pool import NullPool
engine = create_engine(URL, connect_args={'check_same_thread': False} if URL.startswith('sqlite') else {'connect_timeout':15}, pool_pre_ping=True, **({'poolclass':NullPool} if os.getenv('VERCEL') else {}))
Session = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(String(36), index=True, default='demo-bank')
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, onupdate=now)
class User(Record, Base):
    __tablename__ = 'users'
    email: Mapped[str] = mapped_column(String(240), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30), default='viewer')
class Document(Record, Base):
    __tablename__ = 'regulatory_documents'
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(30), default='regulation')
    authority: Mapped[str] = mapped_column(String(80), default='Internal')
    jurisdiction: Mapped[str] = mapped_column(String(80), default='India')
    category: Mapped[str] = mapped_column(String(80), default='General')
    department: Mapped[str] = mapped_column(String(100), default='Legal and Compliance')
    text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(default=1)
    previous_id: Mapped[str | None] = mapped_column(ForeignKey('regulatory_documents.id'), nullable=True)
    source_url: Mapped[str] = mapped_column(Text, default='')
    identifier: Mapped[str] = mapped_column(String(120), default='')
    publication_date: Mapped[str] = mapped_column(String(30), default='')
    effective_date: Mapped[str] = mapped_column(String(30), default='')
    verification: Mapped[str] = mapped_column(String(40), default='Unverified upload')
    status: Mapped[str] = mapped_column(String(40), default='Indexed')
    demo: Mapped[bool] = mapped_column(default=False)
class Chunk(Record, Base):
    __tablename__ = 'document_chunks'
    document_id: Mapped[str] = mapped_column(ForeignKey('regulatory_documents.id'), index=True)
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int] = mapped_column(default=1)
    section: Mapped[str] = mapped_column(String(200), default='Extracted text')
    vector: Mapped[list] = mapped_column(JSON, default=list)
class Requirement(Record, Base):
    __tablename__ = 'regulatory_requirements'
    document_id: Mapped[str] = mapped_column(ForeignKey('regulatory_documents.id'), index=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey('document_chunks.id'))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    department: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Float, default=0.65)
    effective_date: Mapped[str] = mapped_column(String(30), default='')
class Finding(Record, Base):
    __tablename__ = 'compliance_findings'
    requirement_id: Mapped[str] = mapped_column(ForeignKey('regulatory_requirements.id'))
    workflow_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    department: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(60), default='Requires human verification')
    risk_score: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(20))
    factors: Mapped[dict] = mapped_column(JSON)
    evidence: Mapped[list] = mapped_column(JSON)
    policy_evidence: Mapped[list] = mapped_column(JSON)
    recommendation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    review_status: Mapped[str] = mapped_column(String(40), default='Pending')
    owner: Mapped[str] = mapped_column(String(100), default='Compliance team')
class Workflow(Record, Base):
    __tablename__ = 'workflow_runs'
    document_id: Mapped[str] = mapped_column(ForeignKey('regulatory_documents.id'))
    status: Mapped[str] = mapped_column(String(40), default='Running')
    stage: Mapped[str] = mapped_column(String(80), default='Ingestion')
    steps: Mapped[list] = mapped_column(JSON, default=list)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    errors: Mapped[list] = mapped_column(JSON, default=list)
class Review(Record, Base):
    __tablename__ = 'human_reviews'
    finding_id: Mapped[str] = mapped_column(ForeignKey('compliance_findings.id'), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    decision: Mapped[str] = mapped_column(String(50))
    comment: Mapped[str] = mapped_column(Text)
    previous_status: Mapped[str] = mapped_column(String(50))
class Action(Record, Base):
    __tablename__ = 'corrective_actions'
    finding_id: Mapped[str] = mapped_column(ForeignKey('compliance_findings.id'))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default='')
    owner: Mapped[str] = mapped_column(String(100))
    priority: Mapped[str] = mapped_column(String(20))
    due_date: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(40), default='Open')
    progress: Mapped[int] = mapped_column(default=0)
    evidence: Mapped[str] = mapped_column(Text, default='')
class Audit(Record, Base):
    __tablename__ = 'audit_logs'
    actor: Mapped[str] = mapped_column(String(160))
    event: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON)
    previous_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    sequence: Mapped[int] = mapped_column(index=True)
    __table_args__ = (UniqueConstraint('institution_id', 'sequence'),)
class Setting(Record, Base):
    __tablename__ = 'system_settings'
    key: Mapped[str] = mapped_column(String(80))
    value: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint('institution_id', 'key'),)
class Source(Record, Base):
    __tablename__ = 'regulatory_sources'
    name: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(Text)
    jurisdiction: Mapped[str] = mapped_column(String(80))
    enabled: Mapped[bool] = mapped_column(default=False)
class Notification(Record, Base):
    __tablename__ = 'notifications'
    title: Mapped[str] = mapped_column(String(300))
    read: Mapped[bool] = mapped_column(default=False)
class PolicyMapping(Record, Base):
    __tablename__ = 'policy_requirement_mappings'
    policy_id: Mapped[str] = mapped_column(ForeignKey('regulatory_documents.id'), index=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey('regulatory_requirements.id'), index=True)
    notes: Mapped[str] = mapped_column(Text, default='')
    mapped_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    __table_args__ = (UniqueConstraint('policy_id','requirement_id'),)
class Attachment(Record, Base):
    __tablename__ = 'corrective_action_evidence'
    action_id: Mapped[str] = mapped_column(ForeignKey('corrective_actions.id'), index=True)
    filename: Mapped[str] = mapped_column(String(240))
    content_type: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
