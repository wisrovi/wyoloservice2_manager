"""Sphinx configuration file."""

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "Orchestrator Manager"  # pylint: disable=invalid-name
copyright = "2026, William Steve Rodriguez Villamizar (wisrovi)"  # pylint: disable=redefined-builtin,invalid-name  # noqa: A001
author = "William Steve Rodriguez Villamizar (wisrovi)"  # pylint: disable=invalid-name

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_copybutton",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"  # pylint: disable=invalid-name
html_static_path = ["_static"]
