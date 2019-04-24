import os
import pathlib
import subprocess
import time
from io import BytesIO
import glob

from PIL import Image, ImageChops
from mapbox import Static
from osgeo import gdal

import solardb
from process_city_shapes import num2deg


class ImageTile(object):
    """Represents a single image tile."""

    def __init__(self, image, coords, filename=None):
        self.image = image
        self.coords = coords
        self.filename = filename

    @property
    def column(self):
        return self.coords[0]

    @property
    def row(self):
        return self.coords[1]

    @property
    def basename(self):
        """Strip path and extension. Return base filename."""
        return get_basename(self.filename)

    def generate_filename(self, zoom=21, directory=None, source='mapbox', format='jpg', path=True):
        """
        Construct and return a filepath for this tile.

        :param zoom: zoom level of this tile
        :param directory: directory to store this tile image in
        :param source: imagery source, used in determining directory to store in
        :param format: image format type
        :param path: boolean to determine whether to return filepath or filename
        :return:
        """
        if not directory:
            directory = os.path.join(os.getcwd(), 'data', 'imagery', source)
        filename = os.path.join(str(zoom), str(self.row), str(self.column) +
                                '.{ext}'.format(ext=format.lower().replace('jpeg', 'jpg')))
        if not path:
            return filename
        return os.path.join(directory, filename)

    def save(self, filename=None, file_format='jpeg', zoom=21, source='mapbox'):
        if not filename:
            filename = self.generate_filename(zoom=zoom, source=source)
        pathlib.Path(os.path.dirname(filename)).mkdir(parents=True, exist_ok=True)
        self.image.save(filename, file_format)
        self.filename = filename

    def load(self, filename=None, zoom=21, source='mapbox'):
        if not filename:
            filename = self.generate_filename(zoom=zoom, source=source)
        if self.image:
            return self.image
        if not pathlib.Path(filename).is_file():
            return None
        self.filename = filename
        self.image = Image.open(filename)
        return self.image

    def delete(self, filename=None, zoom=21, source='mapbox'):  # TODO zoom should probably be a tile property
        if not filename:
            filename = self.generate_filename(zoom=zoom, source=source)
        pathlib.Path(filename).unlink()
        self.filename = filename

    def __repr__(self):
        """Show tile coords, and if saved to disk, filename."""
        if self.filename:
            return '<Tile #{} - {}>'.format(self.coords,
                                            self.filename)
        return '<Tile #{}>'.format(self.coords)


def get_basename(filename):
    """Strip path and extension. Return basename."""
    return os.path.splitext(os.path.basename(filename))[0]


# assumes a square image
def slice_image(image, base_coords, upsample_count=0, slices_per_side=5):
    out = image
    base_column, base_row = base_coords
    for i in range(upsample_count):
        out = double_image_size(out)
    w, h = out.size
    w = w // slices_per_side
    h = h // slices_per_side
    tiles = []
    for row_offset in range(slices_per_side):
        for column_offset in range(slices_per_side):
            box = (column_offset * w, row_offset * h, (column_offset + 1) * w, (row_offset + 1) * h)
            cropped_image = out.crop(box)
            coords = (column_offset + base_column, row_offset + base_row)
            tiles.append(ImageTile(cropped_image, coords))
    return tiles


def double_image_size(image, filter=Image.LANCZOS):
    return image.resize((image.size[0] * 2, image.size[0] * 2), filter)


# amount of zooms out to do from final zoom level when querying for imagery
ZOOM_FACTOR = 2
# the final zoom level of the saved tiles
FINAL_ZOOM = 21
TILE_SIDE_LENGTH = 256
MAX_IMAGE_SIDE_LENGTH = 1280
# number of times to cut the source imagery to get it to correct tile size
GRID_SIZE = (MAX_IMAGE_SIDE_LENGTH // TILE_SIDE_LENGTH) * 2 ** ZOOM_FACTOR

# the side length of the stitched image
FINISHED_TILE_SIDE_LENGTH = 320
# the amount to stitch from each border tile
STITCH_WIDTH = (FINISHED_TILE_SIDE_LENGTH - TILE_SIDE_LENGTH) // 2
# the amount not to stitch from each border tile
CROPPED_WIDTH = TILE_SIDE_LENGTH - STITCH_WIDTH
CROP_BOXES = [
    (CROPPED_WIDTH, CROPPED_WIDTH, TILE_SIDE_LENGTH, TILE_SIDE_LENGTH),
    (CROPPED_WIDTH, 0, TILE_SIDE_LENGTH, TILE_SIDE_LENGTH),
    (CROPPED_WIDTH, 0, TILE_SIDE_LENGTH, STITCH_WIDTH),
    (0, CROPPED_WIDTH, TILE_SIDE_LENGTH, TILE_SIDE_LENGTH),
    (0, 0, TILE_SIDE_LENGTH, TILE_SIDE_LENGTH),
    (0, 0, TILE_SIDE_LENGTH, STITCH_WIDTH),
    (0, CROPPED_WIDTH, STITCH_WIDTH, TILE_SIDE_LENGTH),
    (0, 0, STITCH_WIDTH, TILE_SIDE_LENGTH),
    (0, 0, STITCH_WIDTH, STITCH_WIDTH)
]
PASTE_COORDINATES = [
    (0, 0),
    (0, STITCH_WIDTH),
    (0, TILE_SIDE_LENGTH + STITCH_WIDTH),
    (STITCH_WIDTH, 0),
    (STITCH_WIDTH, STITCH_WIDTH),
    (STITCH_WIDTH, TILE_SIDE_LENGTH + STITCH_WIDTH),
    (TILE_SIDE_LENGTH + STITCH_WIDTH, 0),
    (TILE_SIDE_LENGTH + STITCH_WIDTH, STITCH_WIDTH),
    (TILE_SIDE_LENGTH + STITCH_WIDTH, TILE_SIDE_LENGTH + STITCH_WIDTH),
]

MAX_RETRIES = 12  # max wait time with exponential backoff would be ~34 minutes

service = Static()


def delete_blank_tiles(source="world_file", extensions=None):
    """
    Deletes all blank image tiles (for a jpeg, this is just an all black image) in the data/imagery/<source> directory

    :param source: imagery subdirectory name to delete images in
    :param extensions: iterable list of file extensions to delete
    """
    print("Deleting blank tile imagery...")
    start_time = time.time()
    if extensions is None:
        extensions = ("jpg", "jpeg", "png")
    else:
        extensions = tuple(extensions)
    for dir_entry in os.scandir(os.path.join('data', 'imagery', source)):
        if dir_entry.is_dir() and dir_entry.name.isdecimal():  # confirm is zoom directory
            for zoom_dir_entry in os.scandir(os.path.join('data', 'imagery', source, dir_entry.name)):
                if zoom_dir_entry.is_dir():
                    for column_dir_entry in \
                            os.scandir(os.path.join('data', 'imagery', source, dir_entry.name, zoom_dir_entry.name)):
                        if column_dir_entry.is_file() and column_dir_entry.name.lower().endswith(extensions):
                            image_path = os.path.join('data', 'imagery', source, dir_entry.name, zoom_dir_entry.name,
                                                      column_dir_entry.name)
                            image = Image.open(image_path)
                            if not ImageChops.invert(image).getbbox():
                                os.remove(image_path)
    print("Finished deleting blank tile imagery in {} seconds".format(time.time()-start_time))


def process_world_files_and_images(directory_path):
    """
    Takes in a directory path containing jpg and jgw files, creates a virtual database file for their mosaic, and then
    generates zoom level 21 slippy tiles for them and places them in data/imagery/world_file/21/

    :param directory_path: path to jpg and jgw files
    """
    print("Importing imagery from {}".format(directory_path))
    start_time = time.time()
    mosaic_file_path = pathlib.Path(directory_path, "mosaic.vrt")
    mosaic2_file_path = pathlib.Path(directory_path, "mosaic2.vrt")
    mosaic3_file_path = pathlib.Path(directory_path, "mosaic3.vrt")
    mosaic_file_path_str = str(mosaic_file_path)
    mosaic2_file_path_str = str(mosaic2_file_path)
    mosaic3_file_path_str = str(mosaic3_file_path)

    files = glob.glob(str(pathlib.Path(directory_path, "*.jpg")))

    subprocess.call(["gdalbuildvrt", "-overwrite", mosaic_file_path_str, *files])
    data_set = gdal.Open(mosaic_file_path_str)
    data_set_band = data_set.GetRasterBand(1)
    output_y_size = data_set_band.YSize * 2
    output_x_size = data_set_band.XSize * 2
    subprocess.call(["gdalwarp", "-overwrite", "-r", "bilinear", "-ts", str(output_x_size), str(output_y_size), "-of",
                     "vrt", mosaic_file_path_str, mosaic2_file_path_str])
    output_y_size = output_y_size * 2
    output_x_size = output_x_size * 2
    subprocess.call(["gdalwarp", "-overwrite", "-r", "bilinear", "-ts", str(output_x_size), str(output_y_size), "-of",
                     "vrt", mosaic2_file_path_str, mosaic3_file_path_str])
    subprocess.call(["python", "gdal2tilesp.py", "-e", "-w", "none", "-z", "21", "-f", "JPEG", "-o", "xyz",
                     "-s", "EPSG:27700", mosaic3_file_path_str, "data/imagery/world_file"])

    print("Finished importing, upsampling, and tiling imagery in {} seconds".format(time.time()-start_time))
    delete_blank_tiles("world_file")
    # TODO add untracked imagery to database


def gather_and_persist_mapbox_imagery_at_coordinate(slippy_coordinates, final_zoom=FINAL_ZOOM, grid_size=GRID_SIZE):
    # the top left square of the query grid this point belongs to
    base_coords = tuple(map(lambda x: x - x % grid_size, slippy_coordinates))
    if grid_size % 2 == 0:
        # if the grid size is even, the center point is between 4 tiles in center (or the top left of bottom right one)
        center_bottom_right_tile = tuple(map(lambda x: x + grid_size // 2, base_coords))
        center_lon_lat = num2deg(center_bottom_right_tile, zoom=final_zoom, center=False)
    else:
        # if the grid is odd, the center point is in the center of the center square
        center_tile = tuple(map(lambda x: x + grid_size // 2, base_coords))
        center_lon_lat = num2deg(center_tile, zoom=FINAL_ZOOM, center=True)
    for i in range(MAX_RETRIES):
        try:
            response = service.image('mapbox.satellite', lon=center_lon_lat[0], lat=center_lon_lat[1], z=final_zoom - 2,
                                     width=MAX_IMAGE_SIDE_LENGTH, height=MAX_IMAGE_SIDE_LENGTH, image_format='jpg90',
                                     retina=(ZOOM_FACTOR > 0))
            if response.ok:
                image = Image.open(BytesIO(response.content))
                tiles = slice_image(image, base_coords, upsample_count=max(ZOOM_FACTOR - 1, 0),
                                    slices_per_side=grid_size)
                to_return = None
                for tile in tiles:
                    if tile.coords == slippy_coordinates:
                        to_return = tile.image
                    tile.save(zoom=FINAL_ZOOM)
                solardb.mark_has_imagery(base_coords, grid_size, zoom=final_zoom)
                return to_return
            backoff_time = pow(2, i)
            print('Got this response from mapbox:"{error}", exponentially backing off, {time} seconds.'
                  .format(error=getattr(response, "content", None), time=backoff_time))
            time.sleep(backoff_time)
        except ConnectionError as e:
            backoff_time = pow(2, i)
            print('Got an connection error when trying to query and process imagery, exponentially backing off, '
                  '{time} seconds.'.format(error=repr(e), time=backoff_time))
            time.sleep(backoff_time)
        except OSError as e:
            if "image file is truncated" in str(e):
                backoff_time = pow(2, i)
                print('Got an OSError:"{error}" when trying to query and process imagery, exponentially backing off, '
                      '{time} seconds.'.format(error=repr(e), time=backoff_time))
                time.sleep(backoff_time)
            else:
                raise e
    raise ConnectionError("Couldn't connect to mapbox after {retries}".format(retries=MAX_RETRIES))


# loads image from disk if possible, otherwise queries an imagery service
def get_image_for_coordinate(slippy_coordinate):
    tile = ImageTile(None, slippy_coordinate)
    image = tile.load()
    if not image:
        image = gather_and_persist_mapbox_imagery_at_coordinate(slippy_coordinate, final_zoom=FINAL_ZOOM)
    return image


# gets a larger image at the specified slippy coordinate by stitching other border tiles together
# TODO: optimize
# TODO: there's also some symmetry here that can be exploited but this seems easier for now
def stitch_image_at_coordinate(slippy_coordinate):
    images = []
    # gather the images in each direction around the target image
    for column in range(slippy_coordinate[0] - 1, slippy_coordinate[0] + 2):
        for row in range(slippy_coordinate[1] - 1, slippy_coordinate[1] + 2):
            images.append(get_image_for_coordinate((column, row),))

    cropped_images = []
    for image, crop_box in zip(images, CROP_BOXES):
        cropped_images.append(image.crop(crop_box))
    output_image = Image.new('RGB', (FINISHED_TILE_SIDE_LENGTH, FINISHED_TILE_SIDE_LENGTH))
    for cropped_image, paste_coordinate in zip(cropped_images, PASTE_COORDINATES):
        cropped_images.append(output_image.paste(cropped_image, box=paste_coordinate))
    return output_image


def delete_images(slippy_coordinates):
    for coordinate_tuple in slippy_coordinates:
        ImageTile(None, coordinate_tuple).delete(zoom=coordinate_tuple[2])
