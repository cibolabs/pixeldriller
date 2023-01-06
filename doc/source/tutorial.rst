Tutorial
==============================

You have collected on-ground measurements of a metric
of interest at multiple field sites.
You now want to extract pixels from satellite
or aerial images acquired over the field sites. And you want to
calculate one or more statistics on the extracted pixel values for each site.

This tutorial guides you through a typical usage pattern to do so.
A complete example is provided in ``pixdrill/example.py``.

The typical usage pattern
==============================

#. Specify the locations and acquisition windows of your field surveys
#. Create Drillers for the items to be drilled
#. Define the statistics to be calculated on the drilled pixels
#. Extract the pixels and compute the statistics
#. Fetch the results

Define the locations and windows of the field surveys
-----------------------------------------------------

Use the ``pixdrill.drillpoints.Point`` class to model the properties of
the pixel extraction you want to do for each field site. The properties are the:
- location of your field site defined by a coordinate and a coordinate reference system
- the extraction region of interest, which will resemble that of your field site
- date of the field survey
- time range, either side of the field survey date, of the imagery acquisition

Example::

    from pixdrill import drill
    from pixdrill import drillpoints

    # Create the first point.
    longitude = 140
    latitude = -36.5
    crs_code = 4326 # EPSG code for WGS84 coordinate reference system. See epsg.org.
    survey_date = datetime.datetime(2022, 7, 28) # 28 July 2022
    acquisition_window = datetime.timedelta(days=3)
    site_shape = drill_points.ROI_SHP_CIRCLE # Define the extraction shape
    site_radius = 50 # The extraction size, in metres
    pt_1 = drillpoints.Point(
        longitude, latitude, survey_date, crs_code,
        acquisition_window, site_radius, site_shape)

    # Create extra points.
    ...

    # Add the points to a list, ready for extraction.
    points = [pt_1, ...]

    # Extract pixels and run stats - only the points argument is shown for the time being
    drill.drill(points, ...)

Choose the images
------------------------------

Specify the images to extract pixels from using one or both of the following methods:

#. provide a list of file paths or URLs
#. use the *Items* returned from a search of a STAC_ catalogue

``Pixel Driller`` uses `GDAL <https://gdal.org/>`__ to read the images. So the
file paths or URLs must be in a form that GDAL can parse.

STAC_ makes ``Pixel Driller`` powerful.
Consider this: you have hundreds of field sites and, depending on your acquisition
window and satellite revisit period, a search of a STAC_ catalogue returns
thousands of images to drill. This is clearly better than having to specify
these yourself in a list.

If using a STAC_ catalogue, we assume that you are familiar
with the properties of that catalogue. In particular:
- the *endpoint* (a URL) to the STAC_ catalogue
- the names of the *collections* in the catalogue; a collection is typically
a grouping of similar images, such as Sentinel-2 Level 2A
- the names of the STAC_ *Item's* raster *assets* that you want to drill; note that
a list of STAC_ *Items* is returned from a search, and the set of *asset* IDs
is the same for every *Item* in a collection

Continuing our example::

    # Specify paths to the images to be drilled.
    img1 = "/path/to/img1.tif"
    img2 = "/path/to/img2.tif"

    # Specify the collection and raster assets of the Items in a STAC catalogue
    endpoint = "https://earth-search.aws.element84.com/v0"
    collections = ['sentinel-s2-l2a-cogs']
    assets = ['B02', 'B11']

    # Extract the pixels and run stats
    drill.drill(
        points, images=[img1, img2],
        stac_endpoint=endpoint, raster_assets=assets, collections=collections,
        ...)

**How do I find the STAC collection and its Items' asset names?**

Hopefully they are documented by the publisher of the STAC_ catalogue.
You may also like to inspect the catalogue using
a `STAC Browser <https://radiantearth.github.io/stac-browser/>`__.

.. _STAC: https://stacspec.org

Define the statistics
------------------------------

A point will be found to intersect one or more of the images that you supply,
or one or more of the STAC_ *Items* returned from a catalogue search.

Statistics are calculated from the pixels extracted around the point from each
image and each STAC_ *Item*.

Use one or both of the following methods to specify the statistics to be calculated:

#. use the built-in, *standard statistics*
#. define your own *user statistics*

Standard statistics
~~~~~~~~~~~~~~~~~~~~

The standard statistics are defined in the ``pixdrill.drillstats`` module.
Use the ``STATS_`` symbols when specifying them. For example, to calculate
the mean and standard deviation of each raster::

    from pixdrill import drillstats
    ...

    std_stats = [drillstats.STATS_MEAN, drillstats.STATS_STDEV]

    drill.drill(
        points, images=[img1, img2],
        stac_endpoint=endpoint, raster_assets=assets, collections=collections,
        std_stats=std_stats, ...)

There is a limitation on the use of standard statistics. The underlying
functions assume that each drilled image is a single-band raster.
So, in our example ``img1`` and ``img2`` contain only one band.
Likewise, the STAC_ assets ``B02`` and ``B11`` contain only one band.

If one of your images contains multiple bands you will have to write your
own functions to calculate statistics.

User statistics
~~~~~~~~~~~~~~~~~~~

The standard statistics are quite limited. So you may need to write your own
functions to calculate the statistics (model predictors) that you require.

Your function must have the following signature::

    def my_func(array_info, item, point):

Where:

- ``array_info`` is a list of ``image_reader.ArrayInfo`` instances
- ``item`` is an instance of ``drill.ImageItem`` for a user-supplied image,
  or an instance of `pystac Item`_ for a STAC_ *Item*.
- point is one of the Point objects that you defined

The ``array_info`` list contains:

- one element if the data were extracted from a user-supplied image
- an element for every asset name given if the data were extracted from a STAC_ *Item*

An ``image_reader.ArrayInfo`` instance contains these properties:

- ``data``: a 3D numpy_ masked array (``numpy.ma.masked_array``) containing the
  pixel values read from the image or item asset
- ``asset_id``: the asset name
- and other attributes that define the location of the array within the
  image it was extracted from (see the docs for ``image_reader.ArrayInfo``)

In the following example we want to know the range (max-min) of all pixel
values. It returns a list with one element when the ``item`` is
``img1`` or ``img2``. And a list with two elements (one each for ``B02`` and ``B11``)
when ``item`` is a `pystac Item`_::

    def user_range(array_info, item, pt):
        return [a_info.data.max() - a_info.data.min() for a_info in array_info]

    # For user stats, supply a list of (stat_name, stat_func) tuples.
    # The name is used as a reference to retrieve the data later.
    user_stats = [("MY_RANGE", user_range)]

    drill.drill(
        points, images=[img1, img2],
        stac_endpoint=endpoint, raster_assets=assets,
        collections=collections,
        std_stats=std_stats, user_stats=user_stats)

.. _pystac Item: https://pystac.readthedocs.io/en/stable/api/pystac.html#pystac.Item

.. _numpy: https://numpy.org/

Extract the pixels and calculate the stats
------------------------------------------

This is done by ``drill.drill()``.

Fetch the results
------------------------------

``Pixel Driller`` stores the statistics for each field site with the corresponding
``drillpoints.Point`` object. They are accessed using the Point's ``stats`` attribute.
``stats`` is an instance of the ``drillstats.PointStats`` class.
Use ``drillstats.PointStats.get_stats()`` to access the statistics for
all items::

    # The stats.
    std_stats = [drillstats.STATS_MEAN, drillstats.STATS_STDEV]
    user_stats = [("MY_RANGE", user_range)]

    # Extract pixels and calc stats.
    drill.drill(
        points, images=[img1, img2],
        stac_endpoint=endpoint, raster_assets=assets,
        collections=collections,
        std_stats=std_stats, user_stats=user_stats)

    # Fetch the results.
    for pt in points:
        print(f"Stats for point: x={pt.x}, y={pt.y}")
        for item_id, item_stats in pt.stats.get_stats().items():
            print(f"    Item ID={item_id}")
            print(f"        Mean values: {item_stats[drillstats.STATS_MEAN]}")
            print(f"        Std dev    : {item_stats[drillstats.STATS_STDEV]}")
            print(f"        Ranges     : {item_stats['MY_RANGE']}")

For ``pt_1`` in our example, this gives the following output::

    Stats for point: x=140, y=-36.5:
        Item ID=S2A_54HVE_20220730_0_L2A
            Asset IDs  : ['B02', 'B11']
            Mean values: [3257.65289256 2369.75]
            Std dev    : [25.58754564 10.98578627]
            Ranges     : [164, 37]
        Item ID=S2B_54HVE_20220725_0_L2A
            Asset IDs  : ['B02', 'B11']
            Mean values: [3945.52066116 3198.11111111]
            Std dev    : [200.69515962 167.57366171]
            Ranges     : [1064, 779]
        Item ID=/path/to/img1.tif
            Asset IDs  : [None]
            Mean values: [60.]
            Std dev    : [0.]
            Ranges     : [0]
        Item ID=/path/to/img2.tif
            Asset IDs  : [None]
            Mean values: [1782.]
            Std dev    : [0.]
            Ranges     : [0]

Note that:

- two STAC_ *Items* were found that matched the Point's location and imagery acquisition window
- the call to ``pt.stats.get_stats()`` (with no parameters) returns a dictionary
  keyed by the item_id whose values are another dictionary, which is keyed
  by the statstic name
- the standard statistics are retrieved using the ``drillstats.STATS_`` symbols
- the user statistcs are retrieved using the user-defined name

A note about null pixel values
------------------------------

By default, ``Pixel Driller`` uses the image's *no data* value to define
pixels that are excluded from the stats calculations. This can be
changed using the ``ignore_val`` parameter in ``drill.drill()``.

An alternative usage pattern
------------------------------

Consider this: a STAC_ *Item* has raster *assets* that contain continuous
(e.g. surface reflectance) and categorical (e.g. a scene classification) data.
You want to calculate the mean and standard deviation of the pixels in the
continuous assets, and user-defined statistics for the categorical assets.

This is achieved by reading the data, calculating the statistics, and 
fetching the results for the continuous assets separately to the
categorical assets.

Example::

    # Create your points.
    points = create_points()

    # Find the STAC Items that each point intersects. This is done in
    # drill.create_stac_drillers(), which return a list of 
    # drillpoints.ItemDriller objects, one for each STAC Item.
    drillers = drill.create_stac_drillers(stac_endpoint, points, collections)

    # Loop over each driller, reading the data and
    # calculating statistics on the continuous assets.
    for drlr in drillers:
        drlr.set_asset_ids(['B02', 'B11'])
        drlr.read_data()
        std_stats = [drillstats.STATS_MEAN, drillstats.STATS_STD]
        drlr.calc_stats(std_stats=std_stats)
    # Fetch the stats
    for pt in points:
        stats_dict = pt.stats.get_stats()
        # do something
        ...
        # then reset the stats, ready for the next extract
        pt.stats.reset()

    # Repeat, but this time for a categorical asset.
    for drlr in drillers:
        drlr.set_asset_ids(['SCL'])
        drlr.read_data()
        std_stats = [drillstats.STATS_COUNT]
        user_stats = [("MY_STAT_1", my_func_1), ("MY_STAT_2", my_func_2)]
        drlr.calc_stats(std_stats=std_stats, user_stats=user_stats)
    # Fetch the stats
    for pt in points:
        stats_dict = pt.stats.get_stats()
        # do something
        ...
        # then reset the point's stats, ready for the next extract
        pt.stats.reset()

    # And so on.
