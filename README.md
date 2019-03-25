# SolarPanelDataWrangler

![image](https://i.imgur.com/2fJrBo2.png)

This is a small project containing scripts I'm using to manipulate data having to do with finding solar panels with machine learning and adding their locations to OpenStreetMap.

I've chosen to use SQLite and SQLAlchemy for persisting the search locations and panel confidences, just so the process can be restartable, rapidly prototypeable, and doesn't need to be hosted (so other people can pick up the torch where I may leave off). In the future, if this needs to be turned into a long standing service, using SQLAlchemy should hopefully lessen the work required to switch to a more robust RDMS like PostgreSQL or something.

# Overview

There are several scripts to aid in the pipeline of turning names of cities into a database of coordinates and whether or not those coordinates contain solar panels.

First, gather_city_shapes.py is used to query OSM with a csv of city, state rows for the boundaries of cities. There are also some tools to help detect incorrect shapes (OSM doesn't always return the correct relation first with my query scheme).
If you don't want to query the data yourself (and have to manually fix it yourself) simply unzip geoJSON.zip in place to get 311 polygons of 100k population US cities.

Next, process_city_shapes.py contains a number of ways to perform operations on these polygons, mainly reducing their complexity, calculating statistics about the shapes, and calculating a grid (and persisting) of coordinates that fall in all of these polygons. The persisting and calculating of these coordinates is currently very slow, so I've made sure to make the operation restartable.

solardb.py contains an ORM for the database object that is currently SQLite, along with some helper functions to aid persistence. I also have started tracking data migrates via alembic, and I'm not sure how well my migrates work for new users, so please leave an issue if you're having trouble with the configuration and I'll try to help.

The next steps are to:
- map the coordinate database to the mapbox API, and to properly queue, slice up, and persist satelitte images until they can have inference run on them (in progress)
- modify [DeepSolar](https://github.com/typicalTYLER/DeepSolar) to run inference on arbitrary tile batches (currently just runs on test set)
- query OSM existing solar panel locations to exclude from results
- do something with the results
- parallelize slower parts of this code (I've tride to paralellize the inner grid calculation and persistence but after much effort it was still not working correctly)
- possibly gather imagery from different sources if mapbox is too rate limited

# Contributing

Feel free to submit pull requests if you want to add a feature or optimize the code! I'm also down to add other Open Climate Fix collaborators as collaborators on this repo.
