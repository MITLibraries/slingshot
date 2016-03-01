# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import shutil

import bagit
import click

from slingshot import (make_uuid, submit, temp_archive, prep_bag,
                       uploadable,)


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
def run(layers, store, url, namespace, username, password):
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
    for data_layer in uploadable(layers, store):
        bag = prep_bag(os.path.join(layers, data_layer), store)
        try:
            bagit.make_bag(bag)
            bag_name = make_uuid(os.path.basename(bag), namespace)
            with temp_archive(bag, bag_name) as zf:
                submit(zf, url, auth)
        except Exception as e:
            shutil.rmtree(bag, ignore_errors=True)
            raise e
