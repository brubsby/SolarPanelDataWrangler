import argparse
import json
import math
import os
import sys
import time

import geojson
import geojsonio as geojsonio
import geopandas
import numpy as np
from shapely.geometry import shape, mapping, GeometryCollection, Point

from gather_city_shapes import get_city_state_filepaths, get_city_state_tuples


# function to convert lat lon to slippy tiles
def deg2num(arr, zoom=21):
    lon_deg = arr[0]
    lat_deg = arr[1]
    lat_rad = np.math.radians(lat_deg)
    n = 2.0 ** zoom
    column = int((lon_deg + 180.0) / 360.0 * n)
    row = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return column, row


# function to convert slippy tiles to lat lon
def num2deg(arr, zoom=21, center=True):
    column = arr[0]
    row = arr[1]
    if center:
        column += 0.5
        row += 0.5
    n = 2.0 ** zoom
    lon_deg = column / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * row / n)))
    lat_deg = math.degrees(lat_rad)
    return lon_deg, lat_deg


def get_polygons(csvpath, exclude=None):
    if exclude is None:
        exclude = []
    for city, state, filepath in get_city_state_filepaths(csvpath):
        name_string = ", ".join((city, state))
        if name_string not in exclude:
            with open(filepath, 'r') as infile:
                yield json.load(infile)


# For decreased computational complexity I run some simplification of the polygons gathered before putting them all
# together into one collection, because these shapes are just a starting point and pretty arbitrary
def make_megagon(csvpath, exclude=None):
    return GeometryCollection([shape(polygon).convex_hull.simplify(0.001).buffer(0.004) for polygon in get_polygons(
        csvpath, exclude=exclude)])


def convert_to_slippy_tile_coords(polygons, zoom=21):
    converted_polygons = []
    for polygon in polygons:
        geojson = mapping(polygon)
        geojson['coordinates'] = np.apply_along_axis(deg2num, 2, np.array(geojson['coordinates']), zoom=zoom)
        converted_polygons.append(shape(geojson))
    return converted_polygons


def save_geojson(filename, feature):
    with open(os.path.join('data', filename), 'w') as outfile:
        geojson.dump(geojson.Feature(geometry=feature, properties={}), outfile)


# function required to call apply_along_axis and get a boolean mask
def point_mapper(x, polygon=None):
    return not polygon.contains(Point((x[0], x[1])))


# This method takes a while, possibly need to multiprocess (1 cpu is maxed out on my machine) or switch to matplotlib
# for possibly more efficient code:
# https://stackoverflow.com/questions/21339448/how-to-get-list-of-points-inside-a-polygon-in-python
def get_coords_inside_polygon(polygon):
    # get a meshgrid the size of the polygon's bounding box
    x, y = np.meshgrid(np.arange(polygon.bounds[0], polygon.bounds[2]), np.arange(polygon.bounds[1], polygon.bounds[3]))

    # convert the meshgrid to an array of points
    x, y = x.flatten(), y.flatten()
    points = np.vstack((x, y)).T

    # calculate if the polygon contains every point
    mask = np.apply_along_axis(point_mapper, 1, points, polygon=polygon)

    # stack the mask so each boolean value gets propagated to both coords
    mask = np.stack((mask, mask), axis=1)

    # delete the points outside the polygon and return
    return np.ma.masked_array(points, mask=mask).compressed().reshape((-1, 2))


def get_coords_caller(name, polygon):
    start_time = time.time()
    coordinates = get_coords_inside_polygon(polygon)
    print(str(time.time() - start_time) + " seconds to complete inner grid calculations for " + name)
    return coordinates


def calculate_inner_coordinates(zoom=21):
    start = time.time()
    # possibly replace with importlib lazy loading if this becomes unwieldy
    import solardb

    slippy_tile_coordinates = list(convert_to_slippy_tile_coords(
        list(make_megagon(args.csvpath, exclude=solardb.get_finished_polygon_names())), zoom=zoom))
    city_state_tuples = list(get_city_state_tuples(args.csvpath))
    assert (len(city_state_tuples) == len(slippy_tile_coordinates))  # make sure no length mismatch
    zipped_names_and_polygons = list(zip([', '.join(city_state_tuple) for city_state_tuple in city_state_tuples],
                                         slippy_tile_coordinates))
    solardb.persist_polygons(zipped_names_and_polygons, zoom=zoom)
    to_calculate_names_and_polygons = []
    for name, polygon in zipped_names_and_polygons:
        if not solardb.polygon_has_inner_grid(name):
            to_calculate_names_and_polygons.append((name, polygon))
    for name, polygon in to_calculate_names_and_polygons:
        coordinates = get_coords_caller(name, polygon)
        solardb.persist_coords(name, coordinates, zoom=zoom)
    print(time.time() - start)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process shapes of city polygons')
    parser.add_argument('--input_csv', dest='csvpath', default=os.path.join('data', '100k_US_cities.csv'),
                        help='specify the csv list of city and state names to gather geoJSON for')
    parser.add_argument('--megagon', dest='megagon', action='store_const',
                        const=True, default=False,
                        help='Create the megagon (all of the city polygons combined) and save it')
    parser.add_argument('--calculate_area', dest='area', action='store_const',
                        const=True, default=False,
                        help='Calculates the area of all polygons in km2')
    parser.add_argument('--calculate_inner_grid', dest='inner', action='store_const',
                        const=True, default=False,
                        help='Calculates every slippy coordinate that\'s within a polygon, '
                             'currently takes a very long time')
    parser.add_argument('--calculate_centroids', dest='centroids', action='store_const',
                        const=True, default=False,
                        help='Calculates missing centroids in the database')
    parser.add_argument('--geojsonio', dest='geojsonio', action='store_const',
                        const=True, default=False,
                        help='Opens processing output in geojsonio if the operation makes sense')
    args = parser.parse_args()

    output = None
    if args.megagon:
        megagon = make_megagon(args.csvpath)
        save_geojson('megagon.geojson', megagon)
        output = megagon
    if args.area:
        projected_polygons = convert_to_slippy_tile_coords(list(make_megagon(args.csvpath)), zoom=21)
        print(str(math.ceil(sum([polygon.area for polygon in projected_polygons])))
              + " total API calls to cover this polygon area!")
        output = projected_polygons
    if args.inner:
        calculate_inner_coordinates(zoom=21)
    if args.centroids:
        if 'solardb' not in sys.modules:
            import solardb
        solardb.compute_centroids()
    if args.geojsonio and output is not None:
        geojsonio.display(geopandas.GeoSeries(output))
