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
- Each asset is a single-band raster

We'll rely on:
- pystac-client for searching a STAC endpoint
- osgeo.gdal for reading rasters
- osgeo.osr for coordinate transformations
- numpy for stats calcs
- tuiview.vectorrasterizer for masking by 'poly' geometry


Possible future enhancments
=========================

An option to use GDAL's notion of all-touched (-at) to include all pixels
touched buy the region of interest.

We could generalise the spatio-temporeal region.
It reduces to a polygon and time range.
We could allow users to define it several ways.
Spatial definitions include:
- point and radius
- point and rectangle width and height
- bounding box
- a vector dataset
Temporal definitions include:
- a reference time and tdelta either side of of reference time
- a start and end time
- a reference time and either -tdelta day before or +tdelta days after
A future versions may accept a list of STRegion objects, giving the
end user greater flexbility in defining the STRegions for each point.

"""

import logging
from concurrent import futures

from pystac_client import Client

from . import pointstats

def query(
    stac_endpoint, points, raster_assets,
    collections=None, nearest_n=1, item_properties=None,
    std_stats=[pointstats.STATS_RAW], user_stats=None, ignore_val=None,
    concurrent=None):
    """
    Given a STAC endpoint and a list of pointstats.Point objects,
    compute the zonal statistics for all raster assets for
    the n nearest-in-time STAC items for every point.

    Each Point object is updated with its statistics.

    Proceed as follows...

    Query the STAC endpoint for Items within the spatio-temporal region of
    interest (STRegion) of each X-Y-Time point, optionally filtered
    by the list of item properties.
    
    Restrict the number of Items for each point to up to the nearest_n in time.
    
    Then, for each point, extract the pixels within the region of interest
    about the point (defined by the buffer and shape, where shape is one of
    the point.ROI_SHP_ attributes) for the specifified raster assets
    for the list of Items.
    
    Finally, calculate a set of statistics for the pixels about each point.
    There are two types of stats:
    
    1. std_stats is a list of standard stats supplied by the pointstats
       module. Use the STATS_* attributes defined in pointstats. The result
       is placed in the PointStats.stats dictionary, keyed by the STATS_*
       attribute.
        
    2. user_stats is a list of (name, function) pairs. The function is used
       to calculate a user-specified statistic. Its return value is placed in
       the PointStats.stats dictionary, keyed by the given name.
       A user-supplied function must take two arguments:
       - a 3D numpy array, containing the pixels for the roi for an asset
       - the asset ID
       If a user stats function requires additional arguments, users should
       use functools.partial to supply the required data.

    For example::

      my_func = functools.partial(func_that_takes_an_array,
        func_otherarg1=value, func_otherarg2=value) 
      results = pixstac.query(
        "https://earth-search.aws.element84.com/v0",
        points, 50, point.ROI_SHP_SQUARE, sp_ref, datetime.timedelta(days=8),
        asset_ids, item_properties=item_props,
        stats=[pointstats.MEAN, pointstats.RAW], ignore_val=[0,0,0],
        stats_funcs=[("my_func_name", my_func)])

    The names are used to retrieve the values in the returned PixStats objects.
    
    For example::

      for stats_set in results:
        for pix_stats in stats_set:
          my_stat = pix_stats.stats["my_func_name"]
          mean = pix_stats.stats[pointstats.MEAN]
          raw_arr = pix_stats.stats[pointstats.RAW]

    The name pointstats.RAW, if used will provide the raw pixels in the region
    of interest in the returned PixStats objects.

    sp_ref defines the osr.SpatialReference of every point.
    
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

    ignore_val is the list of null values for each raster asset (or specify one
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
    for pt in points:
        # TODO: it might be worth optimising the search by clumping points
        # instead of a naive one-point-at-a-time approach.
        items = stac_search(client, pt, collections)
        # Tell the point which items it intersects.
        pt.add_items(items)
        # Group all points for each item together in an ItemPoints collection.
        for item in items:
            if item.id not in item_points:
                item_points[item.id] = pointstats.ItemPoints(item)
            item_points[item.id].add_point(pt)
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
                calc_stats(ip, raster_assets, std_stats, user_stats)) \
                    for ip in item_points.values()]
    else:
        logging.info("Running extract sequentially.")
        for ip in item_points.values():
            calc_stats(ip, raster_assets, std_stats, user_stats)


def calc_stats(item_points, raster_assets, std_stats, user_stats):
    """
    Calculate the statistics for all points in the given ItemPoints object.

    This reads the rasters and calculates the stats.

    """
    logging.info(
          f"calculating stats for {len(item_points.points)} points " \
          f"in item {item_points.item.id}")
    item_points.read_data(raster_assets)
    item_points.calc_stats(std_stats, user_stats)


def stac_search(stac_client, pt, collections):#start_date, end_date, collections=None):
    """
    Search the list of collections in a STAC endpoint for items that
    intersect the x, y coordinate of the point and are within the point's
    temporal search window.

    stac_client is the pystac.Client object returned from calling
    pystac.Client.open(endpoint_url).
    
    If no collections are specified then search all collections in the endpoint.

    Return a list of pystac.item.Item objects.

    TODO: permit user-defined properties for filtering the stac search.

    """
    # Properties to filter by. These are part of the STAC API's query extension:
    # https://github.com/radiantearth/stac-api-spec/tree/master/fragments/query
    # We would add eo:cloud_cover here if we wanted to exclude very cloudy scenes.
    # Properties can be determined by examining the 'properties' attribute
    # of an item in the collection.
    # e.g. curl -s https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2B_53HPV_20220728_0_L2A | jq | less
    pt_json = {
        "type": "Point",
        "coordinates": [pt.wgs84_x, pt.wgs84_y] }
    # TODO: permit user-defined properties. For example:
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
    results = list(search.items())
    return results
