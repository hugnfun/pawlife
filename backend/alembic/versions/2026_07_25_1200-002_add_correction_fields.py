"""add correction fields to log tables

Revision ID: 002
Revises: 001
Create Date: 2026-07-25 12:00:00.000000

为 meal_logs / activity_logs / weight_logs 三张表添加纠错追踪字段：
- corrected_from_id: 指向被纠正的原始记录ID
- correction_reason: 纠正原因摘要
- is_corrected: 是否为纠正版本

需求来源：requirements-v1.1.md §3 数据纠错闭环
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # meal_logs
    op.add_column('meal_logs', sa.Column('corrected_from_id', postgresql.UUID(as_uuid=True), nullable=True, comment='指向被纠正的原始记录ID'))
    op.add_column('meal_logs', sa.Column('correction_reason', sa.Text(), nullable=True, comment='纠正原因摘要'))
    op.add_column('meal_logs', sa.Column('is_corrected', sa.Boolean(), server_default=sa.text('false'), nullable=False, comment='是否为纠正版本'))

    # activity_logs
    op.add_column('activity_logs', sa.Column('corrected_from_id', postgresql.UUID(as_uuid=True), nullable=True, comment='指向被纠正的原始记录ID'))
    op.add_column('activity_logs', sa.Column('correction_reason', sa.Text(), nullable=True, comment='纠正原因摘要'))
    op.add_column('activity_logs', sa.Column('is_corrected', sa.Boolean(), server_default=sa.text('false'), nullable=False, comment='是否为纠正版本'))

    # weight_logs
    op.add_column('weight_logs', sa.Column('corrected_from_id', postgresql.UUID(as_uuid=True), nullable=True, comment='指向被纠正的原始记录ID'))
    op.add_column('weight_logs', sa.Column('correction_reason', sa.Text(), nullable=True, comment='纠正原因摘要'))
    op.add_column('weight_logs', sa.Column('is_corrected', sa.Boolean(), server_default=sa.text('false'), nullable=False, comment='是否为纠正版本'))

    # 索引：加速「查找某宠物的纠正版本」查询
    op.create_index('ix_meal_logs_corrected_from_id', 'meal_logs', ['corrected_from_id'])
    op.create_index('ix_activity_logs_corrected_from_id', 'activity_logs', ['corrected_from_id'])
    op.create_index('ix_weight_logs_corrected_from_id', 'weight_logs', ['corrected_from_id'])


def downgrade() -> None:
    op.drop_index('ix_weight_logs_corrected_from_id', table_name='weight_logs')
    op.drop_index('ix_activity_logs_corrected_from_id', table_name='activity_logs')
    op.drop_index('ix_meal_logs_corrected_from_id', table_name='meal_logs')

    op.drop_column('weight_logs', 'is_corrected')
    op.drop_column('weight_logs', 'correction_reason')
    op.drop_column('weight_logs', 'corrected_from_id')

    op.drop_column('activity_logs', 'is_corrected')
    op.drop_column('activity_logs', 'correction_reason')
    op.drop_column('activity_logs', 'corrected_from_id')

    op.drop_column('meal_logs', 'is_corrected')
    op.drop_column('meal_logs', 'correction_reason')
    op.drop_column('meal_logs', 'corrected_from_id')
