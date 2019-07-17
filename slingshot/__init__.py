"""
Slingshot
"""


PUBLIC_WORKSPACE = "public"
RESTRICTED_WORKSPACE = "secure"
DATASTORE = "pg"

#: This determines how much is read from an S3 object at once. It is
#: currently used both when reading the zipfile for decompression and
#: when reading the shapefile for loading into Postgres.
S3_BUFFER_SIZE = 1 << 24  # 16 MiB


class state:
    PENDING = 0
    FAILED = 1
    PUBLISHED = 2
