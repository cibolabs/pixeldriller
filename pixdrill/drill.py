"""
``drill.drill()`` is the main interface. Most interaction with this package should
be through this interface.

Assumptions:

- Uses GDAL's /vsicurl/ file system handler for online resources that do
  not require authentication
- The file server supports range requests
- If you want to calculate standard statistics then each STAC Item's asset
  must or raster image must contain only one band

It depends on:

- pystac-client for searching a STAC endpoint
- osgeo.gdal for reading rasters
- osgeo.osr for coordinate transformations
- numpy for standard stats calcs

"""

import logging
from concurrent import futures

from osgeo import gdal
from pystac_client import Client

from . import drillpoints
from . import drillstats

class PixelStacError(Exception): pass

def drill(
    points, images=None,
    stac_endpoint=None, raster_assets=None, collections=None, item_properties=None,
    nearest_n=1, std_stats=None, user_stats=None, ignore_val=None,
    concurrent=False):
    """
    Given a list of drillpoints.Point objects, compute the zonal statistics for
    the specified rasters.
    
    Rasters are specified in one of two ways. Firstly, use the images
    argument to supply a list of paths to rasters. In this case a path may be
    any string understood by GDAL. All bands in each raster will be read.
    
    The second method of specifying rasters is to search a STAC endpoint for them.
    In this case, you must also supply a list of raster_assets, and optionally
    a list of collection names in the STAC catalogue and a list of item properties
    to filter the search by. stac_search() is called to find all STAC items
    that intersect the survey points within their time-window; but only the
    n nearest-in-time Items are used.

    For each raster, the pixels are drilled and zonal statistics calculated
    using the list of standard stats and user stats.

    The statistics are stored with the Point object, retrievable using the
    Point class's get_stats() or get_item_stats() functions.

    See example.py for typical example usage.

    Familiarise yourself with the concepts of a Point's region of interest and
    temporal window by reading the drillpoints.Point documentation.

    std_stats is a list of standard stats defined in the drillstats module
    with the STATS_* attributes. To use the standard statistics,
    every raster to be read must be a single-band raster.
 
    user_stats is a list of (name, function) pairs. The function is used
    to calculate a user-specified statistics.
    The signature of a user-supplied function must be::

        def user_func(array_info, item, pt):

    where:
    
    - array_info is a list containing the data and meta data about the pixels
      extracted from each asset; each element is an instance of
      asset_reader.ArrayInfo
    - item is the pystac.Item object (for STAC rasters) or ImageItem for 
      image. pystac.Item is part of the PySTAC package.
    - pt is the drillpoints.Point object from around which the pixels
      were extracted

    Each ArrayInfo instance has a data attribute that contains a 3D numpy
    masked array with the pixel data for the asset defined by the instance's
    asset_id attribute. But note that each element in array_info corresponds
    to the raster_assets passed to drill().

    The user function must return a value. It can be any data type.
    The returned value is stored with the point without modification.

    With the statistics calculated, you retrieve their values point-by-point.
    The Point's ``stats`` attribute is a ``PointStats`` object with a
    ``get_stats()`` function. The function returns a dictionary, keyed by the
    Item's ID. So, the dictionary's length matches the number of Items that
    the Point intersects. For example::

        point_stats = pt.stats.get_stats()
        for item_id, item_stats in point_stats.items():
            print(f"    Item ID={item_id}")
            print(f"        Raw arrays : {item_stats[drillstats.STATS_RAW]}")
            print(f"        Mean values: {item_stats[drillstats.STATS_MEAN]}")
            print(f"        Counts     : {item_stats[drillstats.STATS_COUNT]}")
            print(f"        Null Counts: {item_stats[drillstats.STATS_COUNTNULL]}")
            print(f"        My Stat    : {item_stats["MY STAT"]})

    A few things to note in this example:
    
    - the std_stats argument passed to ``drill()`` would have been
      [drillstats.STATS_MEAN, drillstats.STATS_COUNT, drillstats.STATS_COUNTNULL]
    - the user_stats argument defines the 'MY_STAT' statistic and its
      corresponding function name: [('MY_STAT', my_stat_function)]
    - retrieve the numpy masked arrays using the key ``drillstats.STATS_RAW``;
      these are always supplied
    - likewise, retrieve the ArrayInfo object using ``drillstats.STATS_ARRAYINFO``

    Additional implementation details.

    endpoint is passed to pystac_client.Client.Open.

    TODO: properties are passed through to pystac_client.Client.search
    https://pystac-client.readthedocs.io/en/stable/api.html

    TODO: ignore_val is the list of null values for each raster asset (or specify one
    value to be used for all raster assets). It should only be used if the
    null value of the raster is not set or to override it. It's used for:
    
    - the mask value when 'removing' pixels from the raw arrays that
      are outside the region of interest, e.g. if the ROI is a circle then
      we remove pixels from the raw rectangular arrays
    - excluding pixels within the raw arrays from the stats calculations,
      those both within and outside the ROI
      
      
    Parameters
    ----------
    points : sequence of ``drillpoints.Point`` objects
        Points to drill the specified STAC endpoint/rasters for
    images : sequence of strings
        GDAL understood filenames to also drill in
    stac_endpoint : string
        A URL that represents a STAC endpoint
    raster_assets : sequence of strings
        Raster assets to use from the SATC endpoint
    collections : sequence of strings
        Collections to query provided by the STAC endpoint
    item_properties : ?
        Some sort of object to pass to stac-client?
    nearest_n : integer
        How many of the nearest matching records to use
    std_stats : sequence of integers
        Constants from the ``drillstats`` module (STATS_MEAN, STATS_STDEV etc)
        defining which 'standard' statistics to extract
    user_stats : function
        A user defined function as specified above
    ignore_val : value
        A value to use for the ignore value for rasters. Should only be specified
        when a raster does not have this already set. Either a single value (same 
        for all rasters) or one value for each asset.
    concurrent : bool
        Whether to process the assets concurrently
        
    """
    # TODO: Choose the n nearest-in-time items.
    logging.info(f"Searching {stac_endpoint} for {len(points)} points")
    item_points = []
    if stac_endpoint:
        client = Client.open(stac_endpoint)
        stac_item_points = assign_points_to_stac_items(
            client, points, collections, raster_assets)
        item_points.extend(stac_item_points)
    if images:
        image_item_points = assign_points_to_images(points, images)
        item_points.extend(image_item_points)
    # Read the pixel data from the rasters and calculate the stats.
    # On completion, each point will contain PointStats objects, with stats
    # stats for each item.
    logging.info(f"The {len(points)} points intersect {len(item_points)} items")
    if concurrent:
        logging.info("Running extract concurrently.")
        with futures.ThreadPoolExecutor() as executor:
            # TODO: raster_assets ought to be optional.
            tasks = [executor.submit(
                calc_stats(
                    ip, std_stats=std_stats, user_stats=user_stats)) \
                    for ip in item_points]
    else:
        logging.info("Running extract sequentially.")
        for ip in item_points:
            calc_stats(
                ip, std_stats=std_stats, user_stats=user_stats)


def assign_points_to_images(points, images, image_ids=None):
    """
    Return a list of drillpoints.ItemPoints collections, one for each image
    in the images list.

    A point will be added to an ItemPoints collection if it intersects the Item.
    An ImageItem is also added to the point.

    Parameters
    ----------
    points : sequence of ``drillpoints.Point`` objects.
        Points to drill the image for.
    images : sequence of strings.
        GDAL understood filenames to drill.
    image_ids : sequence of strings.
        ID to use for each image. If not specified the image filename is used.

    Returns
    -------
    item_points : list of ``drillpoints.ItemPoints`` objects
        The ItemPoints for each Item.

    """
    item_points = []
    if image_ids is None:
        image_ids = [None] * len(images)
    elif len(images) != len(set(image_ids)):
        errmsg = ("ERROR: the number of image IDs must be the same as the " +
                  "number of images and each ID must be unique")
        raise PixelStacError(errmsg)
    for image ,image_id in zip(images, image_ids):
        image_item = ImageItem(image, id=image_id)
        ip = drillpoints.ItemPoints(image_item)
        item_points.append(ip)
        ds = gdal.Open(image, gdal.GA_ReadOnly)
        for pt in points:
            if pt.intersects(ds):
                ip.add_point(pt)
                pt.add_items([image_item])
    return item_points


def assign_points_to_stac_items(
    stac_client, points, collections, raster_assets=None):
    """
    Search the list of collections in a STAC endpoint for items that
    intersect the x, y coordinate of the list of points and are within the
    Points' temporal search windows.

    stac_client is the pystac.Client object returned from calling
    pystac.Client.open(endpoint_url).
    
    If no collections are specified then search all collections in the endpoint.

    Link each Point with its pystac.Items, and create a drillpoints.ItemPoints
    collection for every item.

    Return the list of drillpoints.ItemPoints collections.

    TODO: permit user-defined properties for filtering the stac search.
    
    Parameters
    ----------
    
    stac_client : pystac.Client object
        Returned from calling pystac.Client.open(endpoint_url)
    points : sequence of ``drillpoints.Point`` objects
        Points to drill the endpoint for
    collections : sequence of strings
        Collections to query provided by the STAC endpoint
    raster_assets : sequence of strings
        Raster assets to use from the SATC endpoint

    Returns
    -------
    item_points : list of ``drillpoints.ItemPoints`` objects
        The ItemPoints for each image

    """
    item_points = {}
    # TODO: it might be worth optimising the search by clumping points
    # instead of a naive one-point-at-a-time approach.
    for pt in points:
        pt_json = {
            "type": "Point",
            "coordinates": [pt.wgs84_x, pt.wgs84_y] }
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
        properties = []
        # TODO: Do I need to split bounding boxes that cross the anti-meridian into two?
        # Or does the stac-client handle this case?
        # See: https://www.rfc-editor.org/rfc/rfc7946#section-3.1.9
        search = stac_client.search(
            collections=collections,
            max_items=None, # no limit on number of items to return
            intersects=pt_json,
            limit=500, # results per page
            datetime=[pt.start_date, pt.end_date],
            query=properties)
        items = list(search.items())
        # Tell the point which items it intersects.
        pt.add_items(items)
        # Group all points for each item together in an ItemPoints collection.
        for item in items:
            if item.id not in item_points:
                item_points[item.id] = drillpoints.ItemPoints(
                    item, asset_ids=raster_assets)
            item_points[item.id].add_point(pt)
    return list(item_points.values())


def calc_stats(item_points, std_stats=None, user_stats=None):
    """
    Calculate the statistics for all points in the given ItemPoints object.

    This reads the rasters and calculates the stats.

    Parameters
    ----------
    
    item_points : list of ``drillpoints.ItemPoints`` objects
        The ItemPoints for each image
    std_stats : sequence of integers
        Constants from the ``drillpoints`` module (STATS_MEAN, STATS_STDEV etc)
        defining which 'standard' statistics to extract
    user_stats : function
        A user defined function as specified above

    """
    msg = "Calculating stats for %i points in item %s."
    logging.info(msg, len(item_points.points), item_points.item.id)
    item_points.read_data()
    item_points.calc_stats(std_stats=std_stats, user_stats=user_stats)


class ImageItem:
    """
    Analogous to a pystac.Item object, which is to be passed to the
    ItemPoints constructor when drilling pixels from an image file.

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
