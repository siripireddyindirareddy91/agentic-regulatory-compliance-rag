"""Durable queues, monitoring state, scheduled reports and refresh sessions."""
from alembic import op
from backend.app.models import Job,MonitorState,GeneratedReport,RefreshSession
revision='003'
down_revision='002'
branch_labels=None
depends_on=None
def upgrade():
    for model in [Job,MonitorState,GeneratedReport,RefreshSession]:model.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():
    for model in [GeneratedReport,MonitorState,Job,RefreshSession]:model.__table__.drop(op.get_bind(),checkfirst=True)
