import click

from slingshot import PUBLIC_WORKSPACE, RESTRICTED_WORKSPACE, DATASTORE
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
@click.option('--geoserver', envvar='GEOSERVER',
              help="Base URL for GeoServer instance")
@click.option('--geoserver-user', envvar='GEOSERVER_USER',
              help="GeoServer username")
@click.option('--geoserver-password', envvar='GEOSERVER_PASSWORD',
              help="GeoServer password")
@click.option('--db-host', default="localhost", help="PostGIS hostname")
@click.option('--db-port', default="5432", help="PostGIS port")
@click.option('--db-database', default="postgres",
              help="PostGIS database name")
@click.option('--db-schema', default="public", help="PostGIS schema")
@click.option('--db-user', default="postgres", help="PostGIS user")
@click.option('--db-password', envvar='PG_PASSWORD', default="",
              help="PostGIS password")
def initialize(geoserver, geoserver_user, geoserver_password, db_host, db_port,
               db_database, db_schema, db_user, db_password):
    """Initialize a GeoServer instance.

    This command will create the workspaces and datastores the are needed
    for loading data into GeoServer.
    """
    datastore = {
        "dataStore": {
            "name": DATASTORE,
            "connectionParameters": {
                "entry": [
                    {"@key": "host", "$": db_host},
                    {"@key": "port", "$": db_port},
                    {"@key": "database", "$": db_database},
                    {"@key": "schema", "$": db_schema},
                    {"@key": "user", "$": db_user},
                    {"@key": "password", "$": db_password},
                    {"@key": "dbtype", "$": "postgis"}
                ]
            }
        }
    }
    geo_auth = (geoserver_user, geoserver_password) if geoserver_user and \
        geoserver_password else None
    geo = GeoServer(geoserver, auth=geo_auth)
    geo.post("/workspaces", json={"workspace": {"name": PUBLIC_WORKSPACE}})
    geo.post("/workspaces", json={"workspace": {"name": RESTRICTED_WORKSPACE}})
    geo.post("/workspaces/{}/datastores".format(PUBLIC_WORKSPACE),
             json=datastore)
    geo.post("/workspaces/{}/datastores".format(RESTRICTED_WORKSPACE),
             json=datastore)
    click.echo("GeoServer initialized")


@main.command()
@click.argument('bucket')
@click.argument('key')
@click.argument('dest')
@click.option('--db-uri', envvar='PG_DATABASE',
              help="SQLAlchemy PostGIS URL "
                   "Ex: postgresql://user:password@host:5432/dbname")
@click.option('--db-schema', envvar='PG_SCHEMA', default='public',
              help="PostGres schema name. Default value: public")
@click.option('--geoserver', envvar='GEOSERVER', help="Base Geoserver ULR")
@click.option('--geoserver-user', envvar='GEOSERVER_USER',
              help="GeoServer user")
@click.option('--geoserver-password', envvar='GEOSERVER_PASSWORD',
              help="GeoServer password")
@click.option('--solr', envvar='SOLR',
              help="Solr URL. Make sure to include the core name.")
@click.option('--solr-user', envvar='SOLR_USER', help="Solr user")
@click.option('--solr-password', envvar='SOLR_PASSWORD', help="Solr password")
@click.option('--s3-endpoint', envvar='S3_ENDPOINT',
              help="If using an alternative S3 service like Minio, set this "
                   "to the base URL for that service")
@click.option('--s3-alias', envvar='S3_ALIAS',
              help="The GeoServer S3 plugin requires a different alias (which "
                   "appears as the protocol) for alternative S3 services, for "
                   "example: minio://bucket/key. See https://docs.geoserver.org/latest/en/user/community/s3-geotiff/index.html "  # noqa: E501
                   "for more information.")
def publish(bucket, key, dest, db_uri, db_schema, geoserver, geoserver_user,
            geoserver_password, solr, solr_user, solr_password, s3_endpoint,
            s3_alias):
    """Publish layer at s3://BUCKET/KEY

    This will publish the uploaded zipfile layer named KEY in the S3 bucket
    named BUCKET. The unpacked, processed layer will be stored in a new
    directory named after the layer in the DEST bucket.

    The initial zipfile should contain the necessary data files and an
    fgdc.xml file. The unpacked zipfile will be flattened (any subdirectories
    removed) and a geoblacklight.json file containing the GeoBlacklight
    record will be added.
    """
    geo_auth = (geoserver_user, geoserver_password) if geoserver_user and \
        geoserver_password else None
    solr_auth = (solr_user, solr_password) if solr_user and solr_password \
        else None
    engine.configure(db_uri, db_schema)
    geo_svc = GeoServer(geoserver, auth=geo_auth)
    solr_svc = Solr(solr, auth=solr_auth)
    layer = create_layer(*(unpack_zip(bucket, key, dest, s3_endpoint)),
                         s3_endpoint)
    layer.record = create_record(layer, geoserver)
    if layer.format == "Shapefile":
        load_layer(layer)
    geo_svc.add(layer, s3_alias)
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
