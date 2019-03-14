import functools
import json
import os
import geojson
import pyproj
import shapely.ops as ops
from shapely.geometry import shape, GeometryCollection

from gather_city_shapes import get_city_state_filepaths


def get_polygons():
    for _, _, filepath in get_city_state_filepaths():
        with open(filepath, 'r') as infile:
            yield json.load(infile)


# For decreased computational complexity I run some simplification of the polygons gathered before putting them all
# together into one collection, because these shapes are just a starting point and pretty arbitrary
def make_megagon():
    return GeometryCollection([shape(polygon).convex_hull.simplify(0.001).buffer(0.004) for polygon in get_polygons()])


# This method currently untested, I'm planning to project into an equal area space so that approximate total area can be
# calculated and used in cost/api estimates
def project_polygons_to_equal_area_projection(polygons):
    projected_polygons = []
    for polygon in polygons:
        projected_polygon = ops.transform(
            functools.partial(
                pyproj.transform,
                pyproj.Proj(init='EPSG:4326'),
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
    megagon = make_megagon()
    save_geojson('megagon.geojson', megagon)
