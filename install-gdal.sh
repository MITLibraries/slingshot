#!/usr/bin/env sh
set -e

if [ ! -d "$HOME/gdal/lib" ]; then
  wget http://download.osgeo.org/gdal/$GDAL_VERSION/gdal-$GDAL_VERSION.tar.xz
  tar -xf gdal-$GDAL_VERSION.tar.xz
  cd gdal-$GDAL_VERSION && ./configure --prefix=$HOME/gdal && make && make install
else
  echo "Using cached directory."
fi
