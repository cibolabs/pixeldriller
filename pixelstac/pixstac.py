"""
Initial implementation
=========================

pixstac.query is the main interface. Most interaction with this package should
be through this interface.

It currently only provides a bare-bones implementation, supporting only
a fixed spatial buffer within plus/minus tdelta time of every point.

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

# TODO: expand the set of stats
RAW = 'raw'
MEAN = 'mean'
STDDEV = 'stddev'

def query(
    endpoint, points, buffer, sp_ref, tdelta, raster_assets,
    nearest_n=None, item_properties=None, stats=[RAW], ignore_val=None,
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
        stats=["MY_STAT", pixstac.RAW], ignore_val=[0,0,0],
        stats_funcs=[(my_func)])

    The 'names' of the statistics are provided in the stats argument. There
    must be one name for every stats_func. These names are used to retrieve the
    values in the returned PixStats objects. Stats may have an additional
    name of pixstac.RAW, in which case the raw arrays are also returned.
    For example::

      for stats_set in results:
        for pix_stats in stats_set:
          my_stat = pix_stats.stats["MY_STAT"]
          raw_arr = pix_stats.stats[pixstac.RAW]

    sp_ref defines the osr.SpatialReference of every point.
    Time is a datetime.datetime object. It may be timezone aware or unaware,
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
    
    If a preproc function is given, then call this function for every array
    before calculating the statistics. The given function must return an
    array. The stats will be calculated on the returned array. The function
    signature must be::

        def preproc_func(arr, asset_id)
    
    """
    pass


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

