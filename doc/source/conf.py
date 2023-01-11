# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Pixel Driller'
copyright = '2022, Tony Gill'
author = 'Tony Gill'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc', 'numpydoc', 'sphinx.ext.graphviz',
    'sphinx.ext.autosectionlabel']

templates_path = ['_templates']
exclude_patterns = []
autodoc_mock_imports = ['numpy', 'osgeo']
autodoc_member_order = 'bysource'
# Make sure section targets are unique
autosectionlabel_prefix_document=True


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'pydata_sphinx_theme'
html_static_path = ['_static']

numpydoc_show_class_members = False
