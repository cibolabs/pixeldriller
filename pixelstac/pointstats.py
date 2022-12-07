"""
Statistics and data extracted about points from the raster assets returned from
a pixelstac query.

"""

import warnings

import numpy
from osgeo import osr

from . import asset_reader


##############################################
# Symbols defining the statistics.
##############################################

# The Set of standard statistics. See the STD_STATS_FUNCS dictionary at
# the end of this module, which maps the statistic to a function.
STATS_RAW = 'raw'
STATS_ARRAYINFO = 'arrayinfo'
STATS_MEAN = 'mean'
STATS_STDEV = 'stddev'
# STATS_COUNT is the number of non-null pixels used in stats calcs.
# STATS_COUNTNULL is the number of null pixels in an array.
# They sum to the size of the array.
STATS_COUNT = 'count' # number of non-null pixels used in stats calcs.
STATS_COUNTNULL ='countnull' # number of null pixels in an array.

##############################################
# Information about points.
##############################################
# For defining the shape of a Point's region of interest.
ROI_SHP_SQUARE = 'square'
# TODO: implement circle as an ROI.
ROI_SHP_CIRCLE = 'circle'

class Point:
    """
    A structure for an X-Y-Time point with a corresponding 
    osr.SpatialReference system. A point is characterised by:
    - a location in space and time
    - a spatial buffer
    - a temporal window
    
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
    - buffer: the distance from the point that defines the region of interest
    - shape: the shape of the region of interest

    """
    def __init__(
        self, point, sp_ref, t_delta, buffer, shape):
        """
        Point constructor.

        point is a (X, Y, Time) tuple. X and Y are the spatial coordinates and
        Time is a datetime.datetime object.

        Time may be may be timezone aware or unaware.
        They are handled as per the pystac_client.Client.search interface.
        See: https://pystac-client.readthedocs.io/en/stable/api.html
        
        sp_ref is the osr.SpatialReference object
        defining the coordinate reference system of the point.

        t_delta is a datetime.timedelta object, which defines the
        temporal window either side of the given Time.

        buffer defines the region of interest about the point. It is assumed
        to be in the same coordinate reference system as the raster assets
        being queried.

        shape defines the shape of the region of interest. If shape is
        ROI_SHP_SQUARE, then buffer is half the length of the square's side.
        If shape is ROI_SHP_CIRCLE, then buffer is the circle's radius.

        """
        self.x = point[0]
        self.y = point[1]
        self.t = point[2]
        self.x_y = (self.x, self.y)
        self.sp_ref = sp_ref
        self.wgs84_x, self.wgs84_y = self.to_wgs84()
        self.start_date = self.t - t_delta
        self.end_date = self.t + t_delta
        self.buffer = buffer
        self.shape = shape
        self.item_stats = {}


    def add_items(self, items):
        """
        A point might intersect multiple STAC items. Use this function
        to link the point with the items it intersects.

        It initialises an ItemStats object for each item and adds it
        to this Point's item_stats dictionary, which is keyed by the item ID.

        """
        for item in items:
            if item.id not in self.item_stats:
                self.item_stats[item.id] = ItemStats(self, item)

    
    def add_data(self, item, arr_info):
        """
        Each point is associated with a region of interest.
        arr_info is the asset_reader.ArrayInfo object created when reading pixel
        data from one of the item's assets.
        See asset_reader.AssetReader.read_roi().

        Calls add_data() on the item's ItemStats.add_data() function.

        If data were read from multiple assets, then call this function multiple
        times, once for each asset.

        This function must be called before calc_stats().

        """
        self.item_stats[item.id].add_data(arr_info)
        

    def intersects(self, ds):
        """
        Return True if the point intersects the GDAL dataset. ds can be a
        open gdal.Dataest or a filepath as a string.

        The comparison is made using the image's coordinate reference system.

        """
        iinfo = asset_reader.ImageInfo(ds)
        img_srs = osr.SpatialReference()
        img_srs.ImportFromWkt(iinfo.projection)
        pt_x, pt_y = self.transform(img_srs)
        in_bounds = (pt_x >= iinfo.x_min and pt_x <= iinfo.x_max and
                     pt_y >= iinfo.y_min and pt_y <= iinfo.y_max)
        return in_bounds

 
    def calc_stats(self, item, std_stats, user_stats):
        """
        Calculate the stats for the pixels about the point for all data that
        has been stored for the given pystac.Item.

        Call add_data() first, for every required asset.

        std_stats is a list of standard stats to calculate for each point's
        region of interest.
        They are a list of STATS_ symbols defined in this module.

        user_stats is a list of tuples. Each tuple defines:
        - the name (a string) for the statistic
        - and the function that is called to calculate it

        The request to calculate the statistics is passed to the item's
        ItemStats.calc_stats() function.

        """
        self.item_stats[item.id].calc_stats(std_stats, user_stats)


    def get_item_ids(self):
        """
        Return a list of the IDs of the pystac.Item items associated with this point.

        """
        return list(self.item_stats.keys())


    def get_stat(self, item_id, stat_name):
        """
        Get a the requested statistic for the item.

        """
        item_stats = self.get_item_stats(item_id)
        return item_stats.get_stats(stat_name)


    def get_stats(self):
        """
        Return a dictionary with all stats for this point. The dictionary's
        keys are the item IDs, and its values are ItemStats objects.

        """
        return self.item_stats


    def reset(self):
        """
        Remove all stats from the attached ItemStats objects.

        """
        for stats in self.item_stats.values():
            stats.reset()


    def get_item_stats(self, item_id):
        """
        Return the ItemStats object for this point that corresponds to the
        required Item ID.

        """
        return self.item_stats[item_id]


    def transform(self, dst_srs):
        """
        Transform the point's x, y location to the destination
        osr.SpatialReference coordinate reference system.

        Return the transformed (x, y) point.

        Under the hood, use the OAMS_TRADITIONAL_GIS_ORDER axis mapping strategies
        to guarantee x, y point ordering of the input and output points.

        """
        src_map_strat = self.sp_ref.GetAxisMappingStrategy()
        dst_map_strat = dst_srs.GetAxisMappingStrategy()
        self.sp_ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        dst_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        # TODO: handle problems that may arise. See:
        # https://gdal.org/tutorials/osr_api_tut.html#coordinate-transformation
        ct = osr.CoordinateTransformation(self.sp_ref, dst_srs)
        tr = ct.TransformPoint(self.x, self.y)
        self.sp_ref.SetAxisMappingStrategy(src_map_strat)
        dst_srs.SetAxisMappingStrategy(dst_map_strat)
        return (tr[0], tr[1])


    def to_wgs84(self):
        """
        Return the x, y coordinates of this Point in the WGS84 coordinate
        reference system, EPSG:4326.

        """
        dst_srs = osr.SpatialReference()
        dst_srs.ImportFromEPSG(4326)
        return self.transform(dst_srs)

##############################################

class ImageItem:
    """
    Analogous to a pystac.Item object, which is to be passed to the
    ItemPoints constructor when drilling pixels from an image file.

    It just sets the Item's id attribute to the given filepath.

    """
    def __init__(self, filepath):
        self.id = filepath


##############################################
# Collections of points.
##############################################

class ItemPointsError(Exception): pass

class ItemPoints:
    """
    A collection of points that Intersect a pystac.Item or an ImageItem.

    The read_data() function is used to read the pixels from the associated
    rasters.

    """
    def __init__(self, item, asset_ids=None):
        """
        Construct an ItemPoints object, setting the following attributes:
        - item: the pystac.Item object or an ImageItem
        - asset_ids: the IDs of the pystac.Item's raster assets to read; leave
          this as None if item is an instance of ImageItem.
        - points: to an empty list

        """
        if isinstance(item, ImageItem) and asset_ids is not None:
            errmsg = "ERROR: do not set asset_ids when item is an ImageItem."
            raise ItemPointsError(errmsg)
        elif not isinstance(item, ImageItem) and asset_ids is None:
            errmsg = "ERROR: must set asset_ids when item is a pystac.Item."
            raise ItemPointsError(errmsg)
        self.item = item
        self.asset_ids = asset_ids
        self.points = []

    
    def set_asset_ids(self, asset_ids):
        """
        Set which asset IDs to read data from on the next call to read_data().
        This function is not relevant when self.item is an ImageItem.

        Using this function probably only makes sense in the context of
        reusing the pystac.Item objects to calculate statistics for an
        entirely new set of raster assets. That is, you would call this function
        after calling reset() and before calling read_data() and calc_stats().

        You may experience strange side effects if you don't call reset().
        The underlying behaviour is that arrays for the new set of asset_ids
        will be appended to the existing arrays for each point's ItemStats objects.
        Then, on the next calc_stats() call, the stats for all previously read
        data will be recalculated in addition to the new stats for the new assets.

        """
        if isinstance(self.item, ImageItem):
            errmsg = "ERROR: do not set asset_ids when item is an ImageItem."
            raise ItemPointsError(errmsg)
        elif not asset_ids:
            errmsg = "ERROR: must set asset_ids."
            raise ItemPointsError(errmsg)
        else:
            self.asset_ids = asset_ids


    def add_point(self, pt):
        """
        Append the Point to this object's points list.

        """
        self.points.append(pt)

 
    def read_data(self, ignore_val=None):
        """
        Read the pixels around every point for the given raster assets.

        ignore_val specifies the no data values of the rasters being read.
        
        When reading from the assets of a STAC Item, ignore_val can be
        a single value, a list of values, or None.
        A list of values is the null value per asset. It assumes all
        bands in an asset use the same null value.
        A single value is used for all bands of all assets.
        None means to use the no data value set on each asset.
        
        When reading from a plain image, ignore_val can be a single value
        or None.
        A single value is used for all bands in the image.
        None means to use the image band's no data value.

        The reading is done by asset_reader.AssetReader.read_data().

        """
        if self.asset_ids is not None:
            # Read assets from a Stac Item.
            if isinstance(ignore_val, list):
                errmsg = "The ignore_val list must be the same length as asset_ids."
                assert len(ignore_val) == len(self.asset_ids), errmsg
            else:
                ignore_val = [ignore_val] * len(self.asset_ids)
            for asset_id, i_v in zip(self.asset_ids, ignore_val):
                reader = asset_reader.AssetReader(self.item, asset_id)
                reader.read_data(self.points, ignore_val=i_v)
        else:
            # Read bands from an image
            reader = asset_reader.AssetReader(self.item)
            if ignore_val is not None:
                if isinstance(ignore_val, list):
                    errmsg = "Passing a list of ignore_vals when reading from " \
                             "an image is unsupported"
                    raise ItemPointsError(errmsg)
            reader.read_data(self.points, ignore_val=ignore_val)

    
    def get_points(self):
        """
        Get the list of pointstats.Point objects in this collection.

        """
        return self.points

    
    def calc_stats(self, std_stats, user_stats):
        """
        Calculate the statistics for every Point.

        Call this after calling read_data().

        std_stats is a list of standard stats to calculate for each point's
        region of interest.
        They are a list of STATS_ symbols defined in this module.

        user_stats is a list of tuples. Each tuple defines:
        - the name (a string) for the statistic
        - and the function that is called to calculate it

        The request to calculate the statistics is passed to each Point's
        calc_stats() function.

        """
        for pt in self.points:
            pt.calc_stats(self.item, std_stats, user_stats)


    def get_item(self):
        """Return the pystac.Item or ImageItem."""
        return self.item


    def reset(self):
        """
        Remove the statistics for every point.

        """
        for pt in self.points:
            pt.reset()


##############################################
# Classes for calculating statistics.
##############################################

class ItemStats:
    """
    A data structure that holds the statistics of the pixel arrays
    extracted from each asset for a single item about a Point.

    Has the following attributes:
    - pt: the point associated with this ItemStats object
    - item: the pystac.item.Item
    - stats: a dictionary containing the raster statistics within the region
      of interest of the associated point.
      The dictionary's keys are defined by names of the std_stats and
      user_stats passed to PointStats.calc_stats(). The dictionary's values are
      a list of the return values of the corresponding stats functions. There
      is one element a the list for each raster asset.
    
    """
    def __init__(self, pt, item):
        """Constructor."""
        self.pt = pt
        self.item = item
        self.stats = {}

    
    def add_data(self, arr_info):
        """
        Add the pointstats.ArrayInfo object.

        Elements are added to two of the stats dictionary's entries::

            stats["STATS_RAW"].append(arr_info.data)
            stats["STATS_ARRAYINFO"].append(arr_info)

        arr_info.data is the numpy masked array of data, which contains the
        pixels for one of the assets of the item.

        """
        if STATS_RAW not in self.stats:
            self.stats[STATS_RAW] = []
        self.stats[STATS_RAW].append(arr_info.data)
        if STATS_ARRAYINFO not in self.stats:
            self.stats[STATS_ARRAYINFO] = []
        self.stats[STATS_ARRAYINFO].append(arr_info)

    
    def calc_stats(self, std_stats, user_stats):
        """
        Calculate the given list of standard and user-defined statistics
        on each asset's array of data.

        add_data() must be called first, for each raster asset.

        std_stats is a list of standard stats to calculate for each point's
        region of interest.
        They are a list of STATS_ symbols defined in this module.

        user_stats is a list of tuples. Each tuple defines:
        - the name (a string) for the statistic
        - and the function that is called to calculate it

        The user function's signature must be::

            def myfunc(array_info, item, pt)

        Where:
        - array_info is a list of ArrayInfo objects, one for each asset
        - item is the pystac.Item object
        - pt is the pointstats.Point object
        
        """
        if std_stats:
            # Check that all arrays are single-band.
            # TODO: Permit std stats being calculated on multi-band images.
            # See https://github.com/cibolabs/pixelstac/issues/30.
            check_std_arrays(self.item, self.stats[STATS_RAW])
            warnings.filterwarnings(
                'ignore', message='Warning: converting a masked element to nan.',
                category=UserWarning)
            # STATS_RAW is already populated.
            stats_list = [
                s_s for s_s in std_stats if \
                s_s not in [STATS_RAW, STATS_ARRAYINFO]]
            for stat_name in stats_list:
                std_stat_func = STD_STATS_FUNCS[stat_name]
                self.stats[stat_name] = std_stat_func(self.stats[STATS_RAW])
        if user_stats:
            for stat_name, stat_func in user_stats:
                self.stats[stat_name] = stat_func(
                    self.stats[STATS_ARRAYINFO], self.item, self.pt)


    def get_stats(self, stat_name):
        """
        Return the values for the requested statistic.

        calc_stats() must have been called first.

        """
        return self.stats[stat_name]


    def reset(self):
        """
        Delete all previously calculated stats and raw arrays.

        """
        self.stats = {}


################################################
# Functions for calculating standard statistics.
################################################

class MultibandAssetError(Exception):
    """Raised by the std stats functions when an asset has multiple bands."""
    pass


def check_std_arrays(item, asset_arrays):
    """
    Raise a MultibandAssetError if at least one of the arrays in
    asset_arrays contains multiple bands.

    """
    errmsg = ""
    rast_counts = [arr.shape[0] for arr in asset_arrays]
    for idx, rcount in enumerate(rast_counts):
        if rcount > 1:
            errmsg += f"Array at index {idx} in asset_arrays contains {rcount} layers.\n"
    if errmsg:
        errmsg = "ERROR: Cannot calculate the standard statistics " \
                 f"because one or more assets for item {item.id} " \
                 "has more than one band:\n " + errmsg
        raise MultibandAssetError(errmsg)


def std_stat_mean(asset_arrays):
    """
    Return a 1D array with the mean values for each masked array
    in the list of asset_arrays.

    """
    # Calculate the stat for each array because their x and y sizes will
    # differ if their pixel sizes are different.
    # If all values in an array are masked, then mean=numpy.nan.
    mean_vals = [arr.mean() for arr in asset_arrays]
    return numpy.array(mean_vals)


def std_stat_stdev(asset_arrays):
    """
    Return a 1D array with the standard deviation for each masked array
    in the list of asset_arrays.

    If all values in an input array are masked, then return numpy.ma.masked
    for that array.

    """
    # Calculate the stat for each array because their x and y sizes will
    # differ if their pixel sizes are different.
    # If all values in an array are masked, then stdev=numpy.nan.
    stdev_vals = [arr.std() for arr in asset_arrays]
    return numpy.array(stdev_vals)


def std_stat_count(asset_arrays):
    """
    Return a 1D array with the number of non-null pixels in each masked array
    in the list of asset_arrays.

    """
    counts = [arr.count() for arr in asset_arrays]
    return numpy.array(counts)


def std_stat_countnull(asset_arrays):
    """
    Return a 1D array with the number of null pixels in each masked array
    in the list of asset_arrays.

    """
    counts = [arr.mask.sum() for arr in asset_arrays]
    return numpy.array(counts)

# A mapping of the standard stats to their functions.
# STATS_RAW is a special cased and handled in ItemStats.add_data().
STD_STATS_FUNCS = {
    STATS_MEAN: std_stat_mean,
    STATS_STDEV: std_stat_stdev,
    STATS_COUNT: std_stat_count,
    STATS_COUNTNULL: std_stat_countnull
}
