import argparse
import os
import time

import numpy as np
import skimage

import imagery
import solardb
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
    query_durations = np.ndarray((1,))
    inference_durations = np.ndarray((1,))
    save_durations = np.ndarray((1,))
    while True:
        query_start_time = time.time()
        tiles = solardb.query_tile_batch_for_inference()
        query_end_time = inference_start_time = time.time()
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
            tile.inference_timestamp = time.time()
            tile.inference_ran = True

        inference_end_time = save_start_time = time.time()
        solardb.update_tiles(tiles)
        save_end_time = time.time()

        query_duration = query_end_time - query_start_time
        inference_duration = inference_end_time - inference_start_time
        save_duration = save_end_time - save_start_time

        query_durations = np.append(query_durations, [query_duration / len(tiles)])
        inference_durations = np.append(inference_durations, [inference_duration / len(tiles)])
        save_durations = np.append(save_durations, [save_duration / len(tiles)])

        query_median_duration = np.median(query_durations)
        inference_median_duration = np.median(inference_durations)
        save_median_duration = np.median(save_durations)

        print("Query median time per tile: " + str(query_median_duration) + " sec/per. Inference (and resizing) median "
                                                                            "time per tile: "
              + str(inference_median_duration) + " sec/per. Save median time per tile: " + str(save_median_duration) +
              " sec/per. Total rate: " + str(3 / (query_median_duration + inference_median_duration +
                                                  save_median_duration)) + " tiles/s")
