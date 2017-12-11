# slingshot

This application provides workflow for spatial data. It can be used to create bags, add shapefiles to PostGIS and GeoServer, and index layers in a Solr instance for GeoBlacklight.

## Installation

To install the latest release, create a virtualenv and use pip:

```bash
(slingshot)$ pip install https://github.com/MITLibraries/slingshot/zipball/v0.3.1
```

This will make a `slingshot` command available from your virtualenv.

## Usage

You can view the help menu for the `slingshot` command with:

```bash
(slingshot)$ slingshot --help
```

The help menu for each subcommand can be viewed with:

```bash
(slingshot)$ slingshot <command> --help
```

### Commands

#### bag

The `bag` command will traverse a given directory of zipped shapefiles and perform the following actions:

1. Unpack the zipfile to a new location
2. Create a bag of the unpacked zipfile
3. Add a GeoBlacklight metadata record to the bag called `gbl_record.json`
4. Load the shapefile into PostGIS

If any of these steps fail, the bag will be removed.

#### publish

The `publish` command will traverse a given directory of bags and register each layer in GeoServer and add it to the Solr index. This effectively makes the layer available in GeoBlacklight.

#### reindex

The `reindex` command deletes all the shapefiles from the Solr index, traverses the given directory of bags, and reindexes each of the layers.

## Development

In order to run the integration tests you will need access to a PostGIS database. Add the SQLAlchemy connection URL to a `.env` file in the project root:

```
POSTGIS_DB=postgresql://postgres@localhost/slingshot_test
