.. pixeldriller documentation master file, created by
   sphinx-quickstart on Mon Dec 12 10:40:51 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Pixel Driller
========================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

**Should I use Pixel Driller?** Maybe, if you:

- work in the field of remote sensing
- take measurements of *something* on the ground, and
- create statistical or machine learning models to predict that *something*
  from satellite or aerial images
- are comfortable using Python

**What does Pixel Driller do?**

It extracts pixels from images acquired over your field sites and runs statistics
on them, which you want to use as model predictors.

**What are the features?**

- Extract from images by specifying a file path or URL
- Extract from images by searching a STAC catalogue
- Extract from STAC images up to *n* days either side of the field survey date
- Specify the size and shape of the extraction area for each field site
- Use in-built functions for calculating statistics or define your own

**Example**

``pixdrill.drill.drill()`` is the main interface. However, several data structures
and functions must be created before using it. The following example is
a typical usage pattern::

    import datetime
    from osgeo import osr
    from pixdrill import drill
    from pixdrill import drillpoints
    from pixdrill import drillstats

    # Prepare your points. Each represents a field site.
    # Each field site was surveyed on a specific day and covers a
    # region of interest. You may want to extract pixels from all images
    # that were acquired close to the field survey's date.
    points = []
    longitude = 140
    latitude = -36.5
    sp_ref = osr.SpatialReference() # The point's coordinate reference system
    sp_ref.ImportFromEPSG(4326) # WGS84
    # Field survey on 28 July 2022, and you want to 
    # drill images in a STAC catalogue acquired up to 3 days either side of date
    date = datetime.datetime(2022, 7, 28)
    t_delta = datetime.timedelta(days=3)
    site_shape = drill_points.ROI_SHP_CIRCLE # Define the extraction shape
    site_radius = 50 # In metres
    pt_1 = drillpoints.Point(
        longitude, latitude, date, sp_ref, t_delta, site_radius, site_shape)
    points.append(pt_1)
    # Add additional points for each field site
    ...

    # Specify paths to images to be drilled.
    img1 = "/path/to/img1.tif"
    img2 = "/path/to/img2.tif"

    # Specify the STAC catalogue and raster assets of the STAC Items.
    endpoint = "https://earth-search.aws.element84.com/v0"
    collections = ['sentinel-s2-l2a-cogs']
    assets = ['B02', 'B11']
    
    # Select from standard, in-built statistics or define your own.
    # They are run on the pixels extracted from the images for all your
    # field sites. See the tutorial for details.
    std_stats = [drillstats.STATS_MEAN]
    user_stats = [('MY_RANGE', my_range_func)]

    # Drill the given images and those found in the STAC catalogue,
    # and calculate the stats.
    drill.drill(
        points, images=[img1, img2],
        stac_endpoint=endpoint, raster_assets=assets,
        collections=collections,
        std_stats=std_stats, user_stats=user_stats)
    
    # Retrieve the results using each Point's 'stats' attribute.
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


Guides
=======

.. toctree::
   :maxdepth: 1

   tutorial
   developer_guide

Installation
============

To install, do...

Python Module Reference
=======================

.. toctree::
   :maxdepth: 1
   
   pixdrill_drill
   pixdrill_drillpoints
   pixdrill_drillstats
   pixdrill_image_reader

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
