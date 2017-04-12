# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import shutil
import traceback

import click

from slingshot.app import (
    create_record,
    GeoBag,
    index_layer,
    make_bag_dir,
    make_slug,
    register_layer,
    unpack_zip,
)
from slingshot.app import load_layer
from slingshot.db import engine, metadata


@click.group()
@click.version_option()
def main():
    pass


@main.command()
@click.argument('layers', type=click.Path(exists=True, resolve_path=True))
@click.argument('bags', type=click.Path(exists=True, file_okay=False,
                                        resolve_path=True))
@click.option('--db-uri', envvar='PG_DATABASE',
              help='SQLAlchemy database URI. Only PostGIS is currently '
                   'supported.')
@click.option('--workspace', default='mit',
              help='GeoServer workspace for layer.')
@click.option('--public', envvar='PUBLIC_GEOSERVER',
              help='URL for public GeoServer instance.')
@click.option('--secure', envvar='SECURE_GEOSERVER',
              help='URL for secure GeoServer instance.')
def bag(layers, bags, db_uri, workspace, public, secure):
    """Load layers into PostGIS.

    This will load zipped shapefiles into PostGIS and create Bags
    containing the unzipped shapefiles along with a GeoBlacklight JSON
    record. LAYERS should be the path to a zipped shapefile or a
    directory of zipped shapefiles. BAGS is the directory where the
    Bags will be written to. Each Bag directory will be named the same
    as the name of the shapefile.

    A Bag will only be created if the layer was successfully loaded into
    PostGIS. If a Bag already exists the layer will be skipped.
    """
    engine.configure(db_uri)
    metadata.bind = engine()
    if os.path.isdir(layers):
        zips = [os.path.join(layers, l) for l in os.listdir(layers)
                if l.endswith('.zip')]
    else:
        zips = [layers]
    for layer in zips:
        name = os.path.splitext(os.path.basename(layer))[0]
        dest = make_bag_dir(os.path.join(bags, name))
        try:
            unpack_zip(layer, dest)
            bag = GeoBag.create(dest)
            record = create_record(bag,
                                   public=public,
                                   secure=secure,
                                   dc_format_s='Shapefile',
                                   dc_type_s='Dataset',
                                   layer_id_s='{}:{}'.format(workspace, name),
                                   layer_slug_s=make_slug(name))
            bag.record = record.as_dict()
            bag.save()
            load_layer(bag)
            click.echo('Loaded layer {}'.format(name))
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            tb = traceback.format_exc()
            click.echo('Failed creating bag {}: {}'.format(name, tb))


@main.command()
@click.argument('bags')
@click.option('--workspace', default='mit')
@click.option('--datastore', default='data')
@click.option('--public', envvar='PUBLIC_GEOSERVER')
@click.option('--public-user', envvar='PUBLIC_GEOSERVER_USER')
@click.option('--public-password', envvar='PUBLIC_GEOSERVER_PASSWORD')
@click.option('--secure', envvar='SECURE_GEOSERVER')
@click.option('--secure-user', envvar='SECURE_GEOSERVER_USER')
@click.option('--secure-password', envvar='SECURE_GEOSERVER_PASSWORD')
@click.option('--solr', envvar='SOLR')
@click.option('--solr-user', envvar='SOLR_USER')
@click.option('--solr-password', envvar='SOLR_PASSWORD')
def publish(bags, workspace, datastore, public, public_user, public_password,
            secure, secure_user, secure_password, solr, solr_user,
            solr_password):
    public_auth = (public_user, public_password) if public_user and \
        public_password else ()
    secure_auth = (secure_user, secure_password) if secure_user and \
        secure_password else ()
    solr_auth = (solr_user, solr_password) if solr_user and solr_password \
        else ()
    for b in os.listdir(bags):
        try:
            bag = GeoBag(os.path.join(bags, b))
            geoserver = public if bag.is_public() else secure
            geoserver_auth = public_auth if bag.is_public() else secure_auth
            register_layer(bag.name, geoserver, workspace, datastore,
                           auth=geoserver_auth)
            index_layer(bag.record, solr, auth=solr_auth)
            click.echo('Loaded {}'.format(bag.name))
        except Exception as e:
            click.echo('Failed loading {}: {}'.format(b, e))
