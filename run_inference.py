import argparse
import itertools
import os
import time

import numpy as np
import skimage

import imagery
import solardb

from os import path
import sys
sys.path.append(path.abspath('../DeepSolar'))

from inception.predictor import Predictor

IMAGE_SIZE = 299


def detect_clusters():
    polygon_names = solardb.get_polygon_names()
    print("Starting clustering recursion")
    for polygon_name in polygon_names:
        print("Querying tiles for {polygon_name}".format(polygon_name=polygon_name))
        tiles = {}
        coordinates_to_iterate_through = set()
        for tile in solardb.query_tiles_over_threshold(polygon_name=polygon_name, filter_clustered=True):
            coordinate_tuple = (tile.column, tile.row, tile.zoom)
            tiles[coordinate_tuple] = tile
            coordinates_to_iterate_through.add(coordinate_tuple)
        total_iterations = len(coordinates_to_iterate_through)
        print("Starting clustering recursion")
        while coordinates_to_iterate_through:
            print("{0:.0%}".format(((total_iterations - len(coordinates_to_iterate_through)) / total_iterations)))
            tile = coordinates_to_iterate_through.pop()
            cluster = {tile}
            positive_cluster_id = solardb.get_new_positive_cluster_id()
            detect_clusters_recursive_helper(cluster, coordinates_to_iterate_through, tile)
            for coordinate_tuple in cluster:
                slippy_tile = tiles[coordinate_tuple]
                slippy_tile.cluster_id = positive_cluster_id
        solardb.update_tiles(tiles.values())


def detect_clusters_recursive_helper(cluster, coordinates_to_iterate_through, tile, no_check_direction=None):
    north_tuple = (tile[0], tile[1] - 1, tile[2])
    east_tuple = (tile[0] + 1, tile[1], tile[2])
    south_tuple = (tile[0], tile[1] + 1, tile[2])
    west_tuple = (tile[0] - 1, tile[1], tile[2])
    neighbors = [north_tuple, east_tuple, south_tuple, west_tuple]
    for i, coord_tuple in enumerate(neighbors):
        # little bit of optimization to not call the "coord_tuple in coords_to_iterate_through" for the coordinate that
        # just called this method and will never be in the remaining coordinates
        if not (no_check_direction and no_check_direction == i) \
                and coord_tuple in coordinates_to_iterate_through:
            cluster.add(coord_tuple)
            coordinates_to_iterate_through.remove(coord_tuple)
            detect_clusters_recursive_helper(cluster, coordinates_to_iterate_through, coord_tuple, (i + 2) % 4)


def batch_delete_extra_imagery():
    print("Starting extraneous imagery cleanup/deletion")
    polygon_names = solardb.get_polygon_names()
    for polygon_name in polygon_names:
        tiles_above_threshold = solardb.query_tiles_over_threshold(polygon_name=polygon_name)
        expanded_coords_above_threshold = set()
        for tile in tiles_above_threshold:
            for column in range(tile.column - 1, tile.column + 2):
                for row in range(tile.row - 1, tile.row + 2):
                    expanded_coords_above_threshold.add((column, row, tile.zoom))
        print("Calculation for expanded positive coords for {polygon_name} completed".format(polygon_name=polygon_name))
        while True:
            tile_batch = solardb.query_tile_batch(polygon_name=polygon_name)
            to_delete = []
            if not tile_batch:
                break
            for tile in tile_batch:
                tile_tuple = (tile.column, tile.row, tile.zoom)
                if tile_tuple not in expanded_coords_above_threshold:
                    tile.has_image = False
                    to_delete.append(tile_tuple)
            solardb.update_tiles(tile_batch)
            imagery.delete_images(to_delete)
            print("Deleted {num} non-solar panel containing imagery tiles for {polygon_name}".format(
                num=len(to_delete), polygon_name=polygon_name))
            # if no tiles got deleted in the batch it's probably done
            # if the number of expanded coords is larger than the batch size, this could theoretically return early
            if not to_delete:
                break
    print("Deletion finished")


def run_classification(delete_every=None):
    predictor = Predictor(
        dirpath_classification_checkpoint=args.classification_checkpoint,
        dirpath_segmentation_checkpoint=args.segmentation_checkpoint
    )
    avg_tiles_per_sec = 0.0
    for i in itertools.count(0):
        if delete_every and i % delete_every == 0:
            batch_delete_extra_imagery()
        start_time = time.time()
        tiles = solardb.query_tile_batch_for_inference()
        if not tiles:
            print("No viable coordinates left to run inference on. Either provide more polygons or compute centroid "
                  "distances. Attempting to detect clusters now.")
            detect_clusters()
            break

        for tile in tiles:
            image = np.array(imagery.stitch_image_at_coordinate((tile.column, tile.row)))

            resized_image = skimage.transform.resize(image, (IMAGE_SIZE, IMAGE_SIZE))
            if resized_image.shape[2] != 3:
                resized_image = resized_image[:, :, 0:3]
            resized_image = resized_image[None, ...]

            tile.panel_softmax = predictor.classify(resized_image)
            tile.inference_ran = True
            tile.inference_timestamp = time.time()

        solardb.update_tiles(tiles)

        tiles_per_sec = len(tiles) / (time.time() - start_time)
        avg_tiles_per_sec = ((avg_tiles_per_sec * i) + tiles_per_sec) / (i + 1)
        print("{0:.2f} tiles/s | {1:.2f} avg tiles/s".format(tiles_per_sec, avg_tiles_per_sec))


DEFAULT_DELETE_EVERY = 100

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run inference for slippy tiles stored in database')
    parser.add_argument('--classification-checkpoint', dest='classification_checkpoint',
                        default=os.path.join('..', 'DeepSolar', 'ckpt', 'inception_classification'),
                        help='Path to DeepSolar classification checkpoint.')
    parser.add_argument('--segmentation-checkpoint', dest='segmentation_checkpoint',
                        default=os.path.join('..', 'DeepSolar', 'ckpt', 'inception_segmentation'),
                        help='Path to DeepSolar segmentation checkpoint.')
    parser.add_argument('--delete_every', dest='delete_every', default=DEFAULT_DELETE_EVERY,
                        help='Deletes extra imagery every x inference batches, default {}'.format(DEFAULT_DELETE_EVERY))
    args = parser.parse_args()

    run_classification(delete_every=args.delete_every)
