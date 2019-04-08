import functools
import os
from collections import defaultdict

from rtree import index
from shapely import geometry
from shapely.ops import cascaded_union

import solardb
from process_city_shapes import num2deg

GEOJSON_STRING = \
    '{{"type": "FeatureCollection", "features": [{{"type": "Feature", "properties": {{"prediction_confidence": ' \
    '{confidence}}}, "geometry": {{"type": "Polygon", "coordinates": [{points}]}}}}]}}\n'


def create_simple_maproulette_geojson(threshold=0.25, polygon_name=None):
    tiles = solardb.query_tiles_over_threshold(threshold=threshold, polygon_name=polygon_name)
    with open(os.path.join("data", (polygon_name or "") + "maproulette.geojson"), "w") as the_file:
        for tile in tiles:
            bounding_polygon_slippy_coordinates = [
                (tile.column, tile.row),
                (tile.column + 1, tile.row),
                (tile.column + 1, tile.row + 1),
                (tile.column, tile.row + 1),
                (tile.column, tile.row)
            ]
            bounding_polygon_lon_lat_coordinates = \
                map(functools.partial(num2deg, center=False), bounding_polygon_slippy_coordinates)

            points = str([list(coordinates) for coordinates in bounding_polygon_lon_lat_coordinates])
            confidence = tile.panel_softmax
            the_file.write(GEOJSON_STRING.format(points=points, confidence=confidence))


def get_clustered_positive_polygon_dicts(threshold=0.25, polygon_name=None):
    tiles = solardb.query_tiles_over_threshold(threshold=threshold, polygon_name=polygon_name)
    cluster_to_tile_map = defaultdict(list)
    for tile in tiles:
        cluster_to_tile_map[tile.cluster_id].append(tile)
    polygon_dicts = []
    for cluster_id, tiles in cluster_to_tile_map.items():
        bounding_polygons_slippy_coordinates = []
        for tile in tiles:
            bounding_polygon_slippy_coordinates = [
                (tile.column, tile.row),
                (tile.column + 1, tile.row),
                (tile.column + 1, tile.row + 1),
                (tile.column, tile.row + 1),
                (tile.column, tile.row)
            ]
            bounding_polygons_slippy_coordinates.append(
                geometry.Polygon([[p[0], p[1]] for p in bounding_polygon_slippy_coordinates]))
        unioned_slippy_coordinate_polygon = cascaded_union(bounding_polygons_slippy_coordinates)
        slippy_coordinate_bounding_polygon_coordinates = \
            zip(*unioned_slippy_coordinate_polygon.exterior.xy)
        bounding_polygon_lon_lat_coordinates = \
            list(map(functools.partial(num2deg, center=False), slippy_coordinate_bounding_polygon_coordinates))
        string_points = str([list(coordinates) for coordinates in bounding_polygon_lon_lat_coordinates])
        confidence = max(tile.panel_softmax for tile in tiles)
        polygon_dicts.append({
            "bounding_polygon_lon_lat_coordinates": bounding_polygon_lon_lat_coordinates,
            "string_points": string_points,
            "confidence": confidence
        })
    return polygon_dicts


def filter_polygon_dicts_based_off_osm_panels(polygon_dicts):
    panel_nodes = solardb.get_osm_pv_nodes()
    polygon_dict_map = {}
    for i, polygon_dict in enumerate(polygon_dicts):
        polygon_dict_map[i] = polygon_dict
    polygon_enumeration = []
    for i, polygon_dict in polygon_dict_map.items():
        polygon_enumeration.append((i, geometry.Polygon(polygon_dict["bounding_polygon_lon_lat_coordinates"])))
    spatial_index = index.Index(polygon_rtree_generator(polygon_enumeration))
    for node_lon_lat_tuple in panel_nodes:
        for intersecting_item in spatial_index.intersection(node_lon_lat_tuple + node_lon_lat_tuple, objects=True):
            if intersecting_item.object.contains(geometry.Point(node_lon_lat_tuple)):
                spatial_index.delete(intersecting_item.id, intersecting_item.bounds)
                polygon_dict_map.pop(intersecting_item.id, None)
    return polygon_dict_map.values()


def polygon_rtree_generator(polygon_enumeration):
    for i, polygon in polygon_enumeration:
        yield (i, polygon.bounds, polygon)


def create_clustered_maproulette_geojson(threshold=0.25, polygon_name=None, filter_existing_osm_panels=True):
    polygon_dicts = get_clustered_positive_polygon_dicts(threshold=threshold, polygon_name=polygon_name)
    if filter_existing_osm_panels:
        polygon_dicts = filter_polygon_dicts_based_off_osm_panels(polygon_dicts)
    with open(os.path.join("data", (polygon_name or "") + "maproulette.geojson"), "w") as the_file:
        for polygon_dict in polygon_dicts:
            the_file.write(GEOJSON_STRING.format(points=polygon_dict["string_points"],
                                                 confidence=polygon_dict["confidence"]))


if __name__ == "__main__":
    create_clustered_maproulette_geojson()
