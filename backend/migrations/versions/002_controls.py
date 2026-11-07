"""Policy mappings, durable evidence, and native pgvector indexes."""
from alembic import op
from backend.app.models import PolicyMapping, Attachment, OriginalFile
revision='002'
down_revision='001'
branch_labels=None
depends_on=None
def upgrade():
    PolicyMapping.__table__.create(op.get_bind(),checkfirst=True)
    Attachment.__table__.create(op.get_bind(),checkfirst=True)
    OriginalFile.__table__.create(op.get_bind(),checkfirst=True)
    from backend.app.vectors import initialize
    initialize(op.get_bind())
def downgrade():
    OriginalFile.__table__.drop(op.get_bind(),checkfirst=True)
    Attachment.__table__.drop(op.get_bind(),checkfirst=True)
    PolicyMapping.__table__.drop(op.get_bind(),checkfirst=True)
