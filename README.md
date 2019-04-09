# SolarPanelDataWrangler

![image](https://i.imgur.com/zahiUaU.png)

This is a project containing scripts I'm using to manipulate data having to do with finding solar panels with machine learning and adding their locations to OpenStreetMap.

I've chosen to use SQLite and SQLAlchemy for persisting the search locations and panel confidences, just so the process can be restartable, rapidly prototypeable, and doesn't need to be hosted (so other people can pick up the torch where I may leave off). In the future, if this needs to be turned into a long standing service, using SQLAlchemy should hopefully lessen the work required to switch to a more robust RDMS like PostgreSQL or something.

# Quickstart

To install requirements, run:

`pip install -r requirements.txt`

One of the requirements is rtree, which requires you also build libspatialindex, instructions [here](http://toblerity.org/rtree/install.html) (currently only required if you want to add filtering of existing OSM panels to your MapRoulette task to add the found panels to OSM)

Also, currently [this DeepSolar repo](https://github.com/typicalTYLER/DeepSolar) must be present at ../DeepSolar (relative to this repo) and pre-trained weights must be present in the checkpoint directory.

Lastly your Mapbox API key must be in your environment variables as MAPBOX_ACCESS_TOKEN="MY_ACCESS_TOKEN"

With all that taken care of, you can simply run: 

`python run_entire_process.py --city <city to search> --state <state>`

And the whole suite of scripts should run, eventually outputting a MapRoulette challenge geoJSON for your city. (And leaving you with a sqlite database of these locations)

Please create an [issue](https://github.com/typicalTYLER/SolarPanelDataWrangler/issues/new) if you have any trouble with this quickstart!

# Overview

There are several scripts to aid in the pipeline of turning names of cities into a database of coordinates and whether or not those coordinates contain solar panels.

First, gather_city_shapes.py is used to query OSM with a csv of city, state rows for the boundaries of cities. There are also some tools to help detect incorrect shapes (OSM doesn't always return the correct relation first with my query scheme).
If you don't want to query the data yourself (and have to manually fix it yourself) simply unzip geoJSON.zip in place to get 311 polygons of 100k population US cities.

Next, process_city_shapes.py contains a number of ways to perform operations on these polygons, mainly reducing their complexity, calculating statistics about the shapes, and calculating a grid (and persisting) of coordinates that fall in all of these polygons. The persisting and calculating of these coordinates is currently very slow, so I've made sure to make the operation restartable.

solardb.py contains an ORM for the database object that is currently SQLite, along with some helper functions to aid persistence. I also have started tracking data migrates via alembic, and I'm not sure how well my migrates work for new users, so please leave an issue if you're having trouble with the configuration and I'll try to help.

imagery.py contains code to query and preprocess satellite data (currently only from MapBox, but this is where you'd add more services if you wanted).

run_inference.py downloads, preprocesses, and runs inference on all the computed points in the database that don't have an estimation of whether they contain a solar panel.

maproulette.py contains functionality to turn positive classifications (above a certainty threshold) into a line-by-line geoJSON that can be turned into a MapRoulette class 

# Contributing

Feel free to sign up for and submit pull requests for one of the [existing issues](https://github.com/typicalTYLER/SolarPanelDataWrangler/issues) if you want to contribute! I'm also down to add other Open Climate Fix collaborators as collaborators on this repo. Also feel free to create issues if you are having trouble with anything in this repo.
