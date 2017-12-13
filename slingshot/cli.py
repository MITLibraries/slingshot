import os
import shutil
import traceback

import click

from slingshot.app import (
    create_record,
    GeoBag,
    make_slug,
    register_layer,
    Solr,
    unpack_zip,
)
from slingshot.app import load_layer
from slingshot.db import engine


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
    if os.path.isdir(layers):
        zips = [os.path.join(layers, l) for l in os.listdir(layers)
                if l.endswith('.zip')]
    else:
        zips = [layers]
    for layer in zips:
        name = os.path.splitext(os.path.basename(layer))[0]
        dest = os.path.join(bags, name)
        try:
            os.mkdir(dest)
        except OSError:
            click.echo('Skipping existing layer {}'.format(name))
            continue
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
@click.option('--metadata',
              help='Directory where FGDC metadata will be stored. If this'
                   ' option is omitted the metadata won\'t be copied.')
@click.option('--workspace', default='mit',
              help='GeoServer workspace for layer.')
@click.option('--datastore', default='data',
              help='GeoServer datastore for layer.')
@click.option('--public', envvar='PUBLIC_GEOSERVER',
              help='URL for public GeoServer instance.')
@click.option('--secure', envvar='SECURE_GEOSERVER',
              help='URL for secure GeoServer instance.')
@click.option('--geoserver-user', envvar='GEOSERVER_USER',
              help='Username for GeoServer.')
@click.option('--geoserver-password', envvar='GEOSERVER_PASSWORD',
              help='Password for GeoServer.')
@click.option('--solr', envvar='SOLR', help='URL for Solr instance.')
@click.option('--solr-user', envvar='SOLR_USER',
              help='Username for Solr.')
@click.option('--solr-password', envvar='SOLR_PASSWORD',
              help='Password for Solr.')
def publish(bags, metadata, workspace, datastore, public, secure,
            geoserver_user, geoserver_password, solr, solr_user,
            solr_password):
    """Add layers to GeoServer and Solr.

    This will traverse the BAGS directory and register each layer in
    the appropriate GeoServer instance, add it to Solr and, optionally,
    copy the FGDC metadata to the specified directory.
    """
    gs_auth = (geoserver_user, geoserver_password) if geoserver_user and \
        geoserver_password else None
    solr_auth = (solr_user, solr_password) if solr_user and solr_password \
        else None
    s = Solr(solr, solr_auth)
    for b in os.listdir(bags):
        try:
            bag = GeoBag(os.path.join(bags, b))
            geoserver = public if bag.is_public() else secure
            register_layer(bag.name, geoserver, workspace, datastore,
                           auth=gs_auth)
            s.add(bag.record)
            if metadata:
                shutil.copy(bag.fgdc, os.path.join(metadata,
                                                   bag.name + '.xml'))
            click.echo('Loaded {}'.format(bag.name))
        except Exception as e:
            click.echo('Failed loading {}: {}'.format(b, e))
    s.commit()


@main.command()
@click.argument('bags')
@click.option('--solr', envvar='SOLR', help='URL for Solr isntance.')
@click.option('--solr-user', envvar='SOLR_USER',
              help='Username for Solr.')
@click.option('--solr-password', envvar='SOLR_PASSWORD',
              help='Password for Solr.')
def reindex(bags, solr, solr_user, solr_password):
    """Reindex layers in Solr.

    This will delete all existing shapefile layers in Solr and then
    reindex every layer in the BAGS directory.
    """
    solr_auth = (solr_user, solr_password) if solr_user and solr_password \
        else None
    s = Solr(solr, solr_auth)
    s.delete('dct_provenance_s:MIT AND dc_format_s:Shapefile')
    for b in os.listdir(bags):
        try:
            bag = GeoBag(os.path.join(bags, b))
            s.add(bag.record)
            click.echo('Indexed {}'.format(bag.name))
        except Exception as e:
            click.echo('Failed indexing {}: {}'.format(b, e))
    s.commit()
