# -*- coding: utf-8 -*-
#
# Copyright (C) 2018, 2019, 2020 Esteban J. G. Gabancho.
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""S3 file storage support for Invenio.

To use this module together with Invenio-Files-Rest there are a few things you
need to keep in mind.

The storage factory configuration variable, ``FILES_REST_STORAGE_FACTORY``
needs to be set to ``'oarepo_s3.s3fs_storage_factory'`` importable string.

We think the best way to use this module is to have one `Localtion
<https://invenio-files-rest.readthedocs.io/en/latest/api.html#module-invenio_files_rest.models>`_
for each S3 bucket. This is just for simplicity, it can used however needed.

When creating a new location which will use the S3 API, the URI needs to start
with ``s3://``, for example
``invenio files location s3_default s3://my-bucket --default`` will
create a new location, set it as default location for your instance and use the
bucket ``my-bucket``. For more information about this command check
`Invenio-Files-Rest <https://invenio-files-rest.readthedocs.io/en/latest/>`_
documentation.

Then, there are a few configuration variables that need to be set on your
instance, like the endpoint, the access key and the secret access key, see a
more detailed description in :any:`configuration`.

.. note::

  This module doesn't create S3 buckets automatically, so before starting they
  need to be created.

  You might also want to set the correct `CORS configuration
  <https://docs.aws.amazon.com/AmazonS3/latest/dev/cors.html>`_  so files can
  be used by your interface for things like previewing a PDF with some
  Javascript library.

"""
from flask import current_app
from webargs import fields
from webargs.flaskparser import use_kwargs

multipart_init_args = {
    'size': fields.Int(
        locations=('query', 'json', 'form'),
        missing=None,
    ),
    'part_size': fields.Int(
        locations=('query', 'json', 'form'),
        missing=None,
        load_from='partSize',
        data_key='partSize',
    ),
    'multipart': fields.Boolean(default=False, locations=('query',))
}


class MultipartUploadStatus(object):
    IN_PROGRESS = 'in_progress'
    ABORTED = 'aborted'
    COMPLETED = 'complete'


def multipart_init_response_factory(file_obj):
    """Factory for creation of multipart initialization response."""

    def inner():
        """Response for multipart S3 upload init request"""
        return file_obj.dumps()

    return inner


class MultipartUpload(object):
    """Class representing a multipart file upload to S3."""

    def __init__(self, key, expires, size,
                 part_size=None, complete_url=None, abort_url=None):
        """Initialize a multipart-upload session."""
        self.key = key
        self.expires = expires
        self.uploadId = None
        self.size = size
        self.part_size = part_size
        self.session = {}
        self.complete_url = complete_url
        self.abort_url = abort_url
        self.status = MultipartUploadStatus.IN_PROGRESS


@use_kwargs(multipart_init_args)
def multipart_uploader(record, key, files, pid, request, endpoint,
                       resolver, size=None, part_size=None,
                       multipart=False, **kwargs):
    """Multipart upload handler."""
    from oarepo_s3.views import MultipartUploadAbortResource, \
        MultipartUploadCompleteResource

    expiration = current_app.config['S3_MULTIPART_UPLOAD_EXPIRATION']
    complete = resolver(MultipartUploadCompleteResource.view_name, key=key)
    abort = resolver(MultipartUploadAbortResource.view_name, key=key)

    if multipart and size:
        mu = MultipartUpload(key=key,
                             expires=expiration,
                             size=size,
                             part_size=part_size,
                             complete_url=complete,
                             abort_url=abort)

        files[key] = mu
        files[key]['multipart_upload'] = dict(
            **mu.session,
            complete_url=mu.complete_url,
            abort_url=mu.abort_url,
            status=mu.status
        )
    else:
        files[key] = request.stream

    return multipart_init_response_factory(files[key])
