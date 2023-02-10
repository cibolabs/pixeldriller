Developer Guide
===============

This guide provides developers with an overview of Pixel Driller's
concepts and design.

It should be read in conjunction with the :doc:`tutorial`.

Package design
---------------


``pixdrill`` is the top-level package. The Python modules and classes
in ``pixdrill`` are shown in the following class diagram as dark grey boxes.

The package leans on :doc:`pystac-client <pystacclient:index>`,
:doc:`pystac <pystac:index>`, :doc:`numpy <numpy:index>` and
`GDAL <https://gdal.org/>`__.
The main classes in these packages that ``Pixel Driller`` interfaces with
are shown in the diagram as white boxes.

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

- a path or URL to an image, represented by a :class:`pixdrill.drill.ImageItem`
- parameters for searching for images in a STAC catalogue,
  the results of which are represented by :class:`pystac:pystac.Item` objects

In the diagram, ``Item`` is a conceptual abstraction of
:class:`~pixdrill.drill.ImageItem` and :class:`pystac:pystac.Item`.
It has no corresponding software component. All ``Items`` have an
``id`` attribute and a way to access the file paths or URLs to the
underlying image or images.

The main difference between an :class:`~pixdrill.drill.ImageItem` and a
:class:`pystac:pystac.Item` is the number
of images associated with them. An :class:`~pixdrill.drill.ImageItem`
has only one image.
A :class:`pystac:pystac.Item` can have one or more images; each
a :class:`pystac:pystac.Asset`.

``Pixel Driller`` delegates image reading to `GDAL <https://gdal.org/>`__.
GDAL represents an image as a ``Dataset``.
An image is composed of one or more bands. Each band is a two-dimensional
numpy array of pixels.

Where and what to drill
~~~~~~~~~~~~~~~~~~~~~~~

A Survey :class:`~pixdrill.drillpoints.Point` determines the location
of the pixels within an image to extract.

For :class:`Image Items <pixdrill.drill.ImageItem>`, the user supplies the
paths or URLs to the images they want drilled.
The Survey :class:`Point's <pixdrill.drillpoints.Point>` date is not used.

For :class:`STAC Items <pystac:pystac.Item>`, ``Pixel Driller`` uses the images
returned from searching a ``STAC Catalogue`` with the user-supplied
parameters, including:

- the ``STAC Catalogue`` and *collections* specified
- the locations of the Survey :class:`Points <pixdrill.drillpoints.Point>`
- the image acquisition-window for each Survey
  :class:`<pixdrill.drillpoints.Point>`

Drilling
~~~~~~~~~

The :mod:`pixdrill.drill` module contains functions for drilling or creating
the :class:`Driller <pixdrill.drillpoints.ItemDriller>`
objects to do so.
A :class:`Driller <pixdrill.drillpoints.ItemDriller>` contains:

- the ``Item`` to be drilled
- a collection of Survey :class:`Points <pixdrill.drillpoints.Point>`
  that intersect the ``Item``
- a function for reading the pixel data for every
  :class:`~pixdrill.drillpoints.Point` from the ``Item's`` images
- a function for calculating the statistics for every
  :class:`~pixdrill.drillpoints.Point`

:class:`Driller <pixdrill.drillpoints.ItemDriller>`
delegates the responsibility of reading the pixels from an
image to an :class:`Image Reader <pixdrill.image_reader.ImageReader>` object.
It also delegates responsibility for computing statistics to each
:class:`Point's <pixdrill.drillpoints.Point>`
:class:`Stats <pixdrill.drillstats.PointStats>` object.
Thus :class:`Drillers <pixdrill.drillpoints.ItemDriller>` indirectly populate
each :class:`Point's <pixdrill.drillpoints.Point>` survey statistics.

Statistics
~~~~~~~~~~

Each :class:`~pixdrill.drillpoints.Point` stores its pixel data and
statistics in a :class:`pixdrill.drillstats.PointStats` object.
A Point might intersect multiple ``Items``, so the
:class:`~pixdrill.drillstats.PointStats` object stores the pixel data and
statistics for every Item.

Pixel data and statistics are stored in the ``PointStats.item_stats``
dictionary, keyed by the ``Item's`` ID. Each item in the dictionary is
another dictionary containing elements for:

- the *raw* pixel data, a :ref:`masked array <numpy:maskedarray>`
- information about the array of pixels read from the image, an instance
  of :class:`pixdrill.image_reader.ArrayInfo`
- the statistics, the data types of which are those returned from the functions
  used to compute the statistics


**Standard statistics**

:mod:`pixdrill.drillstats` contains built-in functions for computing
a suite of standard statistics. These functions take a list of
3D :ref:`masked arrays <numpy:maskedarray>`. Each array contains the
pixels extracted for a :class:`~pixdrill.drillpoints.Point` for one image.
The standard stats functions assume that each image contains only one band.
So the shape of each array passed to the built-in functions must be
``(1, nrows, ncols)``.

For an :class:`~pixdrill.drill.ImageItem`, the array list passed to a
built-in function contains only one array. For a
:class:`pystac:pystac.Item` the list contains an array for every
:class:`pystac:pystac.Asset` drilled.

**User statistics**

Users can write custom functions to calculate statistics. The
:ref:`Tutorial <tutorial:user statistics>` describes the signature of a 
user's statistics function and the objects that ``Pixel Driller`` passes to it.

The user also provides a name for their function. ``Pixel Driller`` calls each
user function and stores the value returned from the function
in the :class:`~pixdrill.drillstats.PointStats` object.
For example, from
:func:`PointStats.calc_stats() <pixdrill.drillstats.PointStats.calc_stats>`::

    stats = self.item_stats[item_id]  # Dictionary of stats for the Item
    ...

    # user_stats is a list of tuples as supplied by the user. Each tuple
    # contains the name of the statistic (a string) and the function
    # that calculates it.
    for stat_name, stat_func in user_stats:
        stats[stat_name] = stat_func(stats[STATS_ARRAYINFO], item, self.pt)

``Pixel Driller`` passes all the information it thinks the user needs to
calculate a statistic.

``stats[STATS_ARRAYINFO]`` is the
:class:`pixdrill.image_reader.ArrayInfo` object, which contains:

- the pixel data, in the ``data`` attribute
- the asset id, in the ``asset_id`` attribute
- plus the location of the pixels within the image it was read from

``item`` is the :class:`pystac:pystac.Item` or
:class:`~pixdrill.drill.ImageItem`. The user can inspect its
properties, such as its `id` attribute.

``self.pt`` is the :class:`~pixdrill.drillpoints.Point` object,
so the user knows which point is being operated on. The user can pass
additional information to the user function as
:class:`~pixdrill.drillpoints.Point` attributes with Python's
built-in :func:`python:setattr` and :func:`python:getattr` functions.

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

The details are in :func:`pixdrill.drillpoints.Point.change_buffer_units`.


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
all existing tests pass. Tests are located in the ``tests/`` directory.
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
Documentation is in the ``doc/`` directory. Consider modifying the
tutorial or developer guide. Docs are written in
`restructured text <https://www.sphinx-doc.org/en/master/usage/restructuredtext/index.html>`__
and converted to HTML using `sphinx <https://www.sphinx-doc.org/>`__.

To generate the HTML on your development machine::


    user@dev-host:~$ cd pixeldriller
    user@dev-host:~$ sudo apt-get install graphviz
    user@dev-host:~$ python3 -m venv .doc_venv
    user@dev-host:~$ source .doc_venv/bin/activate
    user@dev-host:~$ (.doc_venv) $ pip install -e .[docs]
    user@dev-host:~$ (.doc_venv) $ cd doc
    user@dev-host:~$ (.doc_venv) $ make clean
    user@dev-host:~$ (.doc_venv) $ make html
    user@dev-host:~$ # To serve:
    user@dev-host:~$ (.doc_venv) $ python3 -m http.server --directory build/html
