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
from s3_client_lib.s3_multipart_client import S3MultipartClient


class S3Client(object):
    """S3 client for communication with AWS S3 APIs."""

    def __init__(self, access_key, secret_key, client_kwargs=dict,
                 config_kwargs=dict, tenant=None):
        """Initialize an S3 client."""
        self.endpoint_url = client_kwargs.get('endpoint_url', None)
        self.client_kwargs = client_kwargs
        self.config_kwargs = config_kwargs
        self.client = S3MultipartClient(
            self.endpoint_url, access_key, secret_key, tenant).client

    def create_multipart_upload(self, bucket, key, content_type, metadata=None):
        """Creates a multipart upload to AWS S3 API and returns
           session configuration with pre-signed urls.
        """

        # See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.create_multipart_upload
        response = self.client.create_multipart_upload(
            ACL='public-read',
            Bucket=bucket,
            ContentType=content_type,
            Key=key,
            Metadata=metadata or {},
        )
        return {'key': response['Key'], 'bucket': response['Bucket'], 'upload_id': response['UploadId']}

    def sign_part_upload(self, bucket, key, upload_id, part_num):
        """Get parameters for uploading one part of a multipart upload."""
        return self.client.generate_presigned_url('upload_part',
                                                  Params=dict(Bucket=bucket,
                                                              Key=key,
                                                              UploadId=upload_id,
                                                              PartNumber=part_num,
                                                              Body=''))

    def get_uploaded_parts(self, bucket, key, upload_id):
        """List parts that have been fully uploaded so far."""
        parts = []

        def _list_parts_page(start_at):
            nonlocal parts
            part_data = self.client.list_parts(Bucket=bucket,
                                               Key=key,
                                               UploadId=upload_id,
                                               PartNumberMarker=start_at)

            parts += part_data.get('Parts', [])
            if (part_data['IsTruncated']):
                _list_parts_page(part_data['NextPartNumberMarker'])
            else:
                return parts

        return _list_parts_page(0)

    def complete_multipart_upload(self, bucket, key, upload_id, parts):
        """Complete a multipart upload, combining all the parts into a single object in the S3 bucket."""
        return self.client.complete_multipart_upload(Bucket=bucket,
                                                     Key=key,
                                                     MultipartUpload={'Parts': parts},
                                                     UploadId=upload_id)

    def abort_multipart_upload(self, bucket, key, upload_id):
        """Cancels an in-progress multipart upload to AWS S3."""
        return self.client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)

