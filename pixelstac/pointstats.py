"""
Statistics and data extracted from the raster assets returned from
a pixelstac query.

"""

import warnings

import numpy
from osgeo import osr

from . import asset_reader


##############################################
# Symbols defining the statistics.
##############################################

# TODO: expand the set of stats
# The Set of standard statistics. See the STD_STATS_FUNCS dictionary at
# the end of this module, which maps the statistic to a function.
STATS_RAW = 'raw'
STATS_MEAN = 'mean'
STATS_STDDEV = 'stddev'
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
#ROI_SHP_CIRCLE = 'circle'

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
    - buffer: the distance from the point that defines the region of interest
    - shape: the shape of the region of interest
    - other_attributes: other attributes, of any type, as required by the caller

    """
    def __init__(
        self, point, sp_ref, t_delta, buffer, shape, other_attributes=None):
        """
        Point constructor.

        Takes a (X, Y, Time) point and the osr.SpatialReference object
        defining the coordinate reference system of the point.

        Time is a datetime.datetime object.

        Also takes the datetime.timedelta object, which defines the 
        temporal buffer either side of the given Time.

        The region of interest about the point is defined by the buffer
        and the shape. buffer is assumed to be in the same coordinate
        reference system as the raster assets being queried. shape is one of
        the ROI_SHP_ symbols defined in this module.

        other_attributes are any other attributes that the caller wants to
        attach to this point for later convenience. They have no effect when
        querying the pixelstac. However, the Point and its other_attributes
        are accessible from each PointStats object returned from
        pixelstac.query(). other_attributes can be any data type.

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
        self.other_attributes = other_attributes
        self.item_stats = {}


    def add_items(self, items):
        """
        A point might intersect multiple STAC items. Use this function
        to link the point with the items it intersects.

        It appends the list of pystac.Item items to the this Point's
        item_stats dictionary, keyed by the item ID.

        """
        for item in items:
            if item.id not in self.item_stats:
                self.item_stats[item.id] = ItemStats(item)

    
    def add_data(self, item, data):
        """
        Each point is associated with a region of interest.
        The data are the pixels in that region of interest from one of
        the item's assets.

        data is a numpy masked array. Later stats calculations
        exclude the masked pixels.

        The array is passed to the associated ItemStats object's
        add_data() function for storing.

        If pixels have are read from multiple assets, associated with the item,
        then call this function multiple times.

        This function must be called before calc_stats().

        """
        self.item_stats[item.id].add_data(data)

    
    def calc_stats(self, item, std_stats, user_stats):
        """
        Calculate the stats for the pixels about the point for all data that
        has been stored for the given item.

        Call add_data() first, for every required asset.

        std_stats is a list of standard stats to calculate for the point.
        Use the STATS_ symbols defined in this module.

        user_stats is a list of tuples. Each tuple defines:
        - the name (a string) for the statistic
        - and the function that is called to calculate it

        The request to calculate the statistics is passed to associated
        ItemStats object's calc_stats() function.

        """
        self.item_stats[item.id].calc_stats(std_stats, user_stats)


    def get_item_ids(self):
        """
        Return the IDs of the pystac.Item items associated with this point.

        """
        return self.item_stats.keys()


    def get_stats(self):
        """
        Return a dictionary with all stats for this point. The dictionary
        is keyed by the item ID, and its value is an ItemStats object.

        """
        return self.item_stats

    
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
        reference system.
        Convert the given points (list of x, y tuples) from the source
        spatial reference system to WGS84 (EPSG:4326).

        Return a list of x, y (longitude, latitude) tuples.

        Use transform_points to do the transformation.

        """
        dst_srs = osr.SpatialReference()
        dst_srs.ImportFromEPSG(4326)
        return self.transform(dst_srs)



##############################################
# Collections of points.
##############################################

class PointCollection:
    """An abstract class that represents a collection of points."""
    pass


class ItemPoints(PointCollection):
    """
    A collection of points that Intersect a STAC Item.

    """
    def __init__(self, item):
        """
        Construct an ItemPoints object, setting the following attributes:
        - item: the pystac.Item object
        - points: to an empty list

        """
        self.item = item
        self.points = []

    
    def add_point(self, pt):
        """
        Append the Point to this object's points list.

        """
        self.points.append(pt)

    
    def read_data(self, asset_ids, ignore_val=None):
        """
        TODO: pass ignore_values through.

        Read the pixels around every point.

        ignore_val specifies the no data values of the assets.
        It can be a single value, a list of values, or None.
        A single value is used for all bands of all assets.
        A list of values is the null value per asset. It assumes all
        bands in an asset use the same null value.
        None means to use the no data value set on each asset.

        """
        if isinstance(ignore_val, list):
            errmsg = "The ignore_val list must be the same length as asset_ids."
            assert len(ignore_val) == len(asset_ids), errmsg
        else:
            ignore_val = [ignore_val] * len(asset_ids)
        for asset_id, i_v in zip(asset_ids, ignore_val):
            reader = asset_reader.AssetReader(self.item, asset_id)
            reader.read_data(self.points, ignore_val=i_v)

    
    def calc_stats(self, std_stats, user_stats):
        """
        Calculate the statistics for every point.

        Call this after calling read_data.

        """
        for pt in self.points:
            pt.calc_stats(self.item, std_stats, user_stats)


class ImagePoints(PointCollection):
    """
    A collection of points that intersect a standard Image, represented
    by a path or URL.

    """
    pass


##############################################
# Classes for calculating statistics.
##############################################

#class PointStats:
#    """
#    An object returned from pixelstats.query that contains the raw pixel
#    data and statistics for the region of interest around a point for all
#    STAC items of interest.
#
#    This class is effectively a collection of ItemStats objects, with 
#    a reference to the associated point and Items and additional information
#    about the statistics to be calculated.
#
#    Has the following attributes:
#    - pt: the pixelstac.Point object
#    - asset_ids: list of user-supplied IDs to the raster assets in item.
#    - std_stats: the list of standard stats to calculate for the point
#    - user_stats: the list of user stats and associated function to
#      calculate for the point.   
#    - item_stats_list: a list of ItemStats objects; the stats are calculated 
#      by calling calc_stats().
#    - ignore_vals: If set, is a list of ignore values, one per asset, to ignore
#      when calcluating statistics; the default is to use the no-data
#      value of layers in the assets of each item at the time they are read.
#
#    """
#    # NEW:
#    def __init__(self):
#
#    # ORIGINAL
##    def __init__(
##        self, pt, items, asset_ids, std_stats=[STATS_RAW], user_stats=None,
##        ignore=None):
#        """
#        Constructor that takes a list of pystac.item.Item objects returned from
#        pixelstac.search_stac and a list of raster asset IDs in the item.
#
#        std_stats is a list of standard stats supplied by this
#        module. Use the STATS_* attributes defined in this module.
#        
#        user_stats is a list of (name, function) pairs. The function is used
#        to calculate a user-specified statistic for each item.
#
#        A user-supplied function must take two arguments:
#        - a 3D numpy array, containing the pixels for the roi for an asset
#        - the asset ID
#        The value returned from the function is appended to the appropriate
#        list in the stats dictionary.
#
#        ignore is a scalar or list of pixel values that are ignored when calculating
#        the statistics. By default, the nodataval in each layer of each asset
#        of each item is used, if set. Specify one of:
#        - a scalar, which is used for all layers of all assets
#        - a list, the same length as asset_ids, defining the ignore_val to
#          use for all layers of the corresponding asset
#        Note that specifying a unique ignore value for every layer of every
#        asset is unsupported.
#
#        See also ItemStats.
#        
#        """
##        self.std_stats = std_stats
##        self.user_stats = user_stats
#        # Initialise things
##        self.pt = pt
##        self.asset_ids = asset_ids
##        self.std_stats = std_stats
##        self.user_stats = user_stats
##        if ignore is None:
##            self.ignore_vals = [None] * len(self.asset_ids)
##        else:
##            self.ignore_vals = ignore if isinstance(ignore, list) else \
##                               [ignore] * len(asset_ids)
##        assert len(self.ignore_vals) == len(self.asset_ids)
##        self.item_stats_list = [ItemStats(item, self) for item in items]
#        #self.item_stats_list = []
#        self.item_stats = {}
##        self.item_stats_list = []
#
#    def add_items(self, items):
#        """
#        Create an ItemStats object for each pystac.Item in the items list
#        and add them to this instance's item_stats dictionary, if the item's
#        ID is not already in the dictionary.
#
#        """
#        for item in items:
#            if item.id not in self.item_stats:
#                self.item_stats[item.id] = ItemStats(item)
#
##        item_stats = [ItemStats(item, self) for item in items]
##        self.item_stats_list.extend(item_stats)
#
#
#    def add_data(self, item, data):
#        """
#        Add the numpy masked array of data, which contains the pixels for one of
#        the assets of the item.
#
#        """
#        self.item_stats[item.id].add_data(data)
#
#    
#    def calc_stats(self, item, std_stats, user_stats):
#        """
#        Calculate the stats for the pixels about the point for all assets
#        in the given item.
#
#        Call add_data first, for every required asset.
#
#        """
#        self.item_stats[item.id].calc_stats(std_stats, user_stats)


class ItemStats:
    """
    A data structure that holds the statistics of the pixel arrays
    extracted from each asset for a single item about a Point.

    Has the following attributes:
    - item: the pystac.item.Item
    - point_stats: the parent PointStats object
    - stats: a dictionary containing the raster statistics within the region
      of interest of the associated point.
      The dictionary's keys are defined by names of the std_stats and 
      user_stats passed to the PointStats object. The dictionary's values are
      the return values of the corresponding stats function.
    
    """
#    def __init__(self, item, pt_stats):
    def __init__(self, item):
        """Constructor."""
        self.item = item
        self.stats = {}

    
    def add_data(self, data):
        """
        Add the numpy masked array of data, which contains the pixels for one of
        the assets of the item.

        The data is appended to the list in self.stats[STATS_RAW].

        """
        if STATS_RAW not in self.stats:
            self.stats[STATS_RAW] = []
        self.stats[STATS_RAW].append(data)

    
    def calc_stats(self, std_stats, user_stats):
        """
        Using the point's region of interest, read the array of pixels from
        all bands in each raster asset. Store the arrays in this instance's
        stats dictionary, with STATS_RAW as the key, if STATS_RAW is in the list
        of stats to return.

        Then calculate this instance's list of standard stats and user stats.

        TODO: asset_ids is only used for reporting which asset is multiband
        if std_stats is not None. But it's decoupled, so no guarantee it is correct.

        """
        # ORIGINAL:
#        pt = self.pt_stats.pt
#        asset_arrays = []
#        for asset_id, ignore_val in zip(self.pt_stats.asset_ids, self.pt_stats.ignore_vals):
#            arr = asset_reader.read_roi(self.item, asset_id, pt, ignore_val=ignore_val)
#            asset_arrays.append(arr)
#        if self.pt_stats.std_stats:
#            # Check that all arrays are single-band.
#            check_std_arrays(asset_arrays, self.pt_stats.asset_ids)
#            if STATS_RAW in self.pt_stats.std_stats:
#                self.stats.update({STATS_RAW: asset_arrays})
#                self.stats[STATS_RAW] = asset_arrays
#            # Calculate all other std stats.
#            warnings.filterwarnings(
#                'ignore', message='Warning: converting a masked element to nan.',
#                category=UserWarning)
#            std_stats = [s_s for s_s in self.pt_stats.std_stats if s_s != STATS_RAW]
#            for std_stat_name in std_stats:
#                std_stat_func = STD_STATS_FUNCS[std_stat_name]
#                self.stats[std_stat_name] = std_stat_func(asset_arrays)
        # NEW:
        if std_stats:
            # Check that all arrays are single-band.
            check_std_arrays(self.item, self.stats[STATS_RAW])
            warnings.filterwarnings(
                'ignore', message='Warning: converting a masked element to nan.',
                category=UserWarning)
            # STATS_RAW is already populated.
            stats_list = [s_s for s_s in std_stats if s_s != STATS_RAW]
            for stat_name in stats_list:
                std_stat_func = STD_STATS_FUNCS[stat_name]
                self.stats[stat_name] = std_stat_func(self.stats[STATS_RAW])
        # TODO: add support for user-defined stats functions.
        # for stat_name, stat_func in point_stats.user_stats:
        #     self.stats[stat_name] = stat_func(
        #       asset_arrays, self.pt_stats.asset_ids, self.item)

    def get_stats(self, stat_name):
        """
        Return the values for the requested statistic.

        """
        return self.stats[stat_name]


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
    in asset_arrays.

    """
    # Calculate the stat for each array because their their x and y sizes will
    # differ if their pixel sizes are different.
    mean_vals = [arr.mean() for arr in asset_arrays]
    return numpy.array(mean_vals)


def std_stat_count(asset_arrays):
    """
    Return a 1D array with the number of non-null pixels in each masked array
    in asset_arrays.

    """
    counts = [arr.count() for arr in asset_arrays]
    return numpy.array(counts)


def std_stat_countnull(asset_arrays):
    """
    Return a 1D array with the number of null pixels in each masked array
    in asset_arrays.

    """
    counts = [arr.mask.sum() for arr in asset_arrays]
    return numpy.array(counts)

# A mapping of the standard stats to their functions.
# STATS_RAW is a special cased and handled in ItemStats.add_data().
STD_STATS_FUNCS = {
    STATS_MEAN: std_stat_mean,
    STATS_COUNT: std_stat_count,
    STATS_COUNTNULL: std_stat_countnull
}
