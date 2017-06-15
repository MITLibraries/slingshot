import os
import shutil
import tempfile
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from click.testing import CliRunner
from dotenv import load_dotenv, find_dotenv
import pytest

from slingshot.cli import main
from slingshot.db import engine, metadata


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def db():
    load_dotenv(find_dotenv())
    uri = os.environ.get('POSTGIS_DB')
    engine.configure(uri)
    return engine


@pytest.fixture(autouse=True)
def db_setup(db):
    metadata.drop_all()
    metadata.clear()


def test_bag_loads_shapefile(db, runner, shapefile):
    store = tempfile.mkdtemp()
    layers = tempfile.mkdtemp()
    shutil.copy2(shapefile, layers)
    uri = os.environ.get('POSTGIS_DB')
    res = runner.invoke(main, ['bag', '--db-uri', uri, '--public',
                               'mock://example.com', '--secure',
                               'mock://example.com', layers, store])
    assert res.exit_code == 0
    with db().connect() as conn:
        r = conn.execute('SELECT COUNT(*) FROM bermuda').scalar()
        assert r == 713


def test_bag_creates_bag(runner, shapefile):
    store = tempfile.mkdtemp()
    layers = tempfile.mkdtemp()
    shutil.copy2(shapefile, layers)
    uri = os.environ.get('POSTGIS_DB')
    res = runner.invoke(main, ['bag', '--db-uri', uri, '--public',
                               'mock://example.com', '--secure',
                               'mock://example.com', layers, store])
    assert res.exit_code == 0
    assert 'Loaded layer bermuda' in res.output


def test_bag_skips_existing_layers(runner, shapefile, bags_dir):
    uri = os.environ.get('POSTGIS_DB')
    res = runner.invoke(main, ['bag', '--db-uri', uri, '--public',
                               'mock://example.com', '--secure',
                               'mock://example.com', shapefile, bags_dir])
    assert res.exit_code == 0
    assert 'Skipping existing layer bermuda' in res.output


def test_bag_removes_failed_bag(runner, shapefile):
    store = tempfile.mkdtemp()
    uri = os.environ.get('POSTGIS_DB')
    with patch('slingshot.cli.load_layer') as m:
        m.side_effect = Exception
        res = runner.invoke(main, ['bag', '--db-uri', uri, '--public',
                                   'mock://example.com', '--secure',
                                   'mock://example.com', shapefile, store])
        assert res.exit_code == 0
        assert 'Failed creating bag bermuda' in res.output
        assert not os.listdir(store)
