from datetime import datetime, timedelta

from slingshot.record import Record, rights_converter, geom_converter


def test_record_maps_rights():
    r = Record(dc_rights_s='Unrestricted Access')
    assert r.dc_rights_s == 'Public'


def test_record_maps_geom():
    r = Record(layer_geom_type_s='Entity point')
    assert r.layer_geom_type_s == 'Point'


def test_record_defaults_to_mit():
    r = Record()
    r.dct_provenance_s == 'MIT'


def test_record_defaults_to_now_for_modified_time():
    now = datetime.utcnow()
    td = timedelta(seconds=1)
    r = Record()
    assert r.layer_modified_dt is not None
    dt = datetime.strptime(r.layer_modified_dt, '%Y-%m-%dT%H:%M:%SZ')
    assert (now - td) < dt < (now + td)


def test_rights_converter_maps_rights():
    assert rights_converter('Unrestricted layer') == 'Public'
    assert rights_converter('rEsTrIcted layer') == 'Restricted'
    assert rights_converter('Public') == 'Public'


def test_geom_convert_maps_geometry():
    assert geom_converter('a point or two') == 'Point'
    assert geom_converter('here is a string, yo') == 'Line'
    assert geom_converter('however, this is a polygon') == 'Polygon'
    assert geom_converter('Line') == 'Line'
    assert geom_converter('Composite Object') == 'Mixed'
