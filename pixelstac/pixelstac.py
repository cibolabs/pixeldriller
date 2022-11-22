"""
Initial implementation
=========================

pixstac.query is the main interface. Most interaction with this package should
be through this interface.

It currently only provides a bare-bones implementation, supporting only
a fixed spatial buffer within plus/minus tdelta time of every point.

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
- numpy for stats calcs

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

    The statistics are added to each Point object, retrievable using the
    Point Class's get_stats() or get_point_stats() functions.

    Proceed as follows...

    Query the STAC endpoint for Items that intersect each point within the
    Point's temporal window of interest. TODO: The items can be optionally filtered
    by the list of item properties.
    
    TODO: Restrict the number of Items for each point to up to the nearest_n in time.
    
    Then for each Item returned, extract the pixels for the given raster
    assets for the region of interest of each Point that intersects the Item.
    The region of interest is defined by the Point's buffer and shape,
    where shape is one of the pointstats.ROI_SHP_ attributes).
    
    With the pixels extracted for each Item/Asset/Point combination,
    calculate a set of statistics. There are two categories of stats:
    
    1. std_stats is a list of standard stats supplied by the pointstats
       module. Use the STATS_* attributes defined in pointstats. Standard
       stats assume that each raster asset contains only one band.
        
    2. TODO: user_stats is a list of (name, function) pairs. The function is used
       to calculate a user-specified statistic.
       A user-supplied function must take two arguments:
       - a 3D numpy array, containing the pixels for the region of interest
         for an asset
       - the asset ID (TODO: confirm if the asset ID is need or sufficient.)
       If a user stats function requires additional arguments, users should
       use functools.partial to supply the required data.
       The assets may contain multiple bands and the user function should
       handle this accordingly.

    For example::
      std_stats_list = [
        pointstats.STATS_MEAN, pointstats.STATS_COUNT, pointstats.STATS_COUNTNULL]
      my_func = functools.partial(func_that_takes_an_array,
        func_otherarg1=value, func_otherarg2=value)
      pixelstac.query(
        "https://earth-search.aws.element84.com/v0",
        my_points_list, asset_ids, collections=['sentinel-s2-l2a-cogs'],
        item_properties=item_props,
        std_stats=std_stats_list, user_stats=[("my_stat_name", my_func)])
      for pt in my_points_list:
        print(f"Stats for point: x={pt.x}, y={pt.y}")
        for item_id, item_stats in pt.get_stats().items():
            print(f"    Item ID={item_id}") # The pystac.item.Item
            print(f"        Raw arrays : {item_stats.get_stats(pointstats.STATS_RAW)}")
            print(f"        Mean values: {item_stats.get_stats(pointstats.STATS_MEAN)}")
            print(f"        Counts     : {item_stats.get_stats(pointstats.STATS_COUNT)}")
            print(f"        Null Counts: {item_stats.get_stats(pointstats.STATS_COUNTNULL)}")
            print(f"        My Stat    : {item_stats.get_stats("my_stat_name")})

    Note that the raw arrays are always populated, even if pointstats.STATS_RAW
    is not one of the standard stats specified.

    
    buffer is the distance around the point that defines the region of interest.
    Its units (e.g. metre) are assumed to be the same as the units of the
    coordinate reference system of the STAC Item's assets.
    It is the caller's responsibility to know what these are.
    
    Time (in the X-Y-Time point) is a datetime.datetime object.
    It may be timezone aware or unaware,
    in which case they are handled as per the pystac_client.Client.search
    interface. See:
    https://pystac-client.readthedocs.io/en/stable/api.html
    
    endpoint is passed to pystac_client.Client.Open.
    properties are passed through to pystac_client.Client.search
    https://pystac-client.readthedocs.io/en/stable/api.html

    TODO: ignore_val is the list of null values for each raster asset (or specify one
    value to be used for all raster assets). It should only be used if the
    null value of the raster is not set. It's used for:
      - as the mask value when 'removing' pixels from the raw arrays that
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


def stac_search(stac_client, points, collections):
    """
    Search the list of collections in a STAC endpoint for items that
    intersect the x, y coordinate of the list of points and are within the
    points' temporal search windows.

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
