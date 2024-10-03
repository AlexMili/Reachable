import os.path as osp

from reachable.main import is_reachable, is_reachable_async


__all__ = ["is_reachable", "is_reachable_async"]

version_path = osp.join(osp.dirname(__file__), "VERSION.md")
if osp.exists(version_path):
    with open(version_path, "r") as f:
        __version__ = f.readline()
