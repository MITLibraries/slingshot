import os

import boto3
from moto import mock_s3, mock_dynamodb2
import pytest

from slingshot.layer import Shapefile


@pytest.fixture
def s3():
    with mock_s3():
        conn = boto3.resource("s3")
        conn.create_bucket(Bucket="upload")
        conn.create_bucket(Bucket="store")
        yield conn


@pytest.fixture
def dynamo_table():
    with mock_dynamodb2():
        db = boto3.resource('dynamodb')
        table = db.create_table(
            TableName="slingshot",
            KeySchema=[{"AttributeName": "LayerName", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "LayerName", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
            ProvisionedThroughput={"ReadCapacityUnits": 1,
                                   "WriteCapacityUnits": 1})
        yield table


@pytest.fixture
def shapefile():
    return _data_file('fixtures/bermuda.zip')


@pytest.fixture
def geotiff():
    return _data_file('fixtures/france.zip')


@pytest.fixture
def shapefile_layer():
    return _data_file('fixtures/bermuda')


@pytest.fixture
def shapefile_stored(s3, shapefile_layer):
    bucket = s3.Bucket("store")
    for f in os.listdir(shapefile_layer):
        bucket.upload_file(os.path.join(shapefile_layer, f),
                           os.path.join("bermuda", f))
    return "store", "bermuda"


@pytest.fixture
def shapefile_object(shapefile_stored):
    return Shapefile(*shapefile_stored)


@pytest.fixture
def prj_4326():
    return _data_file('fixtures/4326.prj')


@pytest.fixture
def prj_2249():
    return _data_file('fixtures/2249.prj')


def _data_file(name):
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(cur_dir, name)
