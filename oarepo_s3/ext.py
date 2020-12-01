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
from flask import current_app
from invenio_base.utils import obj_or_import_string

from . import config


class OARepoS3State(object):
    """OARepo-S3 extension state."""

    def __init__(self, app):
        """Initialize the state."""
        self.app = app

    @property
    def tenant(self):
        return self.app.config.get('S3_TENANT', None)

    @property
    def client(self):
        client = obj_or_import_string(self.app.config['S3_CLIENT'])
        s3_info = current_app.extensions['invenio-s3'].init_s3fs_info
        return client(access_key=s3_info['key'],
                      secret_key=s3_info['secret'],
                      client_kwargs=s3_info['client_kwargs'],
                      tenant=self.tenant,
                      config_kwargs=s3_info['config_kwargs'])


class OARepoS3(object):
    """OARepo-S3 extension."""

    def __init__(self, app=None):
        """Extension initialization."""
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Flask application initialization."""
        self.init_config(app)
        _state = OARepoS3State(app)
        app.extensions['oarepo-s3'] = _state

    def init_config(self, app):
        """Initialize configuration."""
        for k in dir(config):
            if k.startswith('S3_'):
                app.config.setdefault(k, getattr(config, k))
