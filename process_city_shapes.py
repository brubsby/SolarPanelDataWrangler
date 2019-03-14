import argparse
import json
import math
import os

import geojson
import numpy as np
from shapely.geometry import shape, mapping, GeometryCollection

from gather_city_shapes import get_city_state_filepaths


# function to convert lat lon to slippy tiles
def deg2num(arr, zoom=20):
    lat_deg = arr[1]
    lon_deg = arr[0]
    lat_rad = np.math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return xtile, ytile


# function to convert slippy tiles to lat lon
def num2deg(arr, zoom=20):
    xtile = arr[1]
    ytile = arr[0]
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg


def get_polygons(csv):
    for _, _, filepath in get_city_state_filepaths(csv):
        with open(filepath, 'r') as infile:
            yield json.load(infile)


# For decreased computational complexity I run some simplification of the polygons gathered before putting them all
# together into one collection, because these shapes are just a starting point and pretty arbitrary
def make_megagon(csv):
    return GeometryCollection([shape(polygon).convex_hull.simplify(0.001).buffer(0.004) for polygon in get_polygons(csv)])


def convert_to_slippy_tile_coords(polygons, zoom=20):
    converted_polygons = []
    for polygon in polygons:
        geojson = mapping(polygon)
        geojson['coordinates'] = np.apply_along_axis(deg2num, 2, np.array(geojson['coordinates']), zoom=zoom)
        converted_polygons.append(shape(geojson))
    return converted_polygons


def save_geojson(filename, feature):
    with open(os.path.join('data', filename), 'w') as outfile:
        geojson.dump(geojson.Feature(geometry=feature, properties={}), outfile)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process shapes of city polygons')
    parser.add_argument('--input_csv', dest='csv', default=os.path.join('data', '100k_US_cities.csv'),
                        help='specify the csv list of city and state names to gather geoJSON for')
    parser.add_argument('--megagon', dest='megagon', action='store_const',
                        const=True, default=False,
                        help='Create the megagon (all of the city polygons combined) and save it')
    parser.add_argument('--calculate_area', dest='area', action='store_const',
                        const=True, default=False,
                        help='Calculates the area of all polygons in km2')
    args = parser.parse_args()

    if args.megagon:
        megagon = make_megagon(args.csv)
        save_geojson('megagon.geojson', megagon)
    if args.area:
        projected_polygons = convert_to_slippy_tile_coords(list(make_megagon(args.csv)), zoom=20)
        print(str(math.ceil(sum([polygon.area for polygon in projected_polygons])))
              + " total API calls to cover this polygon area!")
