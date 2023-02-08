Developer Guide
===============

This guide provides developers with an overview of Pixel Driller's
concepts and design.

It should be read in conjunction with the :doc:`tutorial`.

Package design
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

A ``Survey Point`` determines the location of the pixels within an image to
extract.

For ``Image Items``, the user supplies the paths or URLs to the images
they want drilled. The ``Survey Point`` date is not used.

For ``STAC Items``, Pixel Driller uses the images returned from the search
of a ``STAC Catalogue`` using the user-supplied parameters, including:

- the ``STAC Catalogue`` and *collections* specified
- the locations of the ``Survey Points``
- the image acquisition-window for each ``Survey Point``

Drilling
~~~~~~~~~

The ``drill`` module contains functions for drilling or creating the
``Driller`` objects to do so. A ``Driller`` is an instance of the
``drillpoints.ItemDriller`` class. A ``Driller`` contains:

- a collection of ``Survey Points`` that intersect the ``Item``
- a function for reading the pixel data for every point from its ``Item's``
  images
- a function for calculating the statistics for every point

``Driller`` delegates the responsibility of reading the pixels from an
image to an ``Image Reader`` object. It also delegates responsibility
for computing statistics to each ``Point's`` associated ``Survey Stats``
object, which is an instance of ``drillstats.PointStats``. As such,
``Drillers`` indirectly populate the each point's survey statistics.

Statistics
~~~~~~~~~~

Each ``Survey Point`` stores its pixel data and statistics in a
``Survey Stats`` object, which is an instance of ``drillstats.PointStats``.
A Point might intersect multiple Items, so the ``Survey Stats`` object
stores the pixel data and statistics for every Item.

Pixel data and statistics are stored in the ``PointStats.item_stats``
dictionary, keyed by the Item's ID. Each item in the dictionary is
another dictionary containing elements for:

- the _raw_ pixel data, a ``numpy.ma.masked_array``
- information about the array of pixels read from the image, an instance
  of ``image_reader.ArrayInfo``
- the statistics, the data type of which is that returned from the function
  used to compute the statistic

**Standard statistics**

The ``pixdrill.drillstats`` module contains built-in functions for computing
a suite of standard statistics. These functions take a list of
``numpy.ma.masked_array`` arrays. Each is a 3D array containing the pixels
extracted for a Point for one image. The functions assume that each image
contains only one band, thus the shape of each array passed to the built-in
functions must be (1, nrows, ncols).

For an ImageItem, the array list passed to a built-in function contains only
one array. For a STAC Item, the list will contain an array for each
Item asset.

**User statistics**

Users can write their own functions to calculate statistics. The
:ref:`Tutorial <tutorial:user statistics>` describes the function
signature and the objects that are passed to a user's function.

The user will also provide a name for their function. The code calls each
user function and stores the value returned from the function
in the ``PointStats`` object. For example, from ``PointStats.calc_stats()``::

    stats = self.item_stats[item_id]  # Dictionary of stats for the Item
    ...

    # user_stats is a list of tuples as supplied by the user. Each tuple
    # contains the name of the statistic (a string) and the function
    # that calculates it.
    for stat_name, stat_func in user_stats:
        stats[stat_name] = stat_func(stats[STATS_ARRAYINFO], item, self.pt)

The information passed to the user function contains everything we think a
user would need to compute a statistic.
``stats[STATS_ARRAYINFO]`` is the ``image_reader.ArrayInfo`` object, which
contains:

- the pixel data, in the ``data`` attribute
- the asset id, in the ``asset_id`` attribute
- plus the location of the pixels within the image it was read from

``item`` is the ``Stac Item`` or ``Image Item``. The user can inspect its
properties, such as its ID. And ``self.pt`` is the ``Point`` object, so that
the user knows which point is being operated on. The user can pass
additional information to the user function a ``Point`` attributes,
for example, using Python's built-in ``setattr`` and ``getattr`` functions.

Reprojecting points
--------------------

When reading pixels from an image, the Point's bounding box is
calculated in the image's coordinate reference system (CRS). There are three
coordinate reference systems that must be considered:

#. The coordinate reference system of the image
#. The coordinate reference system of the Point, as specified by the user
#. The coordinate reference system of the Point's buffer attribute, which
   defines the size of the region of interest

It's straight forward to transform the point's location to the same
CRS as the image. The buffer requires more attention.

For the buffer, we want it to be expressed in metres if the image's CRS
is projected, and in degrees if the image's CRS is geographic. So we must
convert the buffer to a length in metres if the user defines the buffer
in degrees and the image has a projected CRS. Or convert the buffer to
a length in degrees if the user defines it in metres (the default) and
the image has a geographic CRS.

A complication arises when the buffer distance is defined in metres,
the image's CRS is geographic, and the point's CRS is geographic.
We don't know which CRS the buffer distance is defined in.
So we have to choose one.

The same complication arises when the buffer distance is defined in degrees,
the image's CRS is projected, and the point's CRS is projected. Again, we
don't know which CRS the buffer distance is defined in and we have to
choose one.

The details are in ``Point.change_buffer_units()``.


Contributing
------------------

We welcome the community's contributions.

We prefer to use the
`Fork and pull model <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/getting-started/about-collaborative-development-models>`__
for pull requests.

A suggested development environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The project's ``Dockerfile`` is a good reference for creating the
development environment in which you can develop and run tests.
Use this along with the ``build-dev`` and ``run-dev``
targets in the ``Makefile``. Modify those targets for your own environment.
For example::

    user@dev-host:~$ git clone https://github.com/cibolabs/pixeldriller.git
    user@dev-host:~$ cd pixeldriller
    user@dev-host:~/pixeldriller$ cp Makefile MyMakefile
    # EDIT MyMakefile: update the build-dev and run-dev targets
    user@dev-host:~/pixeldriller$ make -f MyMakefile build-dev
    user@dev-host:~/pixeldriller$ make -f MyMakefile run-dev
    # Then, from the running container, pip install an editable
    # version of the package, and run the example
    root@5d63691b9aa8:~/pixeldriller# source activate_dev
    root@5d63691b9aa8:~/pixeldriller# python3 -m example
    Stats for point: x=0, y=-1123600
        Item ID=S2B_52LHP_20220730_0_L2A
            Mean values: [443.80165289 219.33884298]
        Item ID=S2A_52LHP_20220728_0_L2A
            Mean values: [2543.60330579 2284.67768595]
        Item ID=S2A_52LHP_20220725_0_L2A
            Mean values: [492.32231405 403.69421488]
    Stats for point: x=140, y=-36.5
        Item ID=S2A_54HVE_20220730_0_L2A
            Mean values: [3257.65289256 3140.01652893]
        Item ID=S2B_54HVE_20220725_0_L2A
            Mean values: [3945.52066116 3690.01652893]


Tests and coverage
~~~~~~~~~~~~~~~~~~~

When contributing, please write a test for new features, and confirm that
all existing tests pass. Tests are located in the ``tests`` directory.
We use the `pytest <https://docs.pytest.org>`__ framework.

We also use coverage to show the test coverage.

From within the running development container, run tests using::

    root@5d63691b9aa8:~/pixeldriller# python3 -m pytest -s tests

For coverage::

    root@5d63691b9aa8:~/pixeldriller# python3 -m coverage run --source=pixdrill -m pytest tests
    root@5d63691b9aa8:~/pixeldriller# python3 -m coverage report
    # OR to generate a coverage report as HTML
    root@5d63691b9aa8:~/pixeldriller# python3 -m coverage html


Documentation
~~~~~~~~~~~~~~~~~

When contributing, please also update these docs.
Documentation is in the ``doc`` folder. Consider modifying the
tutorial or developer guide. Docs are written in
`restructured text <https://www.sphinx-doc.org/en/master/usage/restructuredtext/index.html>`__
and converted to HTML using `sphinx <https://www.sphinx-doc.org/>`__.

To generate the HTML on your development machine::


    user@dev-host:~$ cd pixeldriller
    user@dev-host:~$ sudo apt-get install graphviz
    user@dev-host:~$ python3 -m venv .doc_venv
    user@dev-host:~$ source .doc_venv/bin/activate
    user@dev-host:~$ (.doc_venv) $ pip install .[docs]
    user@dev-host:~$ (.doc_venv) $ cd doc
    user@dev-host:~$ (.doc_venv) $ make clean
    user@dev-host:~$ (.doc_venv) $ make html
    user@dev-host:~$ # To serve:
    user@dev-host:~$ (.doc_venv) $ python3 -m http.server --directory build/html
