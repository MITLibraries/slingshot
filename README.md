# slingshot

This application will create bags from a directory of data layers, submit them to a [kepler](https://github.com/MITLibraries/kepler) instance and store the bags in another directory.

## Installation

Use pip to install into a virtualenv:

```bash
(slingshot)$ pip install https://github.com/MITLibraries/slingshot/zipball/master
```

This make a `slingshot` command available from your virtualenv.

## Usage

You can view the help menu for the `slingshot` command with:

```bash
(slingshot)$ slingshot --help
```

The `run` subcommand will process a directory of layers. View the help message for more information:

```bash
(slingshot)$ slingshot run --help
```
