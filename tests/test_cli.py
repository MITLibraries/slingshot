import os

from click.testing import CliRunner
import pytest
import requests_mock

from slingshot import state
from slingshot.cli import main
from slingshot.db import engine, metadata


@pytest.fixture
def runner():
    if 'S3_ENDPOINT' in os.environ:
        del os.environ['S3_ENDPOINT']
    return CliRunner()


@pytest.mark.integration
def test_publishes_shapefile(db, runner, shapefile, s3, dynamo_table):
    bucket = s3.Bucket("upload")
    bucket.upload_file(shapefile, "bermuda.zip")
    uri = db().url
    schema = metadata().schema
    with requests_mock.Mocker() as m:
        m.post("mock://example.com/geoserver/rest/workspaces/public/"
               "datastores/pg/featuretypes")
        m.post("mock://example.com/solr/update/json/docs")
        res = runner.invoke(main,
                            ['publish',
                             '--upload-bucket', 'upload',
                             '--storage-bucket', 'store',
                             '--db-user', uri.username,
                             '--db-password', uri.password,
                             '--db-host', uri.host,
                             '--db-port', uri.port,
                             '--db-name', uri.database,
                             '--db-schema', schema,
                             '--geoserver', 'mock://example.com/geoserver/',
                             '--solr', 'mock://example.com/solr',
                             '--dynamo-table', dynamo_table.name,
                             'bermuda.zip'])
    assert res.exit_code == 0
    assert "Published bermuda" in res.output
    with db().connect() as conn:
        r = conn.execute('SELECT COUNT(*) FROM {}.bermuda'.format(schema)) \
            .scalar()
        assert r == 713
    item = dynamo_table.get_item(Key={"LayerName": "bermuda"}).get("Item")
    assert item["State"] == state.PUBLISHED


@pytest.mark.integration
def test_publishes_geotiff(runner, geotiff, s3, dynamo_table):
    bucket = s3.Bucket("upload")
    bucket.upload_file(geotiff, "france.zip")
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/geoserver/rest/workspaces/secure'
               '/coveragestores')
        m.post('mock://example.com/geoserver/rest/workspaces/secure'
               '/coveragestores/france/coverages')
        m.post('mock://example.com/solr/update/json/docs')
        res = runner.invoke(main,
                            ['publish',
                             '--upload-bucket', 'upload',
                             '--storage-bucket', 'store',
                             '--geoserver', 'mock://example.com/geoserver/',
                             '--solr', 'mock://example.com/solr',
                             '--dynamo-table', dynamo_table.name,
                             'france.zip'])
    assert res.exit_code == 0
    assert 'Published france' in res.output
    item = dynamo_table.get_item(Key={"LayerName": "france"}).get("Item")
    assert item["State"] == state.PUBLISHED


def test_initializes_geoserver(runner):
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/geoserver/rest/workspaces')
        m.post('mock://example.com/geoserver/rest/workspaces/public'
               '/datastores')
        m.post('mock://example.com/geoserver/rest/workspaces/secure'
               '/datastores')
        m.delete('mock://example.com/geoserver/rest/security/acl/layers/*.*.r')
        m.post('mock://example.com/geoserver/rest/security/acl/layers')
        res = runner.invoke(main, ['initialize', '--geoserver',
                                   'mock://example.com/geoserver'])
        assert res.exit_code == 0
        assert m.call_count == 6
