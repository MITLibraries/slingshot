from datetime import datetime
import uuid

import pytest
import requests_mock

from slingshot.app import (
    create_record,
    GeoServer,
    HttpSession,
    make_slug,
    make_uuid,
    publish_layer,
    publishable_layers,
    Solr,
    unpack_zip,
)


def test_unpack_zip_extracts_to_bucket(s3, shapefile):
    with open(shapefile, 'rb') as fp:
        s3.Bucket("upload").put_object(Key="bermuda.zip", Body=fp)
    unpack_zip("upload", "bermuda.zip", "store")
    objs = [o.key for o in s3.Bucket("store").objects.all()]
    assert 'bermuda/bermuda.shp' in objs


def test_create_record_creates_record(shapefile_object):
    record = create_record(shapefile_object, "http://example.com")
    assert record.dct_provenance_s == 'MIT'
    assert record.dct_references_s.get(
        'http://www.opengis.net/def/serviceType/ogc/wms') == \
        'http://example.com/wms'
    assert record.layer_id_s == "public:bermuda"


def test_create_record_adds_fgdc_url(shapefile_object):
    record = create_record(shapefile_object, "http://example.com")
    assert record.dct_references_s.\
        get("http://www.opengis.net/cat/csw/csdgm/") == \
        "https://store.s3.amazonaws.com/bermuda/bermuda.xml"


def test_geoserver_adds_shapefile(shapefile_object):
    geoserver = GeoServer("mock://example.com/geoserver/", HttpSession())
    with requests_mock.Mocker() as m:
        m.post("mock://example.com/geoserver/rest/workspaces/public/"
               "datastores/pg/featuretypes")
        geoserver.add(shapefile_object)
        assert m.request_history[0].text == \
            '{"featureType": {"name": "bermuda"}}'


def test_solr_adds_layer_to_solr():
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/update/json/docs')
        s = Solr('mock://example.com/', HttpSession())
        s.add({'foo': 'bar'})
        assert m.request_history[0].json() == {'foo': 'bar'}


def test_solr_deletes_by_query():
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/update')
        s = Solr('mock://example.com/', HttpSession())
        s.delete()
        assert m.request_history[0].json() == \
            {'delete': {'query': 'dct_provenance_s:MIT'}}


def test_solr_commits_changes():
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/update')
        s = Solr('mock://example.com/', HttpSession())
        s.commit()
        assert m.request_history[0].json() == {'commit': {}}


def test_make_uuid_creates_uuid_string():
    assert make_uuid('bermuda', 'mit.edu') == \
        uuid.UUID('df04b29c-0e51-58a8-8a37-557e4f4917df')


def test_make_slug_creates_slug():
    assert make_slug('bermuda') == 'mit-34clfhaokfmkq'


@pytest.mark.integration
def test_publish_layer_makes_fgdc_public(s3, shapefile, db):
    s3.Bucket("upload").upload_file(shapefile, "bermuda.zip")
    with requests_mock.Mocker() as m:
        m.post("mock://example.com/geoserver/rest/workspaces/public/"
               "datastores/pg/featuretypes")
        m.post("mock://example.com/solr/update/json/docs")
        publish_layer("upload", "bermuda.zip",
                      GeoServer("mock://example.com/geoserver", HttpSession()),
                      Solr("mock://example.com/solr", HttpSession()),
                      "store", "mock://example.com/ogc")
    obj = s3.Bucket("store").Object("bermuda/bermuda.xml")
    grants = [g for g in obj.Acl().grants if g['Grantee'].get("URI") == \
              'http://acs.amazonaws.com/groups/global/AllUsers']
    assert grants.pop()['Permission'] == 'READ'


@pytest.mark.integration
def test_publish_layer_uses_ogc_proxy_url(s3, shapefile, db):
    s3.Bucket("upload").upload_file(shapefile, "bermuda.zip")
    with requests_mock.Mocker() as m:
        m.post("mock://example.com/geoserver/rest/workspaces/public/"
               "datastores/pg/featuretypes")
        m.post("mock://example.com/solr/update/json/docs")
        publish_layer("upload", "bermuda.zip",
                      GeoServer("mock://example.com/geoserver", HttpSession()),
                      Solr("mock://example.com/solr", HttpSession()),
                      "store", "mock://example.com/ogc/")
    obj = s3.Bucket("store").Object("bermuda/geoblacklight.json")
    assert "mock://example.com/ogc/wms" in obj.get()['Body'].read()\
            .decode('utf8')


def test_publishable_layers_includes_new_layer(s3, dynamo_table):
    s3.Bucket("upload").put_object(Key="foo.zip", Body="Some data")
    layers = list(publishable_layers("upload", "slingshot"))
    assert layers.pop() == "foo.zip"


def test_publishable_layers_includes_updated_layer(s3, dynamo_table):
    awhile_ago = datetime(1980, 1, 1).isoformat()
    dynamo_table.put_item(Item={"LayerName": "foo",
                                "LastMod": awhile_ago})
    s3.Bucket("upload").put_object(Key="foo.zip", Body="Some data")
    layers = list(publishable_layers("upload", "slingshot"))
    assert layers.pop() == "foo.zip"


def test_publishable_layers_skips_old_layer(s3, dynamo_table):
    the_future = datetime(2080, 1, 1).isoformat()
    # This test will fail in the year 2080. Probably ok. I'll be dead anyways.
    dynamo_table.put_item(Item={"LayerName": "foo",
                                "LastMod": the_future})
    s3.Bucket("upload").put_object(Key="foo.zip", Body="Some data")
    layers = list(publishable_layers("upload", "slingshot"))
    assert not layers
