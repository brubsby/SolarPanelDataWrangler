# SolarPanelDataWrangler

![image](https://i.imgur.com/zahiUaU.png)

This is a project containing scripts I'm using to manipulate data having to do with finding solar panels with machine learning and adding their locations to OpenStreetMap.

I've chosen to use SQLite and SQLAlchemy for persisting the search locations and panel confidences, just so the process can be restartable, rapidly prototypeable, and doesn't need to be hosted (so other people can pick up the torch where I may leave off). In the future, if this needs to be turned into a long standing service, using SQLAlchemy should hopefully lessen the work required to switch to a more robust RDMS like PostgreSQL or something.

# Quickstart

If you'd like to build and work out of the pre-existing Docker container, jump to the Docker container section just below. Regardless of the setup method, once you're all done you should be able to run:

`python run_entire_process.py --city <city to search> --state <state>`

And the whole suite of scripts should run, eventually outputting a MapRoulette challenge geoJSON for your city. (And leaving you with a sqlite database of these locations)

Please create an [issue](https://github.com/typicalTYLER/SolarPanelDataWrangler/issues/new) if you have any trouble with this quickstart!

## Manual Setup

### Conda Environment

One of the requirements is rtree, which requires you to install libspatialindex, instructions [here](http://toblerity.org/rtree/install.html).

To install the environment, choose either the `setup/environment_cpu.yml` and `setup/environment_gpu.yml`. If you have a GPU that you intend to use, you'll need to setup the relevant packages / drivers (e.g. cuDNN / CUDA, NVIDIA diver, etc.) before installing the conda environment. Once you've chosen a YML file, you can create the environment via something like the following:

```
conda create --name spdw --file setup/environment_cpu.yml
```

*Note*: These environments are built on `conda=4.6.11`, `python=3.6.8`, and `tensorflow=1.12.0`.

### DeepSolar repository

Currently, [this DeepSolar repo](https://github.com/typicalTYLER/DeepSolar) must be present at ../DeepSolar (relative to this repo) and pre-trained weights must be present in the `ckpt` directory inside of the `DeepSolar` repository.

### MapBox Token

Your Mapbox API key must be in your environment variables as MAPBOX_ACCESS_TOKEN="MY_ACCESS_TOKEN".

## Docker Setup

Within the `setup` directory is a `build_docker_images.sh` script that can be used to automatically setup a docker container to develop out of.

### No GPU Build 

To build a docker image that uses the no GPU conda environment, first install docker. Next, choose a username that you would like to use inside the container, and from **within the setup directory**, run:

```
bash build_docker_images.sh --docker_user [specify username here]
```

Once the image is built, you should be able to work inside a container created from the image just as if you were logged into a remote instance.

### GPU Build 

To build a docker image that uses  the GPU conda environment, first install nvidia-docker (version 2.0). Next, make sure that you have the appropriate GPU driver installed for your system and for the version of tensorflow that will be used (`1.12.0`) as well as the versions of CUDA and cuDNN (CUDA 9.0 and cuDNN7. Once that is done, choose a username that you would like to use inside the container, and from **within the setup directory**, run:

```
bash build_docker_images.sh --docker_user [specify username here] --gpu_build
```

Once the image is built, you should be able to work inside a container created from the image just as if you were logged into a remote instance.

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
