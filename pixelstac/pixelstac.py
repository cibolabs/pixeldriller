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

# TODO: expand the set of stats
RAW = 'raw'
MEAN = 'mean'
STDDEV = 'stddev'

class Coord:
    """
    A class that contains x, y information about a coordinate and
    its spatial reference system.

    """
    def __init__(self, x, y, sp_ref):
        self.

def query(
    endpoint, points, buffer, sp_ref, raster_assets,
    t_delta=datetime.timedelta(days=1),
    nearest_n=1, item_properties=None, stats=[RAW], ignore_val=None,
    stats_funcs=None):
    """
    Given a STAC endpoint, set of X-Y-Time points, spatial buffer,
    and a temporal buffer (tdelta) return the n nearest-in-time zonal
    stats for all of the specified raster assets.

    Proceed as follows...

    Query the STAC endpoint for Items within the spatio-temporal region of
    interest (STRegion) of each X-Y-Time point, optionally filtered
    by the list of item properties.
    
    Restrict the number of Items for each point to up to the nearest_n in time.
    
    Then, for each point, extract the pixels within the region of interest
    about the point for the specifified raster assets for the list of Items.
    
    Finally, calculate a set of statistics for the pixels within each STRegion.
    stats_funcs defines the functions that are used to calculate the stats.
    The functions must take an array as their only argument. Users can use
    functools.partial to supply other required data.

    For example::

      my_func = functools.partial(func_that_takes_an_array,
        func_otherarg1=value, func_otherarg2=value) 
      results = pixstac.query(
        "https://earth-search.aws.element84.com/v0",
        points, 50, 3577, datetime.timedelta(days=8),
        asset_ids, item_properties=item_props,
        stats=["MY_STAT", pixstac.MEAN, pixstac.RAW], ignore_val=[0,0,0],
        stats_funcs=[(my_func)])

    The 'names' of the statistics are provided in the stats argument. There
    must be at least one for every stats_func. There can be additional for
    standard statistics like pixstat.MEAN, pixstat.STDDEV, and pixstat.RAW 
    (These are special reserved names).
    The names are used to retrieve the values in the returned PixStats objects.
    
    For example::

      for stats_set in results:
        for pix_stats in stats_set:
          my_stat = pix_stats.stats["MY_STAT"]
          mean = pix_stats.stats[pixstac.MEAN]
          raw_arr = pix_stats.stats[pixstac.RAW]

    The name pixstac.RAW, if used will provide the raw pixels in the region
    of interest in the returned PixStats objects.

    sp_ref defines the osr.SpatialReference of every point.
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
    # TODO: Create a bounding box around EVERY point and convert its extents to
    # WGS84 to pass to find_stac_items.
    #wkt = "POINT ({} {})".format(x, y)
    #pt = ogr.CreateGeometryFromWkt(wkt)
    #poly = pt.Buffer(bufferDistance)
    #xmin, xmax, ymin, ymax = poly.GetEnvelope()
    # TODO: work out if xmin, xmax, ymin, ymax are ulx, uly, lrx, and lry
    # TODO: transform the points to WGS84
    # TODO: determine if I have to pass x,y or y,x order
    # ct = osr.CoordinateTransformation(sp_ref, EPSG:4326)
    # wgs_ulx, wgs_uly = ct.TransformPoint(ulx, uly)
    # TODO: and the same for wgs_lrx and wgs_lry
    items = find_stac_items(
        endpoint, points[0],
        points[0][2]-t_delta, points[0][2]+t_delta)
    # TODO: determine the nearest_n items
    # TODO: Extract the pixel values for each asset in each item
    for item in items:
        for asset_id in raster_assets:
            url = item.assets[asset_id].href
            vsi_url = f"/vsicurl/{url}"
            print(vsi_url)
            ds = gdal.Open(vsi_url, gdal.GA_ReadOnly)
            band = ds.GetRasterBand(1)
            # TODO: Reads the CRS from the asset and transform the bounds
            # to the same CRS. Using osr.SpatialReference.ImportFromWKT?
            # ct = osr.CoordinateTransformation(sp_ref, asset_ref)
            # ass_ulx, ass_ulx = ct.TransformPoint(ulx, uly)
            # TODO: and the same for ass_lrx and ass_lry
            # TODO: Convert the bounds to image-coordinates and determine
            # the window size.
            # img_ulx, img_uly = wld2pix(ass_ulx, ass_uly) # these are xoff and yoff
            # img_lrx, img_lry = wld2pix(ass_lrx, ass_lry)
            # TODO: win-size must span the top left corner of the top left pixel
            # to the bottom right corner of the bottom right pixel for all 
            # pixels touched by the bounding box.
            # win_xsize = abs(img_lrx - img_ulx) # TODO: Do I need abs? Does this work for all cases? i.e. what assumptions am I making about the properties of the asset's sp_ref.
            # win_ysize = abs(img_lry - img_lrx) # TODO: Do I need abs? Does this work for all cases? i.e. what assumptions am I making about the properties of the asset's sp_ref.
            pixels = band.ReadArray(xoff=img_ulx, yoff=img_uly, win_xsize=win_xsize, win_ysize=win_ysize)
            # TODO: mask the pixels to the bounds of the AOI
            # In the following example we work in the asset's sp_ref
            #from tuiview import vectorrasterizer
            #boundingBox = [xmin, ymax, xmax, ymin]
            #mask = vectorrasterizer.rasterizeGeometry(poly, boundingBox, xsize, ysize, 0, True)  # filled but no outline
            #mask = mask == 1 # convert to bool
            # TODO: check if the input asset has an ignore value set, either in the returned stac properties or the image itself
            # pixels[mask] = ignore_val
            # TODO: stash the pixels in a PixStats object as RAW.
            # TODO: calc additional stats and stash results in PixStats object.
            # TODO: call the user-specified stats_funcs and stash results in PixStats object.
            # Close the dataset
            ds = None

#    print(items[0].assets[])


def find_stac_items(endpoint, point, start_date, end_date):
    """
    Find the stac items for the X-Y-Time point.

    Time is a datetime.datetime object.



    Search https://earth-search.aws.element84.com/v0, in the
    sentinel-s2-l2a-cogs collection, for items for the given
    tile and dates.

    The tile is specified as a sentinel-2 tile ID, e.g. 49JFM.
    The earliest and latest dates are in ISO date format (YYYY-MM-DD).
    Return a list of pystac.Item instances.

    Read https://element84.com/earth-search/ for more on the search API.

    """
    api = Client.open(endpoint) # TODO: pass the api through to this function.
    # Properties to filter by. These are part of the STAC API's query extension:
    # https://github.com/radiantearth/stac-api-spec/tree/master/fragments/query
    # We would add eo:cloud_cover here if we wanted to exclude very cloudy scenes.
    # Properties can be determined by examining the 'properties' attribute
    # of an item in the collection.
    # e.g. curl -s https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2B_53HPV_20220728_0_L2A | jq | less
    import json
    point_json = {
        "type": "Point",
        "coordinates": [point[0], point[1]] }
    collections = ['sentinel-s2-l2a-cogs'] # Optional argument to pass in, otherwise search everything at the given /search endpoint.
    # TODO: permit user-defined properties.
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
#        bbox=bbox,
        intersects=point_json,
        limit=500, # results per page
        datetime=[start_date, end_date],
        query=properties)
    print(type(search))
    results = list(search.items())
#    print(type(results))
    print(len(results))
#    print(dir(results[0]))
    return results


def wld2pix(transform, geox, geoy):
    """converts a set of map coords to pixel coords"""
    x = (transform[0] * transform[5] - 
        transform[2] * transform[3] + transform[2] * geoy - 
        transform[5] * geox) / (transform[2] * transform[4] - transform[1] * transform[5])
    y = (transform[1] * transform[3] - transform[0] * transform[4] -
        transform[1] * geoy + transform[4] * geox) / (transform[2] * transform[4] - transform[1] * transform[5])
    return (x, y)


#def pix2wld(transform, x, y):
#    """converts a set of pixels coords to map coords"""
#    geox = transform[0] + transform[1] * x + transform[2] * y
#    geoy = transform[3] + transform[4] * x + transform[5] * y
#
#    return (geox, geoy)


class PixStats:
    """
    If pixstac.py gets too cumbersome, we can move this PixStats class,
    and the functions that do the stats calcs, into a separate module.
    I suggest it be called pixstats.py.

    Stores the zonal statistics for each Item (image) about a point.

    Has the following attributes:
    - item: the name or identifier of the STAC item
    - urls: the URL to each raster asset in the item
    - stats: a dictionary, that stores the raw pixels or zonal stats
      For example, given a pix_stats object,
      pix_stats.stats[pixstac.MEAN] is a 1D array with the mean value of
      the pixels in the region of interest for each asset, and
      pix_stats.stats[pixstac.RAW] is a 3D array with the raw pixel values
      in the region of interest for each asset.

    """
    pass

