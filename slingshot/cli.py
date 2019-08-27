from concurrent.futures import as_completed, ThreadPoolExecutor
from datetime import datetime
import os.path
import traceback

import click
from sqlalchemy.engine.url import URL

from slingshot import state, PUBLIC_WORKSPACE, RESTRICTED_WORKSPACE, DATASTORE
from slingshot.app import (GeoServer, HttpSession, make_slug, publish_layer,
                           publishable_layers, Solr)
from slingshot.db import engine
from slingshot.marc import MarcParser
from slingshot.record import Record
from slingshot.s3 import session


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
@click.option('--db-port', default=5432, help="PostGIS port")
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
                    {"@key": "passwd", "$": db_password},
                    {"@key": "dbtype", "$": "postgis"}
                ]
            }
        }
    }
    geo_auth = (geoserver_user, geoserver_password) if geoserver_user and \
        geoserver_password else None
    geo = GeoServer(geoserver, HttpSession(), auth=geo_auth)
    geo.post("/workspaces", json={"workspace": {"name": PUBLIC_WORKSPACE}})
    geo.post("/workspaces", json={"workspace": {"name": RESTRICTED_WORKSPACE}})
    geo.post("/workspaces/{}/datastores".format(PUBLIC_WORKSPACE),
             json=datastore)
    geo.post("/workspaces/{}/datastores".format(RESTRICTED_WORKSPACE),
             json=datastore)
    geo.delete("/security/acl/layers/*.*.r")
    geo.post("/security/acl/layers",
             json={"{}.*.r".format(PUBLIC_WORKSPACE): "*",
                   "{}.*.r".format(RESTRICTED_WORKSPACE): "ADMIN"})
    click.echo("GeoServer initialized")


@main.command()
@click.argument('layers', nargs=-1)
@click.option('--publish-all', is_flag=True,
              help="Publish all layers in the upload bucket. If the layer "
                   "has already been published it will be skipped unless the "
                   "uploaded layer is newer than the published layer.")
@click.option('--db-uri', envvar='PG_DATABASE',
              help="SQLAlchemy PostGIS URL "
                   "Ex: postgresql://user:password@host:5432/dbname "
                   "Alternatively, instead of passing the database URL, the "
                   "URL components can be passed in separately.")
@click.option('--db-user', envvar="PG_USER", help="Postgres user")
@click.option('--db-password', envvar="PG_PASSWORD", help="Postgres password")
@click.option('--db-host', envvar="PG_HOST", default="localhost",
              help="Postgres host. Default value: localhost")
@click.option('--db-port', envvar="PG_PORT", default=5432,
              help="Postgres port. Default value: 5432")
@click.option('--db-name', envvar="PG_NAME", help="Postgres database name")
@click.option('--db-schema', envvar='PG_SCHEMA', default='public',
              help="PostGres schema name. Default value: public")
@click.option('--geoserver', envvar='GEOSERVER', help="Base Geoserver URL")
@click.option('--geoserver-user', envvar='GEOSERVER_USER',
              help="GeoServer user")
@click.option('--geoserver-password', envvar='GEOSERVER_PASSWORD',
              help="GeoServer password")
@click.option('--solr', envvar='SOLR',
              help="Solr URL. Make sure to include the core name.")
@click.option('--solr-user', envvar='SOLR_USER', help="Solr user")
@click.option('--solr-password', envvar='SOLR_PASSWORD', help="Solr password")
@click.option('--ogc-proxy', envvar='OGC_PROXY',
              help="OGC proxy URL")
@click.option('--download-url', envvar='DOWNLOAD_URL',
              help="Base download URL for layers")
@click.option('--aws-region', envvar='AWS_DEFAULT_REGION', default='us-east-1',
              help="AWS region")
@click.option('--s3-endpoint', envvar='S3_ENDPOINT',
              help="If using an alternative S3 service like Minio, set this "
                   "to the base URL for that service")
@click.option('--s3-alias', envvar='S3_ALIAS', default='s3',
              help="The GeoServer S3 plugin requires a different alias (which "
                   "appears as the protocol) for alternative S3 services, for "
                   "example: minio://bucket/key. See https://docs.geoserver.org/latest/en/user/community/s3-geotiff/index.html "  # noqa: E501
                   "for more information.")
@click.option('--dynamo-table',
              help="Name of DynamoDB table for tracking state of layer")
@click.option('--dynamo-endpoint',
              help="If using an alternative DynamoDB service like moto, set "
                   "this to the base URL for that service")
@click.option('--upload-bucket', help="Name of S3 bucket for uploaded layers")
@click.option('--storage-bucket', help="Name of S3 bucket for stored layers")
@click.option('--num-workers', default=1,
              help="Number of worker threads to use. There is likely not much "
                   "point in setting this higher than the database connection "
                   "pool size which is 5 by default. Defaults to 1.")
def publish(layers, db_uri, db_user, db_password, db_host, db_port, db_name,
            db_schema, geoserver, geoserver_user,
            geoserver_password, solr, solr_user, solr_password,
            s3_endpoint, s3_alias, dynamo_endpoint, dynamo_table, aws_region,
            upload_bucket, storage_bucket, num_workers, publish_all,
            ogc_proxy, download_url):
    if not any((layers, publish_all)) or all((layers, publish_all)):
        raise click.ClickException(
            "You must specify either one or more uploaded layer package names "
            "or use the --publish-all switch.")
    geo_auth = (geoserver_user, geoserver_password) if geoserver_user and \
        geoserver_password else None
    solr_auth = (solr_user, solr_password) if solr_user and solr_password \
        else None
    if db_uri is not None:
        uri = db_uri
    else:
        uri = URL("postgresql", username=db_user, password=db_password,
                  host=db_host, port=db_port, database=db_name)
    engine.configure(uri, db_schema)
    geo_svc = GeoServer(geoserver, HttpSession(), auth=geo_auth,
                        s3_alias=s3_alias)
    solr_svc = Solr(solr, HttpSession(), auth=solr_auth)
    dynamo = session().resource("dynamodb", endpoint_url=dynamo_endpoint,
                                region_name=aws_region)
    s3 = session().resource("s3", endpoint_url=s3_endpoint,
                            region_name=aws_region)
    dynamodb = dynamo.Table(dynamo_table)
    if publish_all:
        work = publishable_layers(s3.Bucket(upload_bucket), dynamodb)
    else:
        work = layers
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(publish_layer, upload_bucket, layer,
                                   geo_svc, solr_svc, storage_bucket,
                                   ogc_proxy, download_url, s3_endpoint):
                   layer for layer in work}
        for future in as_completed(futures):
            layer = futures[future]
            try:
                res = future.result()
            except Exception:
                click.echo(f"Failed to publish {layer}")
                click.echo(traceback.format_exc())
                dynamodb.put_item(Item={
                    "LayerName": os.path.splitext(layer)[0],
                    "LastMod": datetime.utcnow().isoformat(timespec="seconds"),
                    "State": state.FAILED})
            else:
                click.echo("Published {}".format(res))
                dynamodb.put_item(Item={
                    "LayerName": os.path.splitext(layer)[0],
                    "LastMod": datetime.utcnow().isoformat(timespec="seconds"),
                    "State": state.PUBLISHED})


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
    s = Solr(solr, HttpSession(), solr_auth)
    s.delete('dct_provenance_s:MIT AND dc_format_s:"Paper Map"')
    s.delete('dct_provenance_s:MIT AND dc_format_s:"Cartographic Material"')
    for record in MarcParser(marc_file):
        try:
            if record.get('dc_format_s') and \
               record.get('_location') in ('Map Room', 'GIS Collection'):
                del(record['_location'])
                record['layer_slug_s'] = make_slug(record['dc_identifier_s'])
                gbl_record = Record(**record)
                s.add(gbl_record.as_dict(), soft_commit=False)
        except Exception as e:
            click.echo('Failed indexing {}: {}'.format(
                record['dc_identifier_s'], e))
    s.commit()
