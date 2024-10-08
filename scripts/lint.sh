#!/usr/bin/env bash

set -e
set -x

ruff check src/reachable
# mypy src/reachable
