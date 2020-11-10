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
from flask import abort, jsonify
from flask.views import MethodView
from invenio_db import db
from invenio_files_rest.models import ObjectVersion
from invenio_files_rest.proxies import current_permission_factory
from invenio_files_rest.signals import file_deleted
from invenio_files_rest.views import check_permission
from invenio_files_rest.tasks import remove_file_data
from invenio_records_rest.views import pass_record
from webargs import fields
from webargs.flaskparser import use_kwargs

from oarepo_s3.api import MultipartUploadStatus
from oarepo_s3.proxies import current_s3

multipart_complete_args = {
    'parts': fields.List(
        fields.Dict,
        locations=('json', 'form'))
}


class MultipartUploadCompleteResource(MethodView):
    """Complete multipart upload method view."""
    view_name = '{endpoint}_upload_complete'

    @pass_record
    @use_kwargs(multipart_complete_args)
    def post(self, pid, record, key, parts):
        files = record.files
        file_rec = files[key]
        mup = file_rec.get('multipart_upload')

        if not mup:
            abort(400, 'resource is not a multipart upload')
        if mup['status'] != MultipartUploadStatus.IN_PROGRESS:
            abort(400, 'multipart upload cannot be completed')

        res = current_s3.client.complete_multipart_upload(
            mup['bucket'],
            mup['key'],
            parts,
            mup['upload_id'])
        file_rec.pop('multipart_upload')

        etag = 'etag:{}'.format(res['ETag'])
        file_rec.obj.file.checksum = etag
        file_rec['checksum'] = etag
        files.flush()
        record.commit()
        db.session.commit()

        return jsonify(res)


def delete_file_object(bucket, obj):
    # Permanently delete specific object version.
    check_permission(
        current_permission_factory(bucket, 'object-delete-version'),
        hidden=False,
    )
    obj.remove()
    # Set newest object as head
    if obj.is_head:
        latest = ObjectVersion.get_versions(obj.bucket,
                                            obj.key,
                                            desc=True).first()
        if latest:
            latest.is_head = True

    if obj.file_id:
        remove_file_data.delay(str(obj.file_id))

    db.session.commit()
    file_deleted.send(obj)


class MultipartUploadAbortResource(MethodView):
    """Cancel a multipart upload method view."""
    view_name = '{endpoint}_upload_abort'

    @pass_record
    def post(self, pid, record, key):
        files = record.files
        file_rec = files[key]
        mup = file_rec.get('multipart_upload')

        if not mup:
            abort(400, 'resource is not a multipart upload')
        if mup['status'] not in [MultipartUploadStatus.IN_PROGRESS,
                                 MultipartUploadStatus.FAILED]:
            abort(400, 'cannot abort, upload not in progress nor failed')

        res = current_s3.client.abort_multipart_upload(
            mup['bucket'],
            mup['key'],
            mup['upload_id'])

        del files[key]
        delete_file_object(mup['bucket'], file_rec.obj)

        files.flush()
        record.commit()
        db.session.commit()

        return jsonify(res)


def multipart_actions(code, files, rest_endpoint, extra, is_draft):
    # decide if view should be created on this
    # resource and return blueprint mapping
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
