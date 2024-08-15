#!/usr/bin/env bash

set -e
set -x

pytest --cov=reachable --cov-report=xml test/
