import click

from slingshot.app import (create_record, GeoServer, make_slug, Solr,
                           unpack_zip,)
from slingshot.db import engine, load_layer
from slingshot.layer import create_layer
from slingshot.marc import MarcParser
from slingshot.record import Record


@click.group()
@click.version_option()
def main():
    pass


@main.command()
@click.argument('bucket')
@click.argument('key')
@click.argument('dest')
@click.option('--db-uri', envvar='PG_DATABASE')
@click.option('--db-schema', envvar='PG_SCHEMA', default='public')
@click.option('--geoserver', envvar='GEOSERVER')
@click.option('--geoserver-user', envvar='GEOSERVER_USER')
@click.option('--geoserver-password', envvar='GEOSERVER_PASSWORD')
@click.option('--solr', envvar='SOLR')
@click.option('--solr-user', envvar='SOLR_USER')
@click.option('--solr-password', envvar='SOLR_PASSWORD')
def publish(bucket, key, dest, db_uri, db_schema, geoserver, geoserver_user,
            geoserver_password, solr, solr_user, solr_password):
    geo_auth = (geoserver_user, geoserver_password) if geoserver_user and \
        geoserver_password else None
    solr_auth = (solr_user, solr_password) if solr_user and solr_password \
        else None
    engine.configure(db_uri, db_schema)
    geo_svc = GeoServer(geoserver, auth=geo_auth)
    solr_svc = Solr(solr, auth=solr_auth)
    layer = create_layer(*unpack_zip(bucket, key, dest))
    layer.record = create_record(layer, geoserver)
    if layer.format == "Shapefile":
        load_layer(layer)
    geo_svc.add(layer)
    solr_svc.add(layer.record.as_dict())
    click.echo("Published {}".format(layer.name))


@main.command()
@click.argument('bucket')
@click.option('--solr', envvar='SOLR')
@click.option('--solr-user', envvar='SOLR_USER')
@click.option('--solr-password', envvar='SOLR_PASSWORD')
def reindex(bucket, solr, solr_user, solr_password):
    """Traverse the S3 bucket and index every layer."""
    click.echo("Not implemented")


@main.command()
@click.argument('marc_file')
@click.option('--solr', envvar='SOLR', help='URL for Solr isntance.')
@click.option('--solr-user', envvar='SOLR_USER',
              help='Username for Solr.')
@click.option('--solr-password', envvar='SOLR_PASSWORD',
              help='Password for Solr.')
def marc(marc_file, solr, solr_user, solr_password):
    """Index MARC records into Solr.

    This will delete existing MIT records with a dc_format_s of
    "Paper Map" or "Cartographic Material", and then index all appropriate
    records from the provided MARC XML file.
    """
    solr_auth = (solr_user, solr_password) if solr_user and solr_password \
        else None
    s = Solr(solr, solr_auth)
    s.delete('dct_provenance_s:MIT AND dc_format_s:"Paper Map"')
    s.delete('dct_provenance_s:MIT AND dc_format_s:"Cartographic Material"')
    for record in MarcParser(marc_file):
        try:
            if record.get('dc_format_s') and \
               record.get('_location') in ('Map Room', 'GIS Collection'):
                del(record['_location'])
                record['layer_slug_s'] = make_slug(record['dc_identifier_s'])
                gbl_record = Record(**record)
                s.add(gbl_record.as_dict())
        except Exception as e:
            click.echo('Failed indexing {}: {}'.format(
                record['dc_identifier_s'], e))
    s.commit()
