import os
import image_slicer
from PIL import Image


# assumes a square image
def slice_image(image, is_retina=False, slices_per_side=5):
    out = image
    if not is_retina:
        out = retinize(image)
    w, h = image.size()
    for i in range(slices_per_side):
        for j in range(slices_per_side):
            box = (j*w, i*h, (j+1)*w, (i+1)*h)
            yield out.crop(box)


def retinize(image, filter=Image.LANCZOS):
    return image.resize((image.size[0] * 2, image.size[0] * 2), filter)


if __name__=='__main__':
    image_slicer.save_tiles(image_slicer.slice(
        os.path.join('data', 'api_samples', '18x1280x1280@2x.jpeg'), 100, save=False),
        directory=os.path.join('data', 'api_samples', 'split'), prefix='18x1280x1280@2x.jpeg')
    image_slicer.save_tiles(image_slicer.slice(
        os.path.join('data', 'api_samples', '19x1280x1280@2x.jpeg'), 100, save=False),
        directory=os.path.join('data', 'api_samples', 'split'), prefix='19x1280x1280@2x.jpeg')
    retinize(Image.open(os.path.join('data', 'api_samples', '19x1280x1280.jpeg'))).save(os.path.join('data', 'api_samples', '19x1280x1280x2.jpeg'))
    image_slicer.save_tiles(image_slicer.slice(
        os.path.join('data', 'api_samples', '19x1280x1280x2.jpeg'), 100, save=False),
        directory=os.path.join('data', 'api_samples', 'split'), prefix='19x1280x1280.jpeg')
