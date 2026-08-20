"""Render GitHub READMEs from Jinja2 templates."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mkreadme")
except PackageNotFoundError:
    __version__ = "0.0.0"
