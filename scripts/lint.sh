#!/usr/bin/env bash

set -e
set -x

# mypy src/reachable
ruff check src/reachable
