import boto3
import io
import threading

from slingshot import S3_BUFFER_SIZE


class _Session:
    """A threadsafe boto session.

    Use the global module-level ``session`` instance of this class to get
    a boto3 session.
    """
    def __init__(self):
        self._session = threading.local()

    def __call__(self):
        try:
            return self._session.s
        except AttributeError:
            self._session.s = boto3.session.Session()
        return self._session.s


session = _Session()


class S3IO(io.RawIOBase):
    """Wrapper for an S3 object to function as a raw I/O binary stream.

    This class mostly exists to provide seekable support for an S3 object
    which is required for working with Zipfiles. The ``read()`` method
    will use an HTTP range request to prevent loading the entire object
    into memory.
    """
    def __init__(self, s3_obj):
        """The ``s3_obj`` should be a boto3 ``S3.Object``."""
        self.obj = s3_obj
        self._position = io.SEEK_SET

    def tell(self):
        return self._position

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            self._position = offset
        elif whence == io.SEEK_CUR:
            self._position += offset
        else:
            self._position = self.obj.content_length + offset
        return self._position

    def readable(self):
        return True

    def writable(self):
        return False

    def seekable(self):
        return True

    def readall(self):
        return self.read()

    def readinto(self, b):
        data = self.read(len(b))
        n = len(data)
        b[:n] = data
        return n

    def read(self, size=-1):
        if size == 0 or self.tell() >= self.obj.content_length:
            return b''
        if size is None or size < 0:
            rng = "bytes={:d}-".format(self.tell())
        else:
            rng = "bytes={:d}-{:d}".format(self.tell(), self.tell() + size-1)
        resp = self.obj.get(Range=rng)
        data = resp['Body'].read()
        self.seek(len(data), io.SEEK_CUR)
        return data


def upload(fp, bucket, key, client, chunksize=S3_BUFFER_SIZE):
    mp = client.create_multipart_upload(Bucket=bucket, Key=key)
    mp_id = mp["UploadId"]
    parts = []
    i = 1
    try:
        while True:
            chunk = fp.read(chunksize)
            if not chunk:
                break
            res = client.upload_part(Body=chunk, Bucket=bucket, Key=key,
                                     PartNumber=i, UploadId=mp_id)
            parts.append({"PartNumber": i, "ETag": res["ETag"]})
            i += 1
        client.complete_multipart_upload(Bucket=bucket, Key=key,
                                         MultipartUpload={"Parts": parts},
                                         UploadId=mp_id)
    except Exception:
        client.abort_multipart_upload(Bucket=bucket, Key=key,
                                      UploadId=mp["UploadId"])
        raise
