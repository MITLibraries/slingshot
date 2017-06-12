import math

import rasterio
from rasterio.enums import ColorInterp, Resampling
import numpy as np


BLOCKSIZE = 512
TIFF_DEFAULTS = {
    'compress': 'JPEG',
    'interleave': 'PIXEL',
}


def make_palette(cmap):
    """Turn a color map dictionary into a numpy array."""
    palette = np.zeros((len(cmap),), dtype=[('R', np.uint8), ('G', np.uint8),
                                            ('B', np.uint8), ('A', np.uint8)])
    for k, v in cmap.items():
        palette[k] = v
    return palette


def windows(fp):
    """Generate tuples of TIFF windows and blocks.

    ``windows`` is a generator that produces tuples of ``rasterio``
    windows and block generators. A block generator produces data arrays
    for each band in the given window.

    This can be used to iterate over chunks of large TIFFs without
    reading the whole thing into memory at once.
    """
    try:
        palette = make_palette(fp.colormap(1))
    except:
        palette = None
    for _, window in fp.block_windows():
        yield window, blocks(fp, window, palette)


def blocks(fp, window, palette=None):
    """Generate blocks of band data for a given window.

    This produces numpy arrays of data for an image's bands in the given
    window. Paletted images will be expanded to RGB bands.
    """
    cinterp = fp.colorinterp(1)
    if cinterp == ColorInterp.palette:
        block = fp.read(1, window=window)
        expanded = np.take(palette, block)
        for band in ('R', 'G', 'B'):
            yield expanded[band]
    elif cinterp == ColorInterp.gray:
        yield fp.read(1, window=window)
    else:
        for band in range(1, 4):
            yield fp.read(band, window=window)


def overviews(size, blocksize):
    """Compute optimal list of overview levels.

    The size parameter should be max(width, height).
    """
    num_levels = int(math.ceil(math.log((size/blocksize), 2)))
    return [2**y for y in range(1, num_levels + 1)]


def normalize(filein, fileout):
    """Create a normalized GeoTIFF file.

    This will take the input GeoTIFF and create a GeoTIFF that is
    optimized for serving through GeoServer. Compression is set to
    JPEG, the TIFF is tiled using a block size of 512, and overviews
    are added. Paletted TIFFs are expanded to 3-band images and RGB
    images are converted to YCbCr color space.
    """
    with rasterio.open(filein, 'r') as fp_in:
        kwargs = fp_in.profile
        kwargs.update(TIFF_DEFAULTS)
        if max(fp_in.width, fp_in.height) >= BLOCKSIZE:
            kwargs.update({'tiled': True, 'blockxsize': BLOCKSIZE,
                           'blockysize': BLOCKSIZE})
        if fp_in.colorinterp(1) == ColorInterp.palette or fp_in.count == 3:
            kwargs.update({'photometric': 'YCBCR', 'count': 3})
        with rasterio.open(fileout, 'w', **kwargs) as fp_out:
            for window, bands in windows(fp_in):
                for band, block in enumerate(bands, start=1):
                    fp_out.write(block, window=window, indexes=band)
        with rasterio.open(fileout, 'r+') as fp:
            factors = overviews(max(fp.width, fp.height), BLOCKSIZE)
            fp.build_overviews(factors, Resampling.average)
            fp.update_tags(ns='rio_overview', resampling='average')
