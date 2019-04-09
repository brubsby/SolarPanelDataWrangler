import math
import os
import json
import requests
import csv
import argparse


def get_filename(city, state):
    return city.replace(' ', '_') + '.' + state.replace(' ', '_') + '.json'


def get_city_state_tuples(csvpath):
    with open(csvpath, 'r') as csvfile:
        reader = csv.reader(csvfile, skipinitialspace=True)
        for row in reader:
            city = row[0]
            state = row[1]
            yield city, state


def get_city_state_filepaths(csvpath):
    for city, state in get_city_state_tuples(csvpath):
        yield city, state, os.path.join('data', 'geoJSON', get_filename(city, state))


def gather(csvpath):
    for city, state, filepath in get_city_state_filepaths(csvpath):
        if not os.path.isfile(filepath):
                with open(filepath, 'w') as outfile:
                    json.dump(query_nominatim_for_geojson(city, state), outfile)


def query_nominatim_for_geojson(city=None, state=None, county=None, country=None):
    url = "https://nominatim.openstreetmap.org/search?"
    if city:
        url += "city=" + city + "&"
    if state:
        url += "state=" + state + "&"
    if county:
        url += "county=" + county + "&"
    if country:
        url += "country=" + country + "&"
    url += "polygon_geojson=1&format=json"
    response = requests.get(
        url)
    if response.ok:
        response_json = response.json()
        for single_json in response_json:
            feature_type = single_json.get('geojson').get('type')
            if feature_type == 'Polygon' or feature_type == 'MultiPolygon':
                return single_json['geojson']
        raise ValueError("No suitable polygons found for url: {}".format(url))
    else:
        raise ConnectionError(response.content)


# These cities are hard to programmatically get for some reason or another, so you have to use the method here to fix
# your data by hand:
# https://gis.stackexchange.com/questions/183248/getting-polygon-boundaries-of-city-in-json-from-google-maps-api
def get_degenerate_cities(csvpath):
    for city, state, filepath in get_city_state_filepaths(csvpath):
        if os.path.isfile(filepath):
            with open(filepath, 'r') as infile:
                json_dict = json.load(infile)
                if json_dict['type'] != 'Polygon' and json_dict['type'] != 'MultiPolygon':
                    yield city, state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gather and process shapes of cities from OSM')
    parser.add_argument('--input_csv', dest='csvpath', default=os.path.join('data', '100k_US_cities.csv'),
                        help='specify the csv list of city and state names to gather geoJSON for')
    parser.add_argument('--gather', dest='gather', action='store_const',
                        const=True, default=False,
                        help='Run the gather portion of this script, which uses the csv input to gather geoJSON shapes'
                             'from OSM for each city/state pair')
    args = parser.parse_args()

    if args.gather:
        gather(args.csvpath)
