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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run inference for slippy tiles stored in database')
    parser.add_argument('--classification-checkpoint', dest='classification_checkpoint',
                        default=os.path.join('..', 'DeepSolar', 'ckpt', 'inception_classification'),
                        help='Path to DeepSolar classification checkpoint.')
    parser.add_argument('--segmentation-checkpoint', dest='segmentation_checkpoint',
                        default=os.path.join('..', 'DeepSolar', 'ckpt', 'inception_segmentation'),
                        help='Path to DeepSolar segmentation checkpoint.')
    args = parser.parse_args()

    predictor = Predictor(
        dirpath_classification_checkpoint=args.classification_checkpoint,
        dirpath_segmentation_checkpoint=args.segmentation_checkpoint
    )
    avg_tiles_per_sec = 0.0

    for i in itertools.count(0):
        start_time = time.time()
        tiles = solardb.query_tile_batch_for_inference()
        if not tiles:
            print("No viable coordinates left to run inference on. Either provide more polygons or compute centroid "
                  "distances.")

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
