#!/usr/bin/env sh
# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Esteban J. G. Gabancho.
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

pydocstyle invenio_s3 tests docs && \
isort -c -df oarepo_s3 && \
check-manifest --ignore ".travis-*" && \
python setup.py test
