import os
import pathlib
from io import BytesIO

from PIL import Image
from mapbox import Static

import solardb
from process_city_shapes import num2deg


class ImageTile(object):
    """Represents a single image tile."""

    def __init__(self, image, coords, filename=None):
        self.image = image
        self.coords = coords
        self.filename = filename

    @property
    def row(self):
        return self.coords[0]

    @property
    def column(self):
        return self.coords[1]

    @property
    def basename(self):
        """Strip path and extension. Return base filename."""
        return get_basename(self.filename)

    def generate_filename(self, zoom=21, directory=os.path.join(os.getcwd(), 'data', 'imagery'),
                          format='jpg', path=True):
        """Construct and return a filename for this tile."""
        filename = os.path.join(str(zoom), str(self.row), str(self.column) +
                                '.{ext}'.format(ext=format.lower().replace('jpeg', 'jpg')))
        if not path:
            return filename
        return os.path.join(directory, filename)

    def save(self, filename=None, file_format='jpeg', zoom=21):
        if not filename:
            filename = self.generate_filename(zoom=zoom)
        pathlib.Path(os.path.dirname(filename)).mkdir(parents=True, exist_ok=True)
        self.image.save(filename, file_format)
        self.filename = filename

    def load(self, filename=None, zoom=21):
        if not filename:
            filename = self.generate_filename(zoom=zoom)
        if not pathlib.Path(filename).isfile():
            return None
        self.filename = filename
        self.image = Image.open(filename)

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
    base_x, base_y = base_coords
    for i in range(upsample_count):
        out = double_image_size(out)
    w, h = out.size
    w = w // slices_per_side
    h = h // slices_per_side
    tiles = []
    for i in range(slices_per_side):
        for j in range(slices_per_side):
            box = (j * w, i * h, (j + 1) * w, (i + 1) * h)
            cropped_image = out.crop(box)
            coords = (j + base_x, i + base_y)
            tiles.append(ImageTile(cropped_image, coords))
    return tiles


def double_image_size(image, filter=Image.LANCZOS):
    return image.resize((image.size[0] * 2, image.size[0] * 2), filter)


ZOOM_FACTOR = 2
MAPBOX_FINAL_ZOOM = 21
TILE_SIDE_LENGTH = 256
MAX_IMAGE_SIDE_LENGTH = 1280
GRID_SIZE = (MAX_IMAGE_SIDE_LENGTH // TILE_SIDE_LENGTH) * 2 ** ZOOM_FACTOR

service = Static()


def gather_and_persist_imagery_at_coordinate(slippy_coordinates, final_zoom=MAPBOX_FINAL_ZOOM, grid_size=GRID_SIZE,
                                             imagery="mapbox"):
    # the top left square of the query grid this point belongs to
    base_coords = tuple(map(lambda x: x - x % grid_size, slippy_coordinates))
    if grid_size % 2 == 0:
        # if the grid size is even, the center point is between 4 tiles in center (or the top left of bottom right one)
        center_bottom_right_tile = tuple(map(lambda x: x + grid_size // 2, base_coords))
        center_lon_lat = num2deg(center_bottom_right_tile, zoom=final_zoom, center=False)
    else:
        # if the grid is odd, the center point is in the center of the center square
        center_tile = tuple(map(lambda x: x + grid_size // 2, base_coords))
        center_lon_lat = num2deg(center_tile, zoom=MAPBOX_FINAL_ZOOM, center=True)
    if imagery == "mapbox":
        response = service.image('mapbox.satellite', lon=center_lon_lat[0], lat=center_lon_lat[1], z=final_zoom - 2,
                                 width=MAX_IMAGE_SIDE_LENGTH, height=MAX_IMAGE_SIDE_LENGTH, image_format='jpg90',
                                 retina=(ZOOM_FACTOR > 0))
        if response.ok:
            image = Image.open(BytesIO(response.content))
            tiles = slice_image(image, base_coords, upsample_count=max(ZOOM_FACTOR - 1, 0),
                                slices_per_side=grid_size)
            for tile in tiles:
                tile.save(zoom=MAPBOX_FINAL_ZOOM)
            solardb.mark_has_imagery(base_coords, grid_size, zoom=final_zoom)
        else:
            raise Exception(response.content)
    else:
        AttributeError("Unsupported Imagery source: " + str(imagery))


if __name__ == "__main__":
    tile_of_interest = (634291, 775538)
    gather_and_persist_imagery_at_coordinate(tile_of_interest)
