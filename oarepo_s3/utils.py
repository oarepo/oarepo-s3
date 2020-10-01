# -*- coding: utf-8 -*-
#
# Copyright (C) 2018, 2019, 2020 Esteban J. G. Gabancho.
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Version information for oarepo-s3.

This file is imported by ``oarepo_s3.__init__``,
and parsed by ``setup.py``.
"""

def multipart_init_response_factory(multipartUpload):
    """Factory for creation of multipart initialization response."""
    def _multipart_init_response():
        """Response for multipart S3 upload init request"""
        # TODO: serialize mu to json
        return multipartUpload

    return _multipart_init_response
