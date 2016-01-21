# -*- coding: utf-8 -*-
from __future__ import absolute_import

import click


@click.group()
@click.version_option()
def main():
    pass


@main.command()
def run():
    pass
