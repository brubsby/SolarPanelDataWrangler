import functools
import os

import solardb
from process_city_shapes import num2deg

GEOJSON_STRING = \
    '{{"type": "FeatureCollection", "features": [{{"type": "Feature", "properties": {{"prediction_confidence": ' \
    '{confidence}}}, "geometry": {{"type": "Polygon", "coordinates": [{points}]}}}}]}}\n'


def create_maproulette_geojson(threshold=0.25, polygon_name=None):
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


if __name__ == "__main__":
    create_maproulette_geojson()
