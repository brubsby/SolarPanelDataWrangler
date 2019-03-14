import argparse
import functools
import json
import os
import geojson
import pyproj
import shapely.ops as ops
from shapely.geometry import shape, GeometryCollection

from gather_city_shapes import get_city_state_filepaths


def get_polygons(csv):
    for _, _, filepath in get_city_state_filepaths(csv):
        with open(filepath, 'r') as infile:
            yield json.load(infile)


# For decreased computational complexity I run some simplification of the polygons gathered before putting them all
# together into one collection, because these shapes are just a starting point and pretty arbitrary
def make_megagon(csv):
    return GeometryCollection([shape(polygon).convex_hull.simplify(0.001).buffer(0.004) for polygon in get_polygons(csv)])


# Project into an equal area space so that approximate total area can be calculated and used in cost/api estimates
def project_polygons_to_equal_area_projection(polygons):
    projected_polygons = []
    for polygon in polygons:
        projected_polygon = ops.transform(
            functools.partial(
                pyproj.transform,
                pyproj.Proj(init='EPSG:3857'),
                pyproj.Proj(
                    proj='aea',
                    lat1=polygon.bounds[1],
                    lat2=polygon.bounds[3])),
            polygon)
        projected_polygons.append(projected_polygon)
    return projected_polygons


def save_geojson(filename, feature):
    with open(os.path.join('data', filename), 'w') as outfile:
        geojson.dump(geojson.Feature(geometry=feature, properties={}), outfile)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process shapes of city polygons')
    parser.add_argument('--input_csv', dest='csv', default=os.path.join('data', '100k_US_cities.csv'),
                        help='specify the csv list of city and state names to gather geoJSON for')
    parser.add_argument('--proj_dir', dest='proj_dir', default=None,
                        help='specify the csv list of city and state names to gather geoJSON for')
    parser.add_argument('--megagon', dest='megagon', action='store_const',
                        const=True, default=False,
                        help='Create the megagon (all of the city polygons combined) and save it')
    parser.add_argument('--calculate_area', dest='area', action='store_const',
                        const=True, default=False,
                        help='Calculates the area of all polygons in km2')
    args = parser.parse_args()

    if args.proj_dir:
        pyproj.datadir.set_data_dir(args.proj_dir)
    if args.megagon:
        megagon = make_megagon(args.csv)
        save_geojson('megagon.geojson', megagon)
    if args.area:
        projected_polygons = project_polygons_to_equal_area_projection(list(make_megagon(args.csv)))
        print(sum([polygon.area for polygon in projected_polygons]))
