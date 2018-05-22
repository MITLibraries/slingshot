# slingshot

This application provides workflow for spatial data. It can be used to create bags, add shapefiles to PostGIS and GeoServer, and index layers in a Solr instance for GeoBlacklight.

## Installation

These instructions will make a `slingshot` command available from your virtualenv.

### With pipenv

```bash
$ mkdir slingshot && cd slinghost
$ pipenv install https://github.com/MITLibraries/slingshot/zipball/v0.9.0
$ pipenv run slingshot --version
```

### With pip

```bash
$ python3 -m venv slingshot
$ source slingshot/bin/activate
(slingshot)$ pip install https://github.com/MITLibraries/slingshot/zipball/v0.9.0
(slingshot)$ slingshot --version
```

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
3. Add a GeoBlacklight metadata record to the bag called `geoblacklight.json`
4. Load the shapefile into PostGIS

If any of these steps fail, the bag will be removed.

#### publish

The `publish` command will traverse a given directory of bags and register each layer in GeoServer and add it to the Solr index. This effectively makes the layer available in GeoBlacklight.

#### reindex

The `reindex` command deletes all the shapefiles from the Solr index, traverses the given directory of bags, and reindexes each of the layers.

## Development

Clone the repo and install the dependencies using [Pipenv](https://docs.pipenv.org/):

```bash
$ git clone git@github.com:MITLibraries/slingshot.git
$ cd slingshot
$ pipenv install --dev
```

### Running the Tests

In order to run the integration tests you will need access to a PostGIS database. Add the SQLAlchemy connection URL to a `.env` file in the project root using the `POSTGIS_DB` variable. For example:

```
POSTGIS_DB=postgresql://postgres@localhost/slingshot_test
```

Use [Tox](https://tox.readthedocs.io/en/latest/) to run the tests. You can see which environments are configured to run by default with:

```bash
$ tox -l
```

If it seems like your tests are not picking up changes you've made, try running `make clean`. Usually, this problem arises after you've added new third party dependencies.

### Creating a release

1. Check out a new branch.
2. Use the `release` target for `make` to create a new release.
3. Push your new branch and tag, and follow the usual PR procedure.

This will increment the version number, add a commit and create a git tag. By default the patch number will be incremented. You can change this by setting the `RELEASE_TYPE` variable when running `make`:

```bash
$ pipenv run slingshot --version
slingshot, version 0.3.0
$ git checkout -b new-release
$ make release RELEASE_TYPE=minor
Built release for v0.4.0. Make sure to run:
  $ git push origin new-release tag v0.4.0
```

The `RELEASE_TYPE` variable supports the following settings: `major`, `minor` and `patch`.
