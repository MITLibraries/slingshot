import arrow

from slingshot.record import (
    geometry_mapper,
    MitRecord,
    rights_mapper,
)


def test_mit_record_maps_rights():
    r = MitRecord(dc_rights_s='Unrestricted Access')
    assert r.dc_rights_s == 'Public'


def test_mit_record_maps_geom():
    r = MitRecord(layer_geom_type_s='Entity point')
    assert r.layer_geom_type_s == 'Point'


def test_mit_record_defaults_to_mit():
    r = MitRecord()
    r.dct_provenance_s == 'MIT'


def test_mit_record_defaults_to_now_for_modified_time():
    now = arrow.utcnow()
    r = MitRecord()
    assert r.layer_modified_dt is not None
    assert now.shift(minutes=-1) < arrow.get(r.layer_modified_dt) < \
        now.shift(minutes=+1)


def test_mit_record_formats_datetime():
    r = MitRecord(layer_modified_dt='2000-10-31 23:59:59')
    assert r.layer_modified_dt == '2000-10-31T23:59:59Z'


def test_rights_mapper_maps_rights():
    assert rights_mapper('Unrestricted layer') == 'Public'
    assert rights_mapper('rEsTrIcted layer') == 'Restricted'
    assert rights_mapper('Public') == 'Public'


def testGeometryMapperNormalizesTerm():
    assert geometry_mapper('a point or two') == 'Point'
    assert geometry_mapper('here is a string, yo') == 'Line'
    assert geometry_mapper('however, this is a polygon') == 'Polygon'
    assert geometry_mapper('Line') == 'Line'
    assert geometry_mapper('Composite Object') == 'Mixed'
