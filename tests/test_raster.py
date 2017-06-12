from tempfile import NamedTemporaryFile

import rasterio

from slingshot.raster import normalize, BLOCKSIZE, overviews


def test_normalize_tiles_layer(rgb):
    with NamedTemporaryFile() as out:
        normalize(rgb, out.name)
        with rasterio.open(out.name, 'r') as fp:
            assert fp.block_shapes[0] == (BLOCKSIZE, BLOCKSIZE)


def test_normalize_turns_paletted_layer_into_rgb(paletted):
    with NamedTemporaryFile() as out:
        normalize(paletted, out.name)
        with rasterio.open(out.name, 'r') as fp:
            assert fp.count == 3


def test_normalize_keeps_grayscale_as_grayscale(grayscale):
    with NamedTemporaryFile() as out:
        normalize(grayscale, out.name)
        with rasterio.open(out.name, 'r') as fp:
            assert fp.count == 1


def test_overviews_generates_factors_of_overviews():
    assert overviews(2048, 512) == [2, 4]


def test_normalize_creates_overviews(rgb):
    with NamedTemporaryFile() as out:
        normalize(rgb, out.name)
        with rasterio.open(out.name, 'r') as fp:
            assert fp.overviews(1) == [2]
