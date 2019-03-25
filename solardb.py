import math
import time

from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

from sqlalchemy.sql import expression

Base = declarative_base()


class SearchPolygon(Base):
    __tablename__ = 'search_polygons'

    name = Column(String, primary_key=True)
    centroid_row = Column(Float, nullable=False)
    centroid_column = Column(Float, nullable=False)
    centroid_zoom = Column(Integer, nullable=False)
    inner_coords_calculated = Column(Boolean, nullable=False, server_default=expression.false())


class SlippyTile(Base):
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


engine = create_engine('sqlite:///data/solar.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def persist_polygons(names_and_polygons, zoom=20):
    session = Session()
    for name, polygon in names_and_polygons:
        exists = session.query(SearchPolygon).filter(SearchPolygon.name == name).first()
        if not exists:
            session.add(SearchPolygon(name=name, centroid_row=polygon.centroid.x, centroid_column=polygon.centroid.y,
                                      centroid_zoom=zoom))
    session.commit()
    session.close()


def persist_coords(polygon_name, coords, zoom=20):
    start_time = time.time()
    session = Session()
    tiles_to_add = []
    for coord in coords:
        tile_to_add = SlippyTile(polygon_name=polygon_name, row=coord[0], column=coord[1], zoom=zoom)
        exists = session.query(SlippyTile).filter(SlippyTile.zoom == tile_to_add.zoom).filter(
            SlippyTile.row == tile_to_add.row).filter(SlippyTile.column == tile_to_add.column).first()
        if not exists:
            tiles_to_add.append(tile_to_add)
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
            tile.centroid_distance = math.sqrt(math.pow(tile.polygon.centroid_row - tile.row, 2) + math.pow(tile.polygon.centroid_column - tile.column, 2))
        session.commit()
    session.close()
