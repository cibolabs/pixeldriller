"""
Statistics and data extracted from the raster assets returned from
a pixelstac query.

"""

import warnings

import numpy

from . import asset_reader

# TODO: expand the set of stats
STATS_RAW = 'raw'
STATS_MEAN = 'mean'
STATS_STDDEV = 'stddev'


class MultibandAssetError(Exception):
    """Raised by the std stats functions when an asset has multiple bands."""
    pass


class PointStats:
    """
    An object returned from pixelstats.query that contains the raw pixel
    data and statistics for the region of interest around a point for all
    STAC items of interest.

    This class is effectively a collection of ItemStats objects, with 
    a reference to the associated point and Items and additional information
    about the statistics to be calculated.

    Has the following attributes:
    - pt: the pixelstac.Point object
    - asset_ids: list of user-supplied IDs to the raster assets in item.
    - std_stats: the list of standard stats to calculate for the point
    - user_stats: the list of user stats and associated function to
      calculate for the point.   
    - item_stats_list: a list of ItemStats objects; the stats are calculated 
      by calling calc_stats().
    - ignore_vals: If set, is a list of ignore values, one per asset, to ignore
      when calcluating statistics; the default is to use the no-data
      value of layers in the assets of each item at the time they are read.

    """
    def __init__(
        self, pt, items, asset_ids, std_stats=[STATS_RAW], user_stats=None,
        ignore=None):
        """
        Constructor that takes a list of pystac.item.Item objects returned from
        pixelstac.search_stac and a list of raster asset IDs in the item.

        std_stats is a list of standard stats supplied by this
        module. Use the STATS_* attributes defined in this module.
        
        user_stats is a list of (name, function) pairs. The function is used
        to calculate a user-specified statistic for each item.

        A user-supplied function must take two arguments:
        - a 3D numpy array, containing the pixels for the roi for an asset
        - the asset ID
        The value returned from the function is appended to the appropriate
        list in the stats dictionary.

        ignore is a scalar or list of pixel values that are ignored when calculating
        the statistics. By default, the nodataval in each layer of each asset
        of each item is used, if set. Specify one of:
        - a scalar, which is used for all layers of all assets
        - a list, the same length as asset_ids, defining the ignore_val to
          use for all layers of the corresponding asset
        Note that specifying a unique ignore value for every layer of every
        asset is unsupported.

        See also ItemStats.
        
        """
        # Initialise things
        self.pt = pt
        self.asset_ids = asset_ids
        self.std_stats = std_stats
        self.user_stats = user_stats
        if ignore is None:
            self.ignore_vals = [None] * len(self.asset_ids)
        else:
            self.ignore_vals = ignore if isinstance(ignore, list) else \
                               [ignore] * len(asset_ids)
        assert len(self.ignore_vals) == len(self.asset_ids)
        self.item_stats_list = [ItemStats(item, self) for item in items]

    
    def calc_stats(self):
        """
        Calculate the statistics for the raster assets of every item.

        See also ItemStats.calc_stats().

        """
        for item_stats in self.item_stats_list:
            item_stats.calc_stats()


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
    def __init__(self, item, pt_stats):
        """Constructor."""
        self.item = item
        self.pt_stats = pt_stats
        self.stats = {}

    
    def calc_stats(self):
        """
        Using the point's region of interest, read the array of pixels from
        all bands in each raster asset. Store the arrays in this instance's
        stats dictionary, with STATS_RAW as the key, if STATS_RAW is in the list
        of stats to return.

        Then calculate this instance's list of standard stats and user stats.

        """
        pt = self.pt_stats.pt
        asset_arrays = []
        for asset_id, ignore_val in zip(self.pt_stats.asset_ids, self.pt_stats.ignore_vals):
            arr = asset_reader.read_roi(self.item, asset_id, pt, ignore_val=ignore_val)
            asset_arrays.append(arr)
        if STATS_RAW in self.pt_stats.std_stats:
            self.stats[STATS_RAW] = asset_arrays
        std_stats = [s_s for s_s in self.pt_stats.std_stats if s_s != STATS_RAW]
        for std_stat_name in std_stats:
            std_stat_func = STD_STATS_FUNCS[std_stat_name]
            self.stats[std_stat_name] = std_stat_func(
                asset_arrays, self.pt_stats.asset_ids)
        # TODO: add support for user-defined stats functions.
        # for stat_name, stat_func in point_stats.user_stats:
        #     self.stats[stat_name] = stat_func(
        #       asset_arrays, self.pt_stats.asset_ids, self.item)


def std_stat_mean(asset_arrays, asset_ids):
    """
    The function used to calculate zonal stats for STATS_MEAN.
    Only supports single-layer rasters. That is, the first dimension of
    each passed array is 1.

    Return a 1D array containing the mean values. Its length equals the
    length of asset_arrays.

    Raise a MultibandAssetError if at least one asset contains multiple bands.

    """
    # Occurs when calling arr.mean() when all elements of the masked arr are masked.
    warnings.filterwarnings(
        'ignore', message='Warning: converting a masked element to nan.',
        category=UserWarning)
    rast_counts = [arr.shape[0] for arr in asset_arrays]
    errmsg = ''
    mean_vals = []
    for arr, rast_count, asset_id in zip(asset_arrays, rast_counts, asset_ids):
        if rast_count > 1:
            errmsg += f"{asset_id} contains {rast_count} layers.\n"
        else:
            # This also handles the case where rast_count is 0, i.e. the arr is empty,
            # meaning that no-pixels were read from the image. For example,
            # the roi is outside the image extents. In this case arr.mean()
            # returns nan.
            mean_vals.append(arr.mean())
    if errmsg:
        errmsg = "ERROR: Cannot calculate the standard mean statistic " \
                 "because the following assets contain more than " \
                 "one band:\n" + errmsg
        raise MultibandAssetError(errmsg)
    return numpy.array(mean_vals)


# The standard stats and their functions.
# STATS_RAW is handled in ItemStats.calc_stats()
STD_STATS_FUNCS = {
    STATS_MEAN: std_stat_mean
}
