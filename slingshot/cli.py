# -*- coding: utf-8 -*-
from __future__ import absolute_import
from datetime import datetime
import os
import shutil

import bagit
import boto3
import click

from slingshot import (flatten_zip, Kepler, make_bag_dir, make_uuid,
                       temp_archive, write_fgdc)


@click.group()
@click.version_option()
def main():
    pass


@main.command()
@click.argument('layers', type=click.Path(exists=True, file_okay=False,
                                          resolve_path=True))
@click.argument('store', type=click.Path(exists=True, file_okay=False,
                                         resolve_path=True))
@click.argument('url')
@click.option('--namespace', default='arrowsmith.mit.edu',
              help="Namespace used for generating UUID 5.")
@click.option('--username', help="Username for kepler submission.")
@click.option('--password',
              help="Password for kepler submission. Omit for prompt.")
@click.option('--s3-key', prompt=True, help="S3 access key id")
@click.option('--s3-secret', prompt=True, help='S3 secret access key')
@click.option('--s3-bucket', default='kepler', help='S3 bucket name')
@click.option('--fail-after', default=5,
              help="Stop after number of consecutive failures. Default is 5.")
def run(layers, store, url, namespace, username, password, fail_after,
        s3_key, s3_secret, s3_bucket):
    """Create and upload bags to the specified endpoint.

    This script will create bags from all the layers in the LAYERS
    directory, uploading them to URL and storing them in the STORE
    directory. Each layer should be in its own subdirectory.

    Layers that already in exist in the STORE directory will be
    skipped. This match is based solely on the names of the
    subdirectories.

    If a layer is not successfully uploaded it will not be placed in
    the STORE directory.

    The namespace option is used in generating a UUID 5 identifier
    for the layer. The default value is arrowsmith.mit.edu.
    """
    if username and not password:
        password = click.prompt('Password', hide_input=True)
    auth = username, password
    if not all(auth):
        auth = None
    kepler = Kepler(url, auth)
    s3 = boto3.client('s3', aws_access_key_id=s3_key,
                      aws_secret_access_key=s3_secret)
    failures = 0
    for layer in [l for l in os.listdir(layers) if l.endswith('.zip')]:
        archive = os.path.join(layers, layer)
        layer_name = os.path.splitext(layer)[0]
        layer_uuid = make_uuid(layer_name, namespace)
        status = kepler.status(layer_uuid)
        if not status or status.lower() == 'failed':
            bag_dir = make_bag_dir(layer_name, store)
            try:
                write_fgdc(archive,
                           os.path.join(bag_dir, '{}.xml'.format(layer_name)))
                flatten_zip(archive,
                            os.path.join(bag_dir, '{}.zip'.format(layer_name)))
                bagit.make_bag(bag_dir)
                with temp_archive(bag_dir, layer_uuid) as zf:
                    s3.upload_file(zf, s3_bucket, layer_uuid)
                kepler.submit_job(layer_uuid)
                click.echo('{}Z: {} uploaded'.format(
                    datetime.utcnow().isoformat(), layer_name))
                failures = 0
            except Exception as e:
                shutil.rmtree(bag_dir, ignore_errors=True)
                failures += 1
                click.echo("%sZ: %s failed with %r" %
                           (datetime.utcnow().isoformat(), layer_name, e))
                if failures >= fail_after:
                    click.echo(
                        "%sZ: Maximum number of consecutive failures (%d)" %
                        (datetime.utcnow().isoformat(), failures))
                    raise e
