import math
import os
import json
import requests
import csv
import argparse


parser = argparse.ArgumentParser(description='Gather and process shapes of cities from OSM')
parser.add_argument('--input_csv', dest='csv', default=os.path.join('data', '100k_US_cities.csv'),
                    help='specify the csv list of city and state names to gather geoJSON for')
parser.add_argument('--gather', dest='gather', action='store_const',
                    const=True, default=False,
                    help='Run the gather portion of this script, which uses the csv input to gather geoJSON shapes '
                         'from OSM for each city/state pair')
parser.add_argument('--list_degenerate_cities', dest='degenerate', action='store_const',
                    const=True, default=False,
                    help='Run the degenerate shape finding portion of the script, finding shapes that aren\'t polygons')

args = parser.parse_args()


# function to convert lat lon to slippy tiles
def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return xtile, ytile


# function to convert slippy tiles to lat lon
def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg


def get_filename(city, state):
    return city.replace(' ', '_') + '.' + state.replace(' ', '_') + '.json'


def get_city_state_tuples():
    with open(args.csv) as csvfile:
        reader = csv.reader(csvfile, skipinitialspace=True)
        for row in reader:
            city = row[0]
            state = row[1]
            yield city, state


def get_city_state_filepaths():
    for city, state in get_city_state_tuples():
        yield city, state, os.path.join('data', 'geoJSON', get_filename(city, state))


def gather():
    for city, state, filepath in get_city_state_filepaths():
        if not os.path.isfile(filepath):
            response = requests.get(
                "https://nominatim.openstreetmap.org/search?city=" + city + "&state=" + state
                + "&polygon_geojson=1&format=json")
            with open(filepath, 'w') as outfile:
                json.dump(response.json()[0]['geojson'], outfile)


# These cities are hard to programmatically get for some reason or another, so you have to use the method here to fix
# your data by hand:
# https://gis.stackexchange.com/questions/183248/getting-polygon-boundaries-of-city-in-json-from-google-maps-api
def get_degenerate_cities():
    for city, state, filepath in get_city_state_filepaths():
        if os.path.isfile(filepath):
            with open(filepath, 'r') as infile:
                json_dict = json.load(infile)
                if json_dict['type'] != 'Polygon' and json_dict['type'] != 'MultiPolygon':
                    yield city, state


if __name__ == '__main__':
    if args.gather:
        gather()
    if args.degenerate:
        for city, state in get_degenerate_cities():
            print(city + ' ' + state)
