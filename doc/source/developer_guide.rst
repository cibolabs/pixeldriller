Developer Guide
===============

This guide provides developers with an overview of Pixel Driller's
concepts and design.

It should be read in conjunction with the :doc:`tutorial`.

System design
---------------


``pixdrill`` is the top-level package. The Python modules and classes
in ``pixdrill`` are shown in the following class diagram as dark grey boxes.

``Pixel Driller`` leans on other packages (pystac-client, pystac, GDAL, and numpy).
The main classes in these packages that Pixel Driller interfaces with
are shown as white boxes.

..
    graphviz is required to render the diagram
        > sudo apt-get install graphviz
    It adds the executable, dot, to PATH.
    Modify conf.py, adding:
        extensions = [..., sphinx.ext.graphviz]

.. graphviz:: structure.dot

Images and Items
~~~~~~~~~~~~~~~~~~~~~~~

At its core, ``Pixel Driller`` is about extracting pixels from images.
The user specifies these images in one of two ways by providing:

- a path or URL to an image, represented by an ``Image Item``
- parameters for searching for images in a STAC catalogue,
  the results of which are represented by ``STAC Items``

``Item`` is a conceptual abstraction of ``Image Item`` and ``STAC Item``.
It has no corresponding software component. All ``Items`` have an
*ID* and a way to access the file paths (or URLs) to the underlying image or images.

The main difference between an ``Image Item`` and a ``STAC Item`` is the number
if images associated with them. An ``Image Item`` has one image only.
A ``STAC Item`` can have one or more images; each image is a *STAC asset*.

``Pixel Driller`` reads images using the GDAL package.
GDAL represents an image as a ``Dataset``.
An image is composed of one or more bands. Each band is a two-dimensional
numpy array of pixels.

Where and what to drill
~~~~~~~~~~~~~~~~~~~~~~~

The ``Survey Points`` determine the locations of the pixels within an image to extract.

For ``Image Items``, the user supplies the paths or URLs to the images
they want drilled. The ``Survey Points`` dates are not used.

For ``STAC Items``, the images to extract from are determined by:

- the ``STAC Catalogue`` and *collections* specified
- the ``Survey Points'`` locations
- the user-supplied time period either side of the ``Survey Points'`` dates

Drilling
~~~~~~~~~

The ``drill`` module contains functions for drilling or creating the
``Driller`` objects to do so.

``Item Driller``

Iterate over each Driller, drilling pixels for all points for an item,
and storing the pixel data with the Point's PointStats object.

``Image Reader`` and image ``Metadata`` (not much to say about the latter).

``Survey Stats`` - raw data storage, using the ``image_reader.ArrayInfo`` class
and its .data attribute.

Statistics
~~~~~~~~~~

How standard statistics are treated - and constraint that the images in
an Item must only contain a single band.

How user statistics are treated, function signature (see tutorial),
why we pass those objects to the user functions (to give users everything
they could possibly want), and doing nothing with the return values other
than storing them.

The internal storage of statistics inside the PointStats class.
i.e. a dictionary keyed by Items; which in turn have the Statistics, keyed
by the statistic name.

``Drilled Data`` and the .data attribute of the ``ArrayInfo`` class.

Limitations
~~~~~~~~~~~

Don't call calc_stats() twice without resetting, otherwise the statistics
that were calculated previously are recomputed.

The typical and alternative workflows really outline how the data is treated.
