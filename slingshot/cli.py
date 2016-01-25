# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os.path
import shutil

import bagit
import click

from slingshot import make_uuid, sub_dirs, submit, temp_archive, copy_dir


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
def run(layers, store, url):
    data = set(sub_dirs(layers))
    uploaded = set(sub_dirs(store))
    for directory in data - uploaded:
        bag = copy_dir(os.path.join(layers, directory), store)
        try:
            bagit.make_bag(bag)
            bag_name = make_uuid(os.path.basename(bag), 'arrowsmith.mit.edu')
            with temp_archive(bag, bag_name) as zf:
                submit(zf, url)
        except Exception as e:
            shutil.rmtree(bag, ignore_errors=True)
            raise e
