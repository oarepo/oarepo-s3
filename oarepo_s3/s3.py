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
from s3_client_lib.s3_multipart_client import S3MultipartClient

from oarepo_s3.proxies import current_s3


class S3Client(object):
    """S3 client for communication with AWS S3 APIs."""

    def __init__(self, access_key, secret_key, client_kwargs=dict,
                 config_kwargs=dict, tenant=None):
        """Initialize an S3 client."""
        self.endpoint_url = client_kwargs.get('endpoint_url', None)
        self.client_kwargs = client_kwargs
        self.config_kwargs = config_kwargs
        self.client = S3MultipartClient(
            self.endpoint_url, access_key, secret_key, tenant)

    def init_multipart_upload(self, bucket, object_name, object_size):
        """Creates a multipart upload to AWS S3 API and returns
           session configuration with pre-signed urls.
        """
        return self.client.signed_s3_multipart_upload(bucket=bucket,
                                                      object_name=object_name,
                                                      size=object_size,
                                                      checksum_update=None,
                                                      origin=None,
                                                      finish_url=None)

    def complete_multipart_upload(self, bucket, object_name, parts, upload_id):
        """Completes a multipart upload to AWS S3."""
        self.client.finish_multipart_upload(
            bucket, object_name, parts, upload_id)
        return self.client.finish_file_metadata(
            bucket, object_name, object_name)

    def abort_multipart_upload(self, bucket, object_name, upload_id):
        """Cancels an in-progress multipart upload to AWS S3."""
        return self.client.abort_multipart_upload(
            bucket, object_name, upload_id)
