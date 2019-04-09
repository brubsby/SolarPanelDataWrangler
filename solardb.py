
import time

import math
import overpy
from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, PrimaryKeyConstraint, Index, desc
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


class PositiveCluster(Base):
    __tablename__ = 'positive_clusters'

    id = Column(Integer, primary_key=True)


class SlippyTile(Base):
    __tablename__ = 'slippy_tiles'

    row = Column(Integer, nullable=False)
    column = Column(Integer, nullable=False)
    zoom = Column(Integer, nullable=False)
    centroid_distance = Column(Float)
    polygon_name = Column(String, ForeignKey(SearchPolygon.name), nullable=True)
    polygon = relationship("SearchPolygon")
    cluster_id = Column(String, ForeignKey(PositiveCluster.id), nullable=True)
    cluster = relationship("PositiveCluster")
    has_image = Column(Boolean, nullable=False, server_default=expression.false())
    inference_ran = Column(Boolean, nullable=False, server_default=expression.false())
    inference_timestamp = Column(Integer, nullable=True)  # UNIX EPOCH
    panel_softmax = Column(Float, nullable=True)
    panel_seen_by_human = Column(Boolean, nullable=True, server_default=expression.false())
    panel_verified = Column(Boolean, nullable=True, server_default=expression.false())

    __table_args__ = (
        PrimaryKeyConstraint(row, column, zoom, sqlite_on_conflict='IGNORE'),
        Index('centroid_index', polygon_name, centroid_distance)
    )


class OSMSolarNode(Base):
    __tablename__ = 'osm_solar_nodes'

    longitude = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(longitude, latitude, sqlite_on_conflict='IGNORE'),
    )


engine = create_engine('sqlite:///data/solar.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def persist_polygons(names_and_polygons, zoom=21):
    session = Session()
    for name, polygon in names_and_polygons:
        exists = session.query(SearchPolygon).filter(SearchPolygon.name == name).first()
        if not exists:
            session.add(SearchPolygon(name=name, centroid_column=polygon.centroid.x, centroid_row=polygon.centroid.y,
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


def get_polygon_names():
    session = Session()
    polygons = session.query(SearchPolygon).all()
    session.close()
    return [polygon.name for polygon in polygons]


def get_inner_coords_calculated_polygon_names():
    session = Session()
    polygons = session.query(SearchPolygon).filter(SearchPolygon.inner_coords_calculated.is_(True)).all()
    session.close()
    return [polygon.name for polygon in polygons]


def polygon_has_inner_grid(name):
    session = Session()
    inner_grid = session.query(SearchPolygon.inner_coords_calculated).filter(SearchPolygon.name == name).first()[0]
    session.close()
    return inner_grid


def compute_centroid_distances(batch_size=10000):
    session = Session()
    while True:
        uncomputed_centroid_tiles = session.query(SlippyTile).filter(SlippyTile.centroid_distance.is_(None),
                                                                     SlippyTile.polygon_name.isnot(None)
                                                                     ).limit(batch_size).all()
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
        tiles_to_add.append(SlippyTile(column=coord[0], row=coord[1], zoom=zoom, has_image=True))
    session.add_all(tiles_to_add)
    session.commit()
    session.close()


# decimal places to round is so nodes with close lat/lon are only counted as one point,
# degree precision versus length chart: https://en.wikipedia.org/wiki/Decimal_degrees#Precision
def query_osm_solar(polygons, decimal_places_to_round=5):
    api = overpy.Overpass()
    solar_node_lon_lats = set()
    for polygon in polygons:
        # little bit of python magic to massage the polygon into a space separated list of coordinates
        polygon_coords_string = " ".join([" ".join(map(str, coord)) for coord in zip(*reversed(polygon.boundary.xy))])
        # I've read that querying within a polygon is a lot slower than querying within a bounding box, so if this
        # ends up being too slow, feel free to just replace with the bounding box of the polygon
        query_string = \
            """
            [out:json][timeout:2500];
            (
            node["generator:source"="solar"](poly:"{poly}");
            way["generator:source"="solar"](poly:"{poly}");
            relation["generator:source"="solar"](poly:"{poly}");
            );
            out body;
            >;
            out skel qt;
            """.format(poly=polygon_coords_string)
        result = api.query(query_string)
        for node in result.nodes:
            solar_node_lon_lats.add(
                (round(node.lon, decimal_places_to_round), round(node.lat, decimal_places_to_round)))
    return solar_node_lon_lats


def query_and_persist_osm_solar(polygons):
    session = Session()
    solar_node_lon_lats = query_osm_solar(polygons)
    solar_nodes = []
    for lon, lat in solar_node_lon_lats:
        solar_nodes.append(OSMSolarNode(longitude=lon, latitude=lat))
    session.add_all(solar_nodes)
    session.commit()
    session.close()


def query_tile_batch(batch_size=1000000, polygon_name=None):
    session = Session()
    tile_query = session.query(SlippyTile).filter(SlippyTile.has_image.is_(True), SlippyTile.inference_ran.is_(True))
    if polygon_name:
        tile_query = tile_query.filter(SlippyTile.polygon_name == polygon_name)
    tiles = tile_query.limit(batch_size).all()
    session.close()
    return tiles


def query_tile_batch_for_inference(batch_size=400):
    session = Session()
    tiles = \
        session.query(SlippyTile).filter(SlippyTile.centroid_distance.isnot(None), SlippyTile.inference_ran.is_(False))\
            .order_by(SlippyTile.polygon_name, SlippyTile.centroid_distance).limit(batch_size).all()
    session.close()
    return tiles


def update_tiles(tiles):
    session = Session()
    session.add_all(tiles)
    session.commit()
    session.close()


def query_tiles_over_threshold(threshold=0.25, polygon_name=None, filter_clustered=False):
    session = Session()
    coordinate_query = session.query(SlippyTile).filter(SlippyTile.panel_softmax.isnot(None),
                                                        SlippyTile.panel_softmax >= threshold).order_by(
        desc(SlippyTile.panel_softmax))
    if polygon_name:
        coordinate_query = coordinate_query.filter(SlippyTile.polygon_name == polygon_name)
    if filter_clustered:
        coordinate_query = coordinate_query.filter(SlippyTile.cluster_id.is_(None))
    coordinates = coordinate_query.all()
    session.close()
    return coordinates


def get_new_positive_cluster_id():
    session = Session()
    positive_cluster = PositiveCluster()
    session.add(positive_cluster)
    session.commit()
    positive_cluster_id = positive_cluster.id
    session.close()
    return positive_cluster_id


def get_osm_pv_nodes():
    session = Session()
    nodes = session.query(OSMSolarNode).all()
    session.close()
    return [(node.longitude, node.latitude) for node in nodes]
