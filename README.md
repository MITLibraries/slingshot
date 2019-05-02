# slingshot

This application provides workflow for spatial data. It will load a zipped layer from S3 into GeoServer and index it Solr.

## Installation

The easiest way to get started is to install using Pipenv:

```bash
$ git clone git@github.com:MITLibraries/slingshot.git
$ cd slingshot
$ pipenv install
$ pipenv run slingshot
```

## Development

Clone the repo and install the dependencies using [Pipenv](https://docs.pipenv.org/):

```bash
$ git clone git@github.com:MITLibraries/slingshot.git
$ cd slingshot
$ pipenv install --dev
```

### Running the Tests

In order to run the integration tests you will need access to a PostGIS database. Add the SQLAlchemy connection URL to a `.env` file in the project root using the `PG_DATABASE` variable. For example:

```
PG_DATABASE=postgresql://postgres@localhost/postgres
```

You can quickly set up a PostGIS database with docker:

```
$ docker run -p 5432:5432 mdillon/postgis
```

You should also consider adding the `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` to your `.env` file and set these to any dummy value. While this is not strictly necessary, it will help prevent you from accidentally using your real AWS credentials during testing/development.

Use [Tox](https://tox.readthedocs.io/en/latest/) to run the tests. You can see which environments are configured to run by default with:

```bash
$ tox -l
```

If it seems like your tests are not picking up changes you've made, try running `make clean`. Usually, this problem arises after you've added new third party dependencies.
