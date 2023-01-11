"""
``drill.drill()`` is the main interface. Most interaction with this package
should be through this interface.

"""

import logging
from concurrent import futures

from osgeo import gdal
from pystac_client import Client

from . import drillpoints


def drill(points, images=None,
        stac_endpoint=None, raster_assets=None, collections=None,
        item_properties=None, nearest_n=0, std_stats=None, user_stats=None,
        ignore_val=None, concurrent=False):
    """
    Given a list of drillpoints.Point objects, compute the zonal statistics
    around each point for the specified rasters.

    Parameters
    ----------
    points : list of ``drillpoints.Point`` objects
        Points to drill the specified STAC endpoint or images for.
    images : list of strings
        GDAL-readable list of filenames to drill.
    stac_endpoint : string
        The STAC catalogue's URL.
    raster_assets : sequence of strings
        The raster assets to read from each Item in the STAC catalogue.
    collections : list of strings
        The STAC catalogue's collections to query. You would normally only
        specify one catalogue.
    item_properties : a list of objects
        These are passed to ``pystac-client.Client.search()`` using the
        ``query`` parameter.
    nearest_n : integer
        Only use up to n STAC Items that are nearest-in-time to the ``Point``.
        A value of 0 means use all items found.
    std_stats : sequence of integers
        Constants from the ``drillstats`` module (STATS_MEAN, STATS_STDEV etc)
        defining which 'standard' statistics to extract.
    user_stats : a list of tuples
        A user defined list of statistic names and functions. See the
        notes section below for a description of the function signatures.
    ignore_val : value
        A value to use for the ignore value for rasters. Should only be
        specified when a raster does not have this already set. Either a single
        value (same for all rasters) or one value for each asset.
        TODO: explain how they are used differently for assets versus images.
    concurrent : bool
        If True, will call ``drill.calc_stats()`` for each Item to be drilled
        concurrently in a ``ThreadPoolExecutor``.

    Returns
    -------
    None
        Instead, the Points' ``PointStats`` objects are updated.

    Notes
    -----
    Rasters are specified in one of two ways. You may use either or both.
    The first method is to use ``images``
    parameter to supply a list of paths to rasters. A path is
    any string understood by GDAL. All bands in each image are read.
    
    The second method is to search a STAC endpoint for the raster.
    In this case, you must supply:
    
    - a list of ``raster_assets``
    - preferably, a name of one collection in the STAC catalogue
    - optionally, a list of item properties to filter the search by
    
    ``create_stac_drillers()`` is called to find all STAC items that intersect
    the survey points within their time-window; only up to the
    n nearest-in-time Items are used.

    For each raster, the pixels are drilled and zonal statistics calculated
    using the list of standard stats and user stats.   

    ``std_stats`` is a list of standard stats, as defined in the ``drillstats``
    module with the ``STATS_*`` attributes. To use the standard statistics,
    every raster to be read must be a single-band raster.
 
    ``user_stats`` is a list of (name, function) pairs. The function is used
    to calculate a user-specified statistic.
    The signature of a user-supplied function must be::

        def user_func(array_info, item, pt):

    where:
    
    - array_info is a list of ``image_reader.ArrayInfo`` objects, one element
      for each image/asset read
      meta data about the pixels extracted from each image/asset
    - item is the ``pystac.Item`` object (for STAC rasters) or ImageItem for 
      image. It is part of the
      `PySTAC package <https://pystac.readthedocs.io/>`_
    - pt is the ``drillpoints.Point`` object from around which the pixels
      were extracted

    Each ``ArrayInfo`` instance has a ``data`` attribute that contains a
    3D numpy masked array with the pixel data for the asset defined by the
    instance's ``asset_id`` attribute. But note that each element in
    ``array_info`` corresponds to the ``raster_assets`` passed to ``drill()``.

    The user function must return a value. It can be any data type.
    
    The value(s) returned from the stats functions are stored with the
    ``Point's`` ``stats`` object. See the examples section below for how to
    retrieve them.

    TODO: ``item_properties`` are passed through to
    `pystac_client.Client.search() <https://pystac-client.readthedocs.io>`_.

    TODO: ignore_val is the list of null values for each raster asset (or
    specify one value to be used for all raster assets). It should only be used
    if the null value of the raster is not set or to override it.
    It's used for:
    
    - the mask value when 'removing' pixels from the raw arrays that
      are outside the region of interest, e.g. if the ROI is a circle then
      we remove pixels from the raw rectangular arrays
    - excluding pixels within the raw arrays from the stats calculations,
      those both within and outside the ROI

    See Also
    --------

    example.py: a script that shows two usage patterns

    Examples
    --------

    With the statistics calculated, you retrieve them point-by-point.
    Use the Point's ``stats`` attribute. It is an instance of
    ``drillpoints.PointStats``. It has a ``get_stats()`` function.
    ``get_stats()`` returns a dictionary, keyed by the
    Item's ID. So, the dictionary's length matches the number of Items that
    the Point intersects. For example::

        point_stats = pt.stats.get_stats()
        for item_id, item_stats in point_stats.items():
            print(f"    Item ID={item_id}")
            print(f"        Raw arrays : {item_stats[drillstats.STATS_RAW]}")
            print(f"        Mean values: {item_stats[drillstats.STATS_MEAN]}")
            print(f"        Counts     : {item_stats[drillstats.STATS_COUNT]}")
            print(f"        My Stat    : {item_stats["MY_STAT"]})
    
    A few things to note in this example:
    
    - the std_stats argument passed to ``drill()`` would have been
      ``[drillstats.STATS_MEAN, drillstats.STATS_COUNT]``
    - the user_stats argument defines the 'MY_STAT' statistic and its
      corresponding function name: [('MY_STAT', my_stat_function)]
    - retrieve the numpy masked arrays using the key
      ``drillstats.STATS_RAW``; these are always supplied
    - likewise, retrieve the ArrayInfo object using
      ``drillstats.STATS_ARRAYINFO`` (not shown)
        
    """
    # TODO: Choose the n nearest-in-time items.
    logging.info(f"Searching {stac_endpoint} for {len(points)} points")
    drillers = []
    if stac_endpoint:
        client = Client.open(stac_endpoint)
        stac_drillers = create_stac_drillers(
            client, points, collections, raster_assets=raster_assets,
            item_properties=item_properties)
        drillers.extend(stac_drillers)
    if images:
        image_drillers = create_image_drillers(points, images)
        drillers.extend(image_drillers)
    # Read the pixel data from the rasters and calculate the stats.
    # On completion, each point will contain PointStats objects, with stats
    # stats for each item.
    logging.info(f"The {len(points)} points intersect {len(drillers)} items")
    if concurrent:
        logging.info("Running extract concurrently.")
        with futures.ThreadPoolExecutor() as executor:
            tasks = [
                executor.submit(
                    calc_stats(dr, std_stats=std_stats, user_stats=user_stats))
                for dr in drillers]
    else:
        logging.info("Running extract sequentially.")
        for dr in drillers:
            calc_stats(
                dr, std_stats=std_stats, user_stats=user_stats)


def create_image_drillers(points, images, image_ids=None):
    """
    Return a list of ``drillpoints.ItemDriller`` objects, one for each image
    in the images list.

    Parameters
    ----------
    points : sequence of ``drillpoints.Point`` objects
        Points to drill the image for.
    images : sequence of strings
        GDAL-readable filenames to drill.
    image_ids : sequence of strings
        ID to use for each image. If not specified the image filename is used.

    Returns
    -------
    drillers : list of ``drillpoints.ItemDriller`` objects
        The ItemDriller for each image.

    """
    drillers = []
    if image_ids is None:
        image_ids = [None] * len(images)
    elif len(images) != len(set(image_ids)):
        errmsg = ("ERROR: the number of image IDs must be the same as the " +
                  "number of images and each ID must be unique")
        raise PixelStacError(errmsg)
    for image, image_id in zip(images, image_ids):
        image_item = ImageItem(image, id=image_id)
        driller = drillpoints.ItemDriller(image_item)
        drillers.append(driller)
        ds = gdal.Open(image, gdal.GA_ReadOnly)
        for pt in points:
            if pt.intersects(ds):
                driller.add_point(pt)
    return drillers


def create_stac_drillers(stac_client, points, collections, raster_assets=None,
        item_properties=None, nearest_n=0):
    """
    Search the list of collections in a STAC endpoint for items that
    intersect the x, y coordinate of the list of points and are within the
    Points' temporal search windows.

    Return a list of drillpoints.ItemDriller objects, one for each STAC Item
    found.

    TODO: permit user-defined properties for filtering the stac search.
    
    TODO: implement nearest-n
    
    Parameters
    ----------
    
    stac_client : str or pystac.Client object
        The endpoint URL to the STAC catalogue (str) or the pystac.Client
        object returned from calling ``pystac.Client.open(endpoint_url)``.
    points : list of ``drillpoints.Point`` objects
        Points to drill the endpoint for.
    collections : list of strings
        The names of the collections to query, normally only collection
        is given.
    raster_assets : list of strings, required
        Raster assets to use from the STAC endpoint.
    item_properties : a list of objects, optional
        These are passed to ``pystac-client.Client.search()`` using the
        ``query`` parameter.
    nearest_n : integer
        Only use up to n STAC Items that are nearest-in-time to the ``Point``.
        A value of 0 means use all items found.

    Returns
    -------
    drillers : list of ``drillpoints.ItemDriller`` objects
        Each driller is the ItemDriller for a STAC Item.

    """
    if isinstance(stac_client, str):
        client = Client.open(stac_client)
    else:
        client = stac_client

    drillers = {}
    # TODO: it might be worth optimising the search by clumping points
    # instead of a naive one-point-at-a-time approach.
    for pt in points:
        pt_json = {
            "type": "Point",
            "coordinates": [pt.wgs84_x, pt.wgs84_y]}
        # TODO: permit user-defined properties. For example:
    # Properties can be determined by examining the 'properties' attribute
    # of an item in the collection.
    # e.g. curl -s https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2B_53HPV_20220728_0_L2A | jq | less
    #    tile = '54JVR'
    #    zone = tile[:2]
    #    lat_band = tile[2]
    #    grid_sq = tile[3:]
    #    properties = [
    #        f'sentinel:utm_zone={zone}',
    #        f'sentinel:latitude_band={lat_band}',
    #        f'sentinel:grid_square={grid_sq}']
        # TODO: Do bounding boxes that cross the anti-meridian need to be
        # split in 2, or does the stac-client handle this case?
        # See: https://www.rfc-editor.org/rfc/rfc7946#section-3.1.9
        search = client.search(
            collections=collections,
            max_items=None,  # no limit on number of items to return
            intersects=pt_json,
            limit=500,  # results per page
            datetime=[pt.start_date, pt.end_date],
            query=item_properties)
        items = list(search.items())
        # Group all points for each item together in an ItemDriller.
        for item in items:
            if item.id not in drillers:
                drillers[item.id] = drillpoints.ItemDriller(
                    item, asset_ids=raster_assets)
            drillers[item.id].add_point(pt)
    return list(drillers.values())


def calc_stats(driller, std_stats=None, user_stats=None):
    """
    Calculate the statistics for all points in the ItemDriller objects.
    It reads the rasters and calculates the stats.

    Parameters
    ----------

    driller : a ``drillpoints.ItemDriller``.
        The driller for the Item to be drilled.
    std_stats : sequence of integers
        Constants from the ``drillpoints`` module (STATS_MEAN, STATS_STDEV etc)
        defining which 'standard' statistics to extract.
    user_stats : function
        A list of (stat_name, stat_function) tuples containing the user defined
        function as specified in the ``drill()`` function's docstring.

    """
    msg = "Calculating stats for %i points in item %s."
    logging.info(msg, len(driller.points), driller.item.id)
    driller.read_data()
    driller.calc_stats(std_stats=std_stats, user_stats=user_stats)


class ImageItem:
    """
    Analogous to a ``pystac.Item`` object, use an ``ImageItem`` object
    when constructing ItemDriller objects for an image file.

    Parameters
    ----------
    filepath: str
        Path to the GDAL-readable file.
    id:
        An optional ID for the ImageItem. If not given, filepath is used.

    Attributes
    ----------
    filepath : string
        Path to the GDAL file
    id : String
        ID to use for this item. Is the same as filepath unless overridden.

    """
    def __init__(self, filepath, id=None):
        """
        Construct the ImageItem. If id is None, then set the id attribute
        to filepath.

        """
        self.filepath = filepath
        if id:
            self.id = id
        else:
            self.id = filepath


class PixelStacError(Exception):
    pass
