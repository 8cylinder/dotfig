"""Sphinx configuration for the dotfig man page."""

from importlib.metadata import version as package_version

project = "dotfig"
author = "Sheldon McGrandle"
release = package_version("dotfig")

extensions = ["myst_parser", "sphinx_click"]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}

root_doc = "index"
exclude_patterns = ["_build"]
man_show_urls = False

man_pages = [
    ("cli", "dotfig", "Manage dot files", ["Sheldon McGrandle"], 1),
]
