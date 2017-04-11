import shutil
import tempfile
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from click.testing import CliRunner
import pytest
import requests_mock

from slingshot.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_bag_creates_bag(runner, shapefile):
    store = tempfile.mkdtemp()
    layers = tempfile.mkdtemp()
    shutil.copy2(shapefile, layers)
    with patch('slingshot.cli.load_layer'):
        res = runner.invoke(main, ['bag', '--db-uri', 'sqlite://', '--public',
                                   'mock://example.com', '--secure',
                                   'mock://example.com', layers, store])
    assert res.exit_code == 0
    assert 'Loaded layer bermuda' in res.output


def test_publish_publishes_layer(runner, bags_dir):
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/public/rest/workspaces/mit/datastores'
               '/data/featuretypes')
        m.post('mock://example.com/solr/update/json/docs')
        res = runner.invoke(main, ['publish', '--public',
                                   'mock://example.com/public', '--secure',
                                   'mock://example.com/secure', '--solr',
                                   'mock://example.com/solr', bags_dir])
        assert res.exit_code == 0
        assert 'Loaded bermuda' in res.output
