# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
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
import json
from datetime import datetime, timedelta

from flask import current_app
from invenio_db import db
from invenio_files_rest.models import ObjectVersion, ObjectVersionTag
from webargs import fields
from webargs.flaskparser import use_kwargs

from oarepo_s3.constants import MULTIPART_CONFIG_TAG, MULTIPART_EXPIRATION_TAG

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


def multipart_init_response_factory(file_obj):
    """Factory for creation of multipart initialization response."""

    def inner():
        """Response for multipart S3 upload init request"""
        tags = file_obj.obj.get_tags()

        mc_val = tags.get(MULTIPART_CONFIG_TAG, None)
        exp_val = tags.get(MULTIPART_EXPIRATION_TAG, None)

        mc = {'multipart_upload': json.loads(mc_val)} if mc_val else {}
        exp = {'expiration': exp_val} if exp_val else {}

        return {
            **file_obj.dumps(),
            **mc,
            **exp
        }

    return inner


class MultipartUpload(object):
    """Class representing a multipart file upload to S3."""

    def __init__(self, key, expires, size,
                 part_size=None, complete_url=None,
                 abort_url=None, base_uri=None):
        """Initialize a multipart-upload session."""
        self.key = key
        self.expires = expires
        self.uploadId = None
        self.size = size
        self.part_size = part_size
        self.base_uri = base_uri
        self.session = {}
        self.complete_url = complete_url
        self.abort_url = abort_url


@use_kwargs(multipart_init_args)
def multipart_uploader(record, key, files, pid, request, endpoint,
                       resolver, size=None, part_size=None,
                       multipart=False, **kwargs):
    """Multipart upload handler."""
    from oarepo_s3.views import MultipartUploadAbortResource, \
        MultipartUploadCompleteResource

    expiration = current_app.config['S3_MULTIPART_UPLOAD_EXPIRATION']
    date_expiry = datetime.utcnow() + timedelta(seconds=expiration)
    complete = resolver(MultipartUploadCompleteResource.view_name, key=key)
    abort = resolver(MultipartUploadAbortResource.view_name, key=key)

    if multipart and size:
        mu = MultipartUpload(key=key,
                             base_uri=files.bucket.location.uri,
                             expires=expiration,
                             size=size,
                             part_size=part_size,
                             complete_url=complete,
                             abort_url=abort)

        files[key] = mu
        file_obj = files[key]

        with db.session.begin_nested():
            # create tags with multipart upload configuration
            mc_tag = ObjectVersionTag(
                object_version=file_obj.obj,
                key=MULTIPART_CONFIG_TAG,
                value=json.dumps(dict(
                    **mu.session,
                    complete_url=mu.complete_url,
                    abort_url=mu.abort_url,
                )))
            db.session.add(mc_tag)

            exp_tag = ObjectVersionTag(
                object_version=file_obj.obj,
                key=MULTIPART_EXPIRATION_TAG,
                value=date_expiry.isoformat()
            )
            db.session.add(exp_tag)

        db.session.commit()
    else:
        files[key] = request.stream

    return multipart_init_response_factory(files[key])
