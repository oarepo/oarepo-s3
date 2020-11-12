# oarepo-s3

[![image][]][1]
[![image][2]][3]
[![image][4]][5]
[![image][6]][7]

This package built on top of the [invenio-s3](https://github.com/inveniosoftware/invenio-s3)
library offers integration with any AWS S3 REST API compatible object storage backend.
In addition to the invenio-s3, it tries to minimize processing of file requests on the
Invenio server side and uses direct access to S3 storage backend as much as possible
(neither multipart file uploads, nor downloads are processed by Invenio server itself).

## Instalation

To start using this library

1) install the following packages in your project's venv:
    ```bash
    git clone https://github.com/CESNET/s3-client
    cd s3-client
    poetry install
    pip install oarepo-s3
    ```

2) Create an S3 account and bucket on your S3 storage provider of choice.
3) Put the S3 access configuration into your Invenio server config (e.g. `invenio.cfg`):
    ```python
    INVENIO_S3_TENANT=None
    INVENIO_S3_ENDPOINT_URL='https://s3.example.org'
    INVENIO_S3_ACCESS_KEY_ID='your_access_key'
    INVENIO_S3_SECRET_ACCESS_KEY='your_secret_key'
    ```
3) Create Invenio files location targetting the S3 bucket
    ```bash
    invenio files location --default 'default-s3' s3://oarepo-bucket
    ```

## Usage

To use this library as an Invenio Files storage in your projects, put the following
into your Invenio server config:

```python
FILES_REST_STORAGE_FACTORY = 'oarepo_s3.storage.s3_storage_factory'
```

This storage overrides the `save()` method from the `InvenioS3` storage and adds
the possibility for **direct S3 multipart uploads**. Every other functionality
is handled by underlying `InvenioS3` storage library.

### Direct multipart upload

To create a direct multipart upload to S3 backend, one should provide an
instance of `MultipartUpload` instead of a usual `stream` when assigning
a file to a certain record, e.g.:

```python
from oarepo_s3.api import MultipartUpload
files = record.files  # Record instance FilesIterator
mu = MultipartUpload(key='filename',
                     base_uri=files.bucket.location.uri,
                     expires=3600,
                     size=1024*1024*1000,  # total file size
                     part_size=None,
                     # completion resources as registered in blueprints, see below
                     complete_url='/records/1/files/filename/multipart-complete',
                     abort_url='/records/1/files/filename/multipart-abort')

# Assigning a MultipartUpload to the FilesIterator here will
# trigger the multipart upload creation on the S3 storage backend.
files['test'] = mu
```

this will configure the passed in `MultipartUpload` instance with
all the information needed by any uploader client to process and
complete the upload. The multipart upload session configuration
can be found under the `MultipartUpload.session` field.

To be able to complete or abort an ongoing multipart upload, after an
uploader client finishes uploading all the parts to the S3 backend,
one needs to register the provided resources from `oarepo_s3.views` in
the app blueprints:

```python
def multipart_actions(code, files, rest_endpoint, extra, is_draft):
    # rest path -> view
    return {
        'files/<key>/complete-multipart':
            MultipartUploadCompleteResource.as_view(
                MultipartUploadCompleteResource.view_name.format(endpoint=code)
            ),
        'files/<key>/abort-multipart':
            MultipartUploadAbortResource.as_view(
                MultipartUploadAbortResource.view_name.format(endpoint=code)
            )
    }
```

## OARepo Records Draft integration

This library works best together with [oarepo-records-draft](https://github.com/oarepo/oarepo-records-draft)
library. When integrated into draft endpoints one doesn't need to manually
register the completion resources to blueprints. Multipart upload creation
is also handled automatically.

To setup a drafts integration, just run the following:
```bash
pip install oarepo-records-draft oarepo-s3
```

and configure draft endpoints according to the library's README.
Doing so, will auto-register the following file API actions on the draft
endpoints:

### Create multipart upload
```
POST /draft/records/<pid>/files/?multipart=True
{
  "key": "filename.txt",
  "multipart_content_type": "text/plain",
  "size": 1024
}
```

### Complete multipart upload
```
POST /draft/records/<pid>/files/<key>/complete-multipart
{
  "parts": [{"ETag": <uploaded_part_etag>, PartNum: <part_num>},...]
}
```

### Abort multipart upload
```
POST /draft/records/<pid>/files/<key>/abort-multipart
```

## Tasks

This library provides a task that looks up the expired ongoing
file uploads that could no longer be completed and removes them
from the associated record's bucket, to use this task in your
Celery cron schedule, configure it in your Invenio server config like this:

```python
CELERY_BEAT_SCHEDULE = {
    'cleanup_expired_multipart_uploads': {
        'task': 'oarepo_s3.tasks.cleanup_expired_multipart_uploads',
        'schedule': timedelta(minutes=60),
    },
    ...
}
```



  [image]: https://img.shields.io/github/license/oarepo/oarepo-s3.svg
  [1]: https://github.com/oarepo/oarepo-s3/blob/master/LICENSE
  [2]: https://img.shields.io/travis/oarepo/oarepo-s3.svg
  [3]: https://travis-ci.com/oarepo/oarepo-s3
  [4]: https://img.shields.io/coveralls/oarepo/oarepo-s3.svg
  [5]: https://coveralls.io/r/oarepo/oarepo-s3
  [6]: https://img.shields.io/pypi/v/oarepo-s3.svg
  [7]: https://pypi.org/pypi/oarepo-s3
