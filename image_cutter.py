import os
from PIL import Image
import pathlib


class Tile(object):
    """Represents a single tile."""

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

    def save(self, filename=None, format='jpeg', zoom=21):
        if not filename:
            filename = self.generate_filename(zoom=zoom)
        pathlib.Path(os.path.dirname(filename)).mkdir(parents=True, exist_ok=True)
        self.image.save(filename, format)
        self.filename = filename

    def __repr__(self):
        """Show tile number, and if saved to disk, filename."""
        if self.filename:
            return '<Tile #{} - {}>'.format(self.number,
                                            os.path.basename(self.filename))
        return '<Tile #{}>'.format(self.number)


def get_basename(filename):
    """Strip path and extension. Return basename."""
    return os.path.splitext(os.path.basename(filename))[0]


# assumes a square image
def slice_image(image, base_coords, upsample_count=0, slices_per_side=5):
    out = image
    base_x, base_y = base_coords
    for i in range(upsample_count):
        out = double_size(out)
    w, h = out.size
    w = w // slices_per_side
    h = h // slices_per_side
    tiles = []
    for i in range(slices_per_side):
        for j in range(slices_per_side):
            box = (j * w, i * h, (j + 1) * w, (i + 1) * h)
            cropped_image = out.crop(box)
            coords = (j + base_x, i + base_y)
            tiles.append(Tile(cropped_image, coords))
    return tiles


def double_size(image, filter=Image.LANCZOS):
    return image.resize((image.size[0] * 2, image.size[0] * 2), filter)
