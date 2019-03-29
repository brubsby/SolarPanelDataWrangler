"""add columns and ON CONFLICT primary key

Wasn't able to get this migrate working in sqlite due to altering a primary key,
just did the migrate by hand via this method: https://stackoverflow.com/a/14353595/3586848
I've left my notes/attempt here commented out just in case someone wants to try and do it

Revision ID: a8825815024c
Revises:
Create Date: 2019-03-25 15:45:05.011747

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, PrimaryKeyConstraint, orm

# revision identifiers, used by Alembic.
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression

revision = 'a8825815024c'
down_revision = None
branch_labels = None
depends_on = None

Base1 = declarative_base()
Base2 = declarative_base()


class SlippyTileOld(Base1):
    __tablename__ = 'slippy_tiles'

    row = Column(Integer, nullable=False, primary_key=True)
    column = Column(Integer, nullable=False, primary_key=True)
    zoom = Column(Integer, nullable=False, primary_key=True)
    centroid_distance = Column(Float)
    polygon_name = Column(String, ForeignKey('search_polygons.name'))
    polygon = relationship("SearchPolygon")
    has_image = Column(Boolean, nullable=False, server_default=expression.false())
    inference_ran = Column(Boolean, nullable=False, server_default=expression.false())
    inference_timestamp = Column(Integer, nullable=True)  # UNIX EPOCH


class SlippyTileNew(Base2):
    __tablename__ = 'slippy_tiles'

    row = Column(Integer, nullable=False)
    column = Column(Integer, nullable=False)
    zoom = Column(Integer, nullable=False)
    centroid_distance = Column(Float)
    polygon_name = Column(String, ForeignKey('search_polygons.name'))
    polygon = relationship("SearchPolygon")
    has_image = Column(Boolean, nullable=False, server_default=expression.false())
    inference_ran = Column(Boolean, nullable=False, server_default=expression.false())
    inference_timestamp = Column(Integer, nullable=True)  # UNIX EPOCH
    panel_softmax = Column(Float, nullable=True)
    panel_seen_by_human = Column(Boolean, nullable=True, server_default=expression.false())
    panel_verified = Column(Boolean, nullable=True, server_default=expression.false())

    __table_args__ = (
        PrimaryKeyConstraint(row, column, zoom, sqlite_on_conflict='IGNORE'),
    )


def upgrade():
    pass
    # bind = op.get_bind()
    # session = orm.Session(bind=bind)
    # old_tiles = session.query(SlippyTileOld).all()
    #
    # SlippyTileOld.__table__.drop(bind)
    # session.commit()
    #
    # SlippyTileNew.__table__.create(bind)
    # new_tiles = [SlippyTileNew(old_tile) for old_tile in old_tiles]
    # session.add_all(new_tiles)
    # session.commit()
    # session.close()


def downgrade():
    pass
    # bind = op.get_bind()
    # session = orm.Session(bind=bind)
    # old_tiles = session.query(SlippyTileNew).all()
    #
    # SlippyTileNew.__table__.drop(bind)
    # session.commit()
    #
    # SlippyTileOld.__table__.create(bind)
    # old_tiles = [SlippyTileNew(new_tile) for new_tile in old_tiles]
    # session.add_all(old_tiles)
