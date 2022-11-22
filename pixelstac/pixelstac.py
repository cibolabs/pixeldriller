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

from pystac_client import Client

from . import pointstats

def drill(
    stac_endpoint, points, raster_assets,
    collections=None, nearest_n=1, item_properties=None,
    std_stats=[pointstats.STATS_RAW], user_stats=None, ignore_val=None,
    concurrent=False):
    """
    Given a STAC endpoint and a list of pointstats.Point objects,
    compute the zonal statistics for all raster assets for
    the n nearest-in-time STAC items for every point.
    
    Thus, for every Point find zero or more STAC Items, and calculate a set of
    zonal statistics for each raster asset.

    The statistics are stored with the Point object, retrievable using the
    Point class's get_stats() or get_item_stats() functions.

    See example.py for typical example usage.

    Familiarise yourself with the concepts of a Point's region of interest and
    temporal window by reading the pointstats.Point documentation.

    The algorithm proceed as follows...

    Query the STAC endpoint for Items that intersect each point within the
    Point's temporal window.

    TODO: The items can be optionally filtered by the list of item properties.
    
    TODO: Restrict the number of Items for each point to the nearest_n in time.
    
    Then for each Item returned, extract the pixels for every raster
    asset for each intersecting Point's region of interest. The pixels are
    stored as numpy masked arrays.
    
    With the pixels extracted, calculate the zonal statistics.
    There are two categories of statistics:
    standard (std_stats) and user-supplied (user_stats).
    
    std_stats is a list of standard stats defined in the pointstats module
    with the STATS_* attributes. To use the standard statistics,
    every asset must be a single-band raster.
        
    user_stats is a list of (name, function) pairs. The function is used
    to calculate a user-specified statistics.
    The signature of a user-supplied function must be::

        def user_func(array_info, item, pt):

    where:
    - array_info is a list containing the data and meta data about the pixels
      extracted from each asset; each element is an instance of
      asset_reader.ArrayInfo
    - item is the STAC item associated with the assets; it is an instance of
      pystac.Item from the PySTAC package
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
    client = Client.open(stac_endpoint)
    item_points = {}
    logging.info(f"Searching {stac_endpoint} for {len(points)} points")
    item_points = stac_search(client, points, collections)
    # Read the pixel data from the rasters and calculate the stats.
    # Each point will contain ItemStats objects, with its stats for those
    # item's assets.
    # Similar to ItemPoints.read_data(), we could read data for each Item
    # in a threadpool. Probably makes sense to do it at this level than at
    # the Asset level because we expect there to be more items than there 
    # are assets. And also the asset reads can be done sequentially.
    logging.info(f"The {len(points)} points intersect {len(item_points)} items")
    if concurrent:
        logging.info("Running extract concurrently.")
        with futures.ThreadPoolExecutor() as executor:
            tasks = [executor.submit(
                calc_stats(
                    ip, raster_assets, std_stats=std_stats, user_stats=user_stats)) \
                    for ip in item_points]
    else:
        logging.info("Running extract sequentially.")
        for ip in item_points:
            calc_stats(
                ip, raster_assets, std_stats=std_stats, user_stats=user_stats)


def stac_search(stac_client, points, collections):
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
                item_points[item.id] = pointstats.ItemPoints(item)
            item_points[item.id].add_point(pt)
    return list(item_points.values())


def calc_stats(item_points, raster_assets, std_stats=None, user_stats=None):
    """
    Calculate the statistics for all points in the given ItemPoints object.

    This reads the rasters and calculates the stats.

    """
    logging.info(
          f"calculating stats for {len(item_points.points)} points " \
          f"in item {item_points.item.id}")
    item_points.read_data(raster_assets)
    item_points.calc_stats(std_stats, user_stats)
