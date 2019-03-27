import solardb

from mapbox import Static
from process_city_shapes import deg2num, num2deg
import image_cutter
from PIL import Image
from io import BytesIO

ZOOM_FACTOR = 2
MAPBOX_FINAL_ZOOM = 21
TILE_SIDE_LENGTH = 256
MAX_IMAGE_SIDE_LENGTH = 1280
GRID_SIZE = (MAX_IMAGE_SIDE_LENGTH // TILE_SIDE_LENGTH) * 2 ** ZOOM_FACTOR

service = Static()


def query_grid_and_persist(slippy_coordinates, final_zoom=MAPBOX_FINAL_ZOOM, grid_size=GRID_SIZE):
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
    response = service.image('mapbox.satellite', lon=center_lon_lat[0], lat=center_lon_lat[1], z=final_zoom - 2,
                             width=MAX_IMAGE_SIDE_LENGTH, height=MAX_IMAGE_SIDE_LENGTH, image_format='jpg90',
                             retina=(ZOOM_FACTOR > 0))
    if response.ok:
        image = Image.open(BytesIO(response.content))
        tiles = image_cutter.slice_image(image, base_coords, upsample_count=max(ZOOM_FACTOR - 1, 0),
                                         slices_per_side=grid_size)
        for tile in tiles:
            tile.save(zoom=MAPBOX_FINAL_ZOOM)
        solardb.mark_has_imagery(base_coords, grid_size, zoom=final_zoom)
    else:
        raise Exception(response.content)


if __name__ == "__main__":
    tile_of_interest = (634291, 775538)
    query_grid_and_persist(tile_of_interest)
