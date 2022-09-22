#!/usr/bin/env sh
# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Esteban J. G. Gabancho.
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

check-manifest --ignore ".travis-*" && \
pytest -s tests/
