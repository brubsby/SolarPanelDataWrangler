import functools
import os
from collections import defaultdict

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
            bounding_polygon_lat_lon_coordinates = \
                map(functools.partial(num2deg, center=False), bounding_polygon_slippy_coordinates)

            points = str([list(coordinates) for coordinates in bounding_polygon_lat_lon_coordinates])
            confidence = tile.panel_softmax
            the_file.write(GEOJSON_STRING.format(points=points, confidence=confidence))


def create_clustered_maproulette_geojson(threshold=0.25, polygon_name=None):
    tiles = solardb.query_tiles_over_threshold(threshold=threshold, polygon_name=polygon_name)
    cluster_to_tile_map = defaultdict(list)
    for tile in tiles:
        cluster_to_tile_map[tile.cluster_id].append(tile)
    with open(os.path.join("data", (polygon_name or "") + "maproulette.geojson"), "w") as the_file:
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
            bounding_polygon_lat_lon_coordinates = \
                map(functools.partial(num2deg, center=False), slippy_coordinate_bounding_polygon_coordinates)
            points = str([list(coordinates) for coordinates in bounding_polygon_lat_lon_coordinates])
            confidence = max(tile.panel_softmax for tile in tiles)
            the_file.write(GEOJSON_STRING.format(points=points, confidence=confidence))


if __name__ == "__main__":
    create_clustered_maproulette_geojson()
