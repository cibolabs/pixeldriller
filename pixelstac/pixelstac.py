"""
pixstac.drill is the main interface. Most interaction with this package should
be through this interface.

Assumptions:
- Uses GDAL's /vsicurl/ file system handler for online resources that do
  not require authentication
- The file server supports range requests
- If you want to calculate standard statistics then each STAC Item's asset
  must be a single-band raster

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

from . import pointstats
from . import asset_reader

def drill(
    points, images=None,
    stac_endpoint=None, raster_assets=None, collections=None, item_properties=None,
    nearest_n=1, std_stats=None, user_stats=None, ignore_val=None,
    concurrent=False):
    """
    Given a list of pointstats.Point objects, compute the zonal statistics for
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
    temporal window by reading the pointstats.Point documentation.

    std_stats is a list of standard stats defined in the pointstats module
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
    - pt is the pointstats.Point object from around which the pixels
      were extracted

    Each ArrayInfo instance has a data attribute that contains a 3D numpy
    masked array with the pixel data for the asset defined by the instance's
    asset_id attribute. But note that each element in array_info corresponds
    to the raster_assets passed to drill().

    The user function must return a value. It can be any data type.
    The returned value is stored with the point without modification.

    With the statistics calculated, you retrieve their values point-by-point.
    The Point class's get_stats() function returns a dictionary of
    pointstats.ItemStats objects, keyed by the STAC Item's ID. So, the
    dictionary's length is matches the number of STAC Items that the
    Point intersects. The zonal statistics are retrieved using the ItemStats
    get_stats() function, passing it the statistic's name. For example::

        item_stats_dict = pt.get_stats()
        for item_id, item_stats in item_stats_dict.items():
            print(f"    Item ID={item_id}") # The pystac.item.Item
            print(f"        Raw arrays : {item_stats.get_stats(pointstats.STATS_RAW)}")
            print(f"        Mean values: {item_stats.get_stats(pointstats.STATS_MEAN)}")
            print(f"        Counts     : {item_stats.get_stats(pointstats.STATS_COUNT)}")
            print(f"        Null Counts: {item_stats.get_stats(pointstats.STATS_COUNTNULL)}")
            print(f"        My Stat    : {item_stats.get_stats("MY STAT")})

    A few things to note in this example:
    - the std_stats argument passed to drill() is
      [pointstats.STATS_MEAN, pointstats.STATS_COUNT, pointstats.STATS_COUNTNULL]
    - the user_stats argument defines the 'MY_STAT' statistic and its
      corresponding function name: [('MY_STAT', my_stat_function)]
    - the numpy masked arrays are retrievable from the ItemStats.get_stats()
      function with pointstats.STATS_RAW - these are always supplied
    - likewise, the ArrayInfo object is retrievable from the ItemStats.get_stats()
      function with pointstats.STATS_ARRAYINFO 

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
    # On completion, each point will contain ItemStats objects, with stats
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


def assign_points_to_images(points, images):
    """
    Return a list of pointstats.ItemPoints collections, one for each image
    in the images list.

    A point will be added to those ItemPoints collection that it intersects,
    and a pointstats.ImageItem is also added to the point.

    """
    item_points = []
    for image in images:
        image_item = pointstats.ImageItem(image)
        ip = pointstats.ItemPoints(image_item)
        item_points.append(ip)
        ds = gdal.Open(image, gdal.GA_ReadOnly)
        for pt in points:
            if pt.intersects(ds):
                ip.add_point(pt)
                pt.add_items([image_item])
    return item_points


def assign_points_to_stac_items(
    stac_client, points, collections, raster_assets):
    """
    Search the list of collections in a STAC endpoint for items that
    intersect the x, y coordinate of the list of points and are within the
    Points' temporal search windows.

    stac_client is the pystac.Client object returned from calling
    pystac.Client.open(endpoint_url).
    
    If no collections are specified then search all collections in the endpoint.

    Link each Point with its pystac.Items, and create a pointstats.ItemPoints
    collection for every item.

    Return the list of pointstats.ItemPoints collections.

    TODO: permit user-defined properties for filtering the stac search.

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
                item_points[item.id] = pointstats.ItemPoints(
                    item, asset_ids=raster_assets)
            item_points[item.id].add_point(pt)
    return list(item_points.values())


def calc_stats(item_points, std_stats=None, user_stats=None):
    """
    Calculate the statistics for all points in the given ItemPoints object.

    This reads the rasters and calculates the stats.

    """
    logging.info(
          f"calculating stats for {len(item_points.points)} points " \
          f"in item {item_points.item.id}")
    item_points.read_data()
    item_points.calc_stats(std_stats, user_stats)
