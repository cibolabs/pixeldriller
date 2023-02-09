.. pixeldriller documentation master file, created by
   sphinx-quickstart on Mon Dec 12 10:40:51 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Pixel Driller
========================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Introduction
------------

Pixel Driller is for those who:

- want to extract pixels from locations in an image
- calculate statistics on the extracted pixels
- are comfortable using Python

For example, you might be someone who:

- works in the field of remote sensing
- takes measurements of *something* on the ground, and
- creates statistical or machine learning models to predict that *something*
  from satellite or aerial images


What it does
-----------------------------

Pixel Driller extracts pixels from images acquired over your field sites and
runs statistics on them. You would use those statistics as predictors in your
machine learning models.

It handles the following use cases:

- Given a STAC endpoint, set of X-Y-Time points, and a buffer, return the
  n nearest-in-time zonal stats for all bands of the specified raster assets
  about each point
- Given a list of images, a set of X-Y points, and a buffer, return the
  zonal stats for the bands in each image about each point

Features
----------

- Extract from images by specifying a file path or URL
- Extract from images by searching a STAC catalogue
- Extract from STAC images up to *n* days either side of the field survey date
- Specify the size and shape of the extraction area for each field site
- Use in-built functions for calculating statistics or define your own

Example
---------


:meth:`pixdrill.drill.drill` is the main interface. However, several data
structures and functions must be created before using it. The following example
shows a typical usage pattern::

    import datetime
    from pixdrill import drill
    from pixdrill import drillpoints
    from pixdrill import drillstats

    # Step 1. Specify the field survey properties.
    # Specify the locations of your field surveys.
    # For STAC Items, you also specify the image acquisition period
    # either side of the field survey date. Pixels are extracted
    # from images that contain the point, and within the acquisition period
    # for STAC Items.
    points = []
    longitude = 140
    latitude = -36.5
    crs_code = 4326 # EPSG code for WGS84 coordinate reference system. See epsg.org.
    date = datetime.datetime(2022, 7, 28)  # 28 July 2022
    t_delta = datetime.timedelta(days=3)   # 3 days either side
    site_shape = drill_points.ROI_SHP_CIRCLE  # Define the extraction shape
    site_radius = 50  # In metres
    pt_1 = drillpoints.Point(
        longitude, latitude, date, crs_code, t_delta, site_radius, site_shape)
    points.append(pt_1)
    # Add additional points for each field site
    ...

    # Step 2. Choose the images and STAC Items to be drilled.
    # Firstly, the image paths.
    img1 = "/path/to/img1.tif"
    img2 = "/path/to/img2.tif"
    # Secondly, the STAC catalogue and raster assets of the STAC Items.
    endpoint = "https://earth-search.aws.element84.com/v0"
    collections = ['sentinel-s2-l2a-cogs']
    assets = ['B02', 'B11']

    # Step 3. Define statistics.    
    # Select from standard, in-built statistics or define your own.
    # They are run on the pixels extracted from the images for all your
    # field sites. See the tutorial for how to specify and define the
    # stats functions.
    std_stats = [drillstats.STATS_MEAN]
    user_stats = [('MY_RANGE', my_range_func)]

    # Step 4. Extract pixels and compute stats.
    # Drill the given images and those returned from a search of
    # the STAC catalogue. Calculate the stats at the same time.
    drill.drill(
        points, images=[img1, img2],
        stac_endpoint=endpoint, raster_assets=assets,
        collections=collections,
        std_stats=std_stats, user_stats=user_stats)
    
    # Step 5. Fetch results.
    # Retrieve the results using each Point's 'stats' attribute (a dictionary).
    for pt in points:
        print(f"Stats for point: x={pt.x}, y={pt.y}")
        for item_id, item_stats in pt.stats.get_stats().items():
            print(f"    Item ID={item_id}")
            print(f"        Mean values: {item_stats[drillstats.STATS_MEAN]}")
            print(f"        Ranges     : {item_stats['MY_RANGE']}")

The example creates the following output for the first point. Note that
two Items in the STAC catalogue were found 3 days either side of
the field-survey's date of 28 July 2022. Data were extracted for the 'B02'
and 'B11' assets of these items, thus *Mean values* and *Ranges* contain two values.
Contrast that with the results for 'img1.tif' and 'img2.tif', which are
single-band rasters.::
    
    Stats for point: x=140, y=-36.5:
        Item ID=S2A_54HVE_20220730_0_L2A
            Mean values: [3257.65289256 2369.75]
            Ranges     : [164, 37]
        Item ID=S2B_54HVE_20220725_0_L2A
            Mean values: [3945.52066116 3198.11111111]
            Ranges     : [1064, 779]
        Item ID=/path/to/img1.tif
            Mean values: [60.]
            Ranges     : [0]
        Item ID=/path/to/img2.tif
            Mean values: [1782.]
            Ranges     : [0]


Download
---------

`Releases <https://github.com/cibolabs/pixeldriller/releases>`__
and
`Source code <https://github.com/cibolabs/pixeldriller>`__
from Github.


Installation
-------------

The package requires `pystac-client <https://pystac-client.readthedocs.io/>`__,

The package requires :doc:`pystac-client <pystacclient:index>,
`numpy <https://numpy.org/>`__ and `GDAL <https://gdal.org/>`__.

All packages are available from the conda-forge archive.

They may also be available from your platform's package manager.

Alternatively the `GDAL python bindings <https://pypi.org/project/GDAL/>`__
are available on `pypi <https://pypi.org/>`__. But libgdal must be installed
first. You might use your platform's package manager to install GDAL and
its bindings instead. For example, on Ubuntu::


    > sudo apt-get install -y python3-gdal gdal-bin`


pystac-client and numpy are also available from `pypi <https://pypi.org/>`__,
and are installed when installing Pixel Driller::

    > pip install https://github.com/cibolabs/pixeldriller/archive/refs/tags/v0.2.0.tar.gz

Guides
=======

.. toctree::
   :maxdepth: 1

   tutorial
   developer_guide
   api

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
