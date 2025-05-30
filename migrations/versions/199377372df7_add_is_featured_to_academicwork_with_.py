"""Add is_featured to AcademicWork with server default

Revision ID: 199377372df7
Revises: 2aa72b6966ca
Create Date: 2025-04-19 16:02:15.892290

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '199377372df7'
down_revision = '2aa72b6966ca'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('academic_work', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_featured', sa.Boolean(), server_default='0', nullable=False))
        batch_op.create_index(batch_op.f('ix_academic_work_is_featured'), ['is_featured'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('academic_work', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_academic_work_is_featured'))
        batch_op.drop_column('is_featured')

    # ### end Alembic commands ###
