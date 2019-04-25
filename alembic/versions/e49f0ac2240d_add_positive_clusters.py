"""add positive clusters

Revision ID: e49f0ac2240d
Revises: d9ccb1fc3ced
Create Date: 2019-04-06 21:13:17.289431

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e49f0ac2240d'
down_revision = 'd9ccb1fc3ced'
branch_labels = None
depends_on = None


naming_convention = {
    "fk":
    "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('slippy_tiles', naming_convention=naming_convention, schema=None) as batch_op:
        batch_op.add_column(sa.Column('cluster_id', sa.String(), nullable=True))
        batch_op.create_foreign_key('fk_slippy_tiles_cluster_id_positive_clusters', 'positive_clusters', ['cluster_id'],
                                    ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('slippy_tiles', naming_convention=naming_convention, schema=None) as batch_op:
        batch_op.drop_constraint('fk_slippy_tiles_cluster_id_positive_clusters', type_='foreignkey')
        batch_op.drop_column('cluster_id')

    # ### end Alembic commands ###
