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
@click.argument('layers', type=click.Path(exists=True, file_okay=False,
                                          resolve_path=True))
@click.argument('store', type=click.Path(exists=True, file_okay=False,
                                         resolve_path=True))
@click.option('--db-uri', envvar='PG_DATABASE')
@click.option('--workspace', default='mit')
@click.option('--public', envvar='PUBLIC_GEOSERVER')
@click.option('--secure', envvar='SECURE_GEOSERVER')
def bag(layers, store, db_uri, workspace, public, secure):
    engine.configure(db_uri)
    metadata.bind = engine()
    for layer in [l for l in os.listdir(layers) if l.endswith('.zip')]:
        source = os.path.join(layers, layer)
        name = os.path.splitext(layer)[0]
        dest = make_bag_dir(source, store)
        try:
            unpack_zip(source, dest)
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
@click.option('--secure', envvar='SECURE_GEOSERVER')
@click.option('--solr', envvar='SOLR')
def publish(bags, workspace, datastore, public, secure, solr):
    for b in os.listdir(bags):
        try:
            bag = GeoBag(os.path.join(bags, b))
            geoserver = public if bag.record['dc_rights_s'] == 'Public' \
                else secure
            register_layer(bag.name, geoserver, workspace, datastore)
            index_layer(bag.record)
            click.echo('Loaded {}'.format(bag.name))
        except Exception as e:
            click.echo('Failed loading {}: {}'.format(b, e))
