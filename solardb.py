import math
import time

from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, PrimaryKeyConstraint
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

from sqlalchemy.sql import expression

Base = declarative_base()
# TODO improve session management


class SearchPolygon(Base):
    __tablename__ = 'search_polygons'

    name = Column(String, primary_key=True)
    centroid_row = Column(Float, nullable=False)
    centroid_column = Column(Float, nullable=False)
    centroid_zoom = Column(Integer, nullable=False)
    inner_coords_calculated = Column(Boolean, nullable=False, server_default=expression.false())


class SlippyTile(Base):
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


engine = create_engine('sqlite:///data/solar.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def persist_polygons(names_and_polygons, zoom=21):
    session = Session()
    for name, polygon in names_and_polygons:
        exists = session.query(SearchPolygon).filter(SearchPolygon.name == name).first()
        if not exists:
            session.add(SearchPolygon(name=name, centroid_row=polygon.centroid.x, centroid_column=polygon.centroid.y,
                                      centroid_zoom=zoom))
    session.commit()
    session.close()


def persist_coords(polygon_name, coords, zoom=21, batch_size=100000):
    start_time = time.time()
    session = Session()
    tiles_to_add = []
    for coord in coords:
        if len(tiles_to_add) >= batch_size:
            session.add_all(tiles_to_add)
            session.commit()
            tiles_to_add = []
        tiles_to_add.append(SlippyTile(polygon_name=polygon_name, column=coord[0], row=coord[1], zoom=zoom))
    session.add_all(tiles_to_add)
    session.query(SearchPolygon).filter(SearchPolygon.name == polygon_name).first().inner_coords_calculated = True
    session.commit()
    session.close()
    print(str(time.time() - start_time) + " seconds to complete inner grid persistence for " + polygon_name)


def get_finished_polygon_names():
    session = Session()
    names = session.query(SearchPolygon.name).filter(SearchPolygon.inner_coords_calculated.is_(True))
    session.close()
    return names


def polygon_has_inner_grid(name):
    session = Session()
    inner_grid = session.query(SearchPolygon.inner_coords_calculated).filter(SearchPolygon.name == name).first()[0]
    session.close()
    return inner_grid


def compute_centroids(batch_size=10000):
    session = Session()
    while True:
        uncomputed_centroid_tiles = session.query(SlippyTile).filter(
            SlippyTile.centroid_distance.is_(None)).limit(batch_size).all()
        if not uncomputed_centroid_tiles:
            break
        for tile in uncomputed_centroid_tiles:
            tile.centroid_distance = math.sqrt(
                math.pow(tile.polygon.centroid_row - tile.row, 2) + math.pow(tile.polygon.centroid_column - tile.column,
                                                                             2))
        session.commit()
    session.close()


# marks existing slippy tiles as having imagery in the db, and if the tiles don't exist it creates them (for cases where
# the imagery gathered goes outside the planned polygon bounds, still need to track it, and maybe use it)
def mark_has_imagery(base_coord, grid_size, zoom=21):
    session = Session()
    # get and update the tiles in this grid that exist
    tile_query = session.query(SlippyTile).filter(SlippyTile.zoom == zoom).filter(SlippyTile.column.between(
        base_coord[0], base_coord[0] + grid_size - 1)).filter(SlippyTile.row.between(base_coord[1], base_coord[1] +
                                                                                     grid_size - 1))
    tile_query.update({SlippyTile.has_image: True}, synchronize_session='fetch')
    tiles = tile_query.all()
    # get the first tile's parent polygon if they have one
    polygon_name = next(iter(tiles or []), None).polygon_name

    # create a meshgrid of points in this grid
    coords = {}
    for column in range(base_coord[0], base_coord[0] + 20):
        for row in range(base_coord[1], base_coord[1] + 20):
            coords[(column, row)] = True
    # remove the tiles that we already know exist
    for tile in tiles:
        coords.pop((tile.column, tile.row), None)
    tiles_to_add = []
    # create new tile objects for the remaining points in the meshgrid and add them to the db
    for coord in coords.keys():
        tiles_to_add.append(SlippyTile(column=coord[0], row=coord[1], zoom=zoom, polygon_name=polygon_name,
                                       has_image=True))
    session.add_all(tiles_to_add)
    session.commit()
    session.close()
