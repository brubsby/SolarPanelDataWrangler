import argparse
import os

import geopandas
from geojsonio import geojsonio
from shapely.geometry import shape

import gather_city_shapes
import maproulette
import process_city_shapes
import run_inference
import solardb

ZOOM = 21
BATCHES_BETWEEN_DELETE = 100

parser = argparse.ArgumentParser(description='Give the search parameters to find a location (usually city/state '
                                             'sufficient), and this script will attempt to find all the solar panels in'
                                             ' that area (given enough time)')
parser.add_argument('--city', dest='city', help='city parameter to pass to nominatim')
parser.add_argument('--county', dest='county', help='county parameter to pass to nominatim')
parser.add_argument('--state', dest='state', help='state parameter to pass to nominatim')
parser.add_argument('--country', dest='country', help='country parameter to pass to nominatim')
parser.add_argument('-q', '--no-geojsonio', dest='no_geojsonio', action='store_const', const=True, default=False,
                    help='don\'t open geojson windows')
parser.add_argument('--classification-checkpoint', dest='classification_checkpoint',
                    default=os.path.join('..', 'DeepSolar', 'ckpt', 'inception_classification'),
                    help='Path to DeepSolar classification checkpoint.')
parser.add_argument('--segmentation-checkpoint', dest='segmentation_checkpoint',
                    default=os.path.join('..', 'DeepSolar', 'ckpt', 'inception_segmentation'),
                    help='Path to DeepSolar segmentation checkpoint.')

args = parser.parse_args()

polygon_name_params = [args.city, args.county, args.state, args.country]
polygon_name = ', '.join([polygon_name_param for polygon_name_param in polygon_name_params if polygon_name_param])

print("Searching OSM for a polygon for: {}".format(polygon_name))
# Get a polygon from nomanatim for the given area parameters https://wiki.openstreetmap.org/wiki/Nominatim
polygon = gather_city_shapes.query_nominatim_for_geojson(city=args.city, county=args.county, state=args.state,
                                                         country=args.country)

print("Checking if this search polygon is already tracked in the database.")
# If inner coords have been calculated for this polygon, we can skip to later
names = solardb.get_inner_coords_calculated_polygon_names()
if polygon_name not in names:

    print("Found a polygon, simplifying it.")
    # Make it simpler (makes calculation of inner grid quicker)
    polygon = process_city_shapes.simplify_polygon(polygon)

    if not args.no_geojsonio:
        # Create a link to geojsonio for the polygon to double check correctness
        print(geojsonio.make_url(geopandas.GeoSeries([polygon]).to_json()))
        input("A geojson.io link has been created with your simplified search polygon, press enter to continue if it "
              "looks okay. If it doesn't, implement a way to edit your polygon and feed it directly to this script :)")

    print("Calculating the coordinates of the imagery grid contained within this polygon.")
    # This step is necessary so we know what images to query in this polygon, it also persists these in the db
    process_city_shapes.calculate_inner_coordinates([polygon_name], [polygon], zoom=ZOOM)

print("Calculating the distance to the search polygon's centroid from each point if it hasn't been done before.")
# This step is just so we have an order for which coordinates to search first (outwards from the middle)
solardb.compute_centroid_distances()

print("Running classification on every tile in the search polygon that hasn't had inference ran yet.")
# You should be able to SIGINT at this point if it's taking forever and it should pick up where it left off if you do
run_inference.run_classification(args.classification_checkpoint, args.segmentation_checkpoint, BATCHES_BETWEEN_DELETE)

print("Querying OpenStreetMap for existing solar panels in this search polygon.")
# This will requery every time, but it's good because you want your task to filter the newly added panels out.
solardb.query_and_persist_osm_solar([shape(polygon)])

print("Detecting clusters of positive classification tiles.")
run_inference.detect_clusters()

print("Generating line-by-line geoJSON file that represents a MapRoulette challenge where each task is a cluster of "
      "found panels containing no existing OSM solar nodes or ways, saved as ./data/{}"
      .format(maproulette.get_maproulette_geojson_filename(polygon_name)))
maproulette.create_clustered_maproulette_geojson(polygon_name=polygon_name, filter_existing_osm_panels=True)

