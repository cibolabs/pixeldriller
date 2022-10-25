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

import datetime

from pystac_client import Client
from osgeo import gdal
from osgeo import osr

from . import pointstats

def query(
    stac_endpoint, points, buffer, raster_assets, ref_asset=None,
    nearest_n=1, item_properties=None, std_stats=[pointstats.STATS_RAW],
    user_stats=None, ignore_val=None):
    """
    Given a STAC endpoint and a list of pixelstac.Point objects,
    compute the zonal statistics for all raster assets for
    the n nearest-in-time STAC items for every point.

    Return a list of pointstats.PointStats objects.

    Proceed as follows...

    Query the STAC endpoint for Items within the spatio-temporal region of
    interest (STRegion) of each X-Y-Time point, optionally filtered
    by the list of item properties.
    
    Restrict the number of Items for each point to up to the nearest_n in time.
    
    Then, for each point, extract the pixels within the region of interest
    about the point (defined by the buffer) for the specifified raster assets
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
        points, 50, 3577, datetime.timedelta(days=8),
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
    coordinate reference system of the given reference asset (ref_asset).
    It is the caller's responsibility to know what these are.
    If ref_asset is not given, it defaults to the first item in raster_assets.
    
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
    # TODO: Implement masking of array with ignore_val.
    if not ref_asset:
        ref_asset = raster_assets[0]
    results = []
    for point in points:
        items = stac_search(stac_endpoint, point)
        # TODO: Choose the n nearest-in-time items.
        # TODO: what do we do if the ref_asset has no spatial reference defined?
        point.make_roi(buffer, items[0], ref_asset)
        pstats = pointstats.PointStats(point, items, raster_assets)
        results.append(pstats)
    return results


class Point:
    """
    A structure for an X-Y-Time point with a corresponding 
    osr.SpatialReference system. A point is characterised by:
    - a location in space and time
    - a spatial buffer
    - a temporal buffer
    
    These attributes are set at construction time:
    - x: the point's x-coordinate
    - y: the point's y-coordinate
    - t: the point's datetime.datetime time
    - x_y: the point's (x, y) location
    - sp_ref: the osr.SpatialReference of (x, y)
    - wgs84_x: the point's x location in WGS84 coordinates
    - wgs84_y: the point's y location in WGS84 coordinates
    - start_date: the datetime.datetime start date of the temporal buffer
    - end_date: the datetime.datetime end date of the temporal buffer

    These attributes are set on calling make_roi
    - roi: the point's spatial buffer (region of interest)

    """
    def __init__(self, point, sp_ref, t_delta):
        """
        Point constructor.

        Takes a (X, Y, Time) point and the osr.SpatialReference object
        defining the coordinate reference system of the point.

        Time is a datetime.datetime object.

        Also takes the datetime.timedelta object, which defines the 
        temporal buffer either side of the given Time.

        """
        self.x = point[0]
        self.y = point[1]
        self.t = point[2]
        self.x_y = (self.x, self.y)
        self.sp_ref = sp_ref
        self.wgs84_x, self.wgs84_y = self.to_wgs84()
        self.start_date = self.t - t_delta
        self.end_date = self.t + t_delta


    def to_wgs84(self):
        """
        Return the x, y coordinates of this Point in the WGS84 coordinate
        reference system.
        Convert the given points (list of x, y tuples) from the source
        spatial reference system to WGS84 (EPSG:4326).

        Return a list of x, y (longitude, latitude) tuples.

        Use transform_points to do the transformation.

        """
        dst_srs = osr.SpatialReference()
        dst_srs.ImportFromEPSG(4326)
        return transform_point(self.x, self.y, self.sp_ref, dst_srs)

    
    def make_roi(self, buffer, item, ref_asset):
        """
        Construct the region of interest in the same coordinate
        reference system as the reference asset of the given pystac.item.Item.
    
        buffer is the distance either side of the point that defines the roi,
        which in this case is a square. The unit of measure of buffer
        (e.g. metre) must be the same as the unit of measure of the coordinate
        reference system of the reference asset; it is the caller's
        responsibility to know the unit.
    
        """
        # self.x_y is the centre of the point and has a coordinate
        # reference system of self.sp_ref.
        # Example, although I think this creates a circle not a square
        # which do we want?
        #pt = ogr.CreateGeometryFromWkt(wkt)
        #poly = pt.Buffer(bufferDistance)
        #xmin, xmax, ymin, ymax = poly.GetEnvelope()
        pass


def stac_search(stac_endpoint, point, collections=None):#start_date, end_date, collections=None):
    """
    Search the list of collections in the STAC endpoint for items that
    intersect the x, y coordinate of the point and are within the point's
    temporal search window.
    
    If no collections are specified then search all collections in the endpoint.

    Return a list of pystac.item.Item objects.

    TODO: permit user-defined properties for filtering the stac search.

    """
    api = Client.open(stac_endpoint)
    # Properties to filter by. These are part of the STAC API's query extension:
    # https://github.com/radiantearth/stac-api-spec/tree/master/fragments/query
    # We would add eo:cloud_cover here if we wanted to exclude very cloudy scenes.
    # Properties can be determined by examining the 'properties' attribute
    # of an item in the collection.
    # e.g. curl -s https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2B_53HPV_20220728_0_L2A | jq | less
    point_json = {
        "type": "Point",
        "coordinates": [point.wgs84_x, point.wgs84_y] }
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
    search = api.search(
        collections=collections,
        max_items=None, # no limit on number of items to return
        intersects=point_json,
        limit=500, # results per page
        datetime=[point.start_date, point.end_date],
        query=properties)
    results = list(search.items())
    return results


def transform_point(x, y, src_srs, dst_srs):
    """
    Transform the (x, y) point from the source
    osr.SpatialReference to the destination osr.SpatialReference.

    Return the transformed (x, y) point.

    Under the hood, use the OAMS_TRADITIONAL_GIS_ORDER axis mapping strategies
    to guarantee x, y point ordering of the input and output points.

    """
    src_map_strat = src_srs.GetAxisMappingStrategy()
    dst_map_strat = dst_srs.GetAxisMappingStrategy()
    src_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    # TODO: handle problems that may arise. See:
    # https://gdal.org/tutorials/osr_api_tut.html#coordinate-transformation
    ct = osr.CoordinateTransformation(src_srs, dst_srs)
    tr = ct.TransformPoint(x, y)
    src_srs.SetAxisMappingStrategy(src_map_strat)
    dst_srs.SetAxisMappingStrategy(dst_map_strat)
    return (tr[0], tr[1])
