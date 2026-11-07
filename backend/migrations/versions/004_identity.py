"""Embedding profiles, access grants and user-specific notification delivery."""
from alembic import op
from backend.app.models import EmbeddingProfile,AccessGrant,NotificationDelivery
revision='004'
down_revision='003'
branch_labels=None
depends_on=None
def upgrade():
    for model in [EmbeddingProfile,AccessGrant,NotificationDelivery]:model.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():
    for model in [NotificationDelivery,AccessGrant,EmbeddingProfile]:model.__table__.drop(op.get_bind(),checkfirst=True)
