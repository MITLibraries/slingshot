import json
import os

import attr
import shapefile


def test_shapefile_returns_access(shapefile_object):
    assert shapefile_object.is_public()


def test_shapefile_returns_layer_name(shapefile_object):
    assert shapefile_object.name == 'bermuda'


def test_shapefile_returns_record(shapefile_object):
    assert shapefile_object.record.layer_slug_s == 'mit-34clfhaokfmkq'


def test_shapefile_writes_record(s3, shapefile_stored, shapefile_object):
    shapefile_object.record = attr.evolve(shapefile_object.record,
                                          dc_title_s='Fooɓar')
    gbl = os.path.join(shapefile_stored[1], 'geoblacklight.json')
    obj = s3.Object(shapefile_stored[0], gbl)
    record = json.loads(obj.get()['Body'].read())
    assert record['dc_title_s'] == "Fooɓar"


def test_shapefile_returns_fgdc_file(shapefile_object):
    assert shapefile_object.fgdc.read(10) == b"<?xml vers"


def test_shapefile_returns_shp_file(shapefile_object):
    with shapefile.Reader(shp=shapefile_object.shp,
                          dbf=shapefile_object.dbf) as shp:
        assert shp.shapeType == shapefile.POINT


def test_shapefile_returns_encoding(shapefile_object):
    assert shapefile_object.encoding == "ISO-8859-1"


def test_shapefile_returns_srid_as_int(shapefile_object):
    assert shapefile_object.srid == 4326
