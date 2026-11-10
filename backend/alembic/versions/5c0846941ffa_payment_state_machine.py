"""payment state machine

Adds PayPal tracking to payments and renames the "proposed" order status to "awaiting_approval".

Revision ID: 5c0846941ffa
Revises: 23eeef96301d
Create Date: 2026-11-10 15:53:02.534508
"""
from alembic import op
import sqlalchemy as sa


revision = '5c0846941ffa'
down_revision = '23eeef96301d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Server defaults so existing rows (if any) get valid values.
    op.add_column('payments', sa.Column('request_id', sa.String(length=80), nullable=False, server_default=sa.text("gen_random_uuid()::text")))
    op.alter_column('payments', 'request_id', server_default=None)
    op.add_column('payments', sa.Column('paypal_status', sa.String(length=32), nullable=True))
    op.add_column('payments', sa.Column('capture_status', sa.String(length=32), nullable=True))
    op.add_column('payments', sa.Column('failure_reason', sa.Text(), nullable=False, server_default=""))
    op.alter_column('payments', 'failure_reason', server_default=None)
    op.add_column('payments', sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('uq_payments_request_id', 'payments', ['request_id'])
    op.add_column('payments', sa.Column('attempt', sa.Integer(), nullable=False, server_default="1"))
    op.alter_column('payments', 'attempt', server_default=None)
    op.create_unique_constraint('uq_payments_order_attempt', 'payments', ['order_id', 'attempt'])
    op.execute("UPDATE orders SET status = 'awaiting_approval' WHERE status = 'proposed'")


def downgrade() -> None:
    op.execute("UPDATE orders SET status = 'proposed' WHERE status = 'awaiting_approval'")
    op.drop_constraint('uq_payments_order_attempt', 'payments', type_='unique')
    op.drop_column('payments', 'attempt')
    op.drop_constraint('uq_payments_request_id', 'payments', type_='unique')
    op.drop_column('payments', 'verified_at')
    op.drop_column('payments', 'failure_reason')
    op.drop_column('payments', 'capture_status')
    op.drop_column('payments', 'paypal_status')
    op.drop_column('payments', 'request_id')
