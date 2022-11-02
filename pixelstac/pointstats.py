"""
Statistics and data extracted from the raster assets returned from
a pixelstac query.

"""

import collections

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

    """
    def __init__(
        self, pt, items, asset_ids, std_stats=[STATS_RAW], user_stats=None):
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

        See also ItemStats.
        
        """
        # Initialise things
        self.pt = pt
        self.asset_ids = asset_ids
        self.std_stats = std_stats
        self.user_stats = user_stats
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
        stats dictionary, with STATS_RAW as the key.

        Then calculate this instance's list of standard stats and user stats.

        """
        pt = self.pt_stats.pt
        asset_arrays = []
        for asset_id in self.pt_stats.asset_ids:
            arr = asset_reader.read_roi(self.item, asset_id, pt)
            # TODO: handle case where read_roi returns None.
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
    It calculates the mean value for every layer in each array of asset_arrays.
    
    Can only be used if all assets are single-layer rasters.

    Return a named tuple containing the mean value of the pixels for each asset.
    
    Raise a MultibandAssetError if at least one asset contains multiple bands.

    """
    rast_counts = [arr.shape[0] for arr in asset_arrays]
    errmsg = ''
    mean_vals = []
    for arr, rast_count, asset_id in zip(asset_arrays, rast_counts, asset_ids):
        # TODO: handle the case where read_roi returned None, will
        # rast_count be 0??
        if rast_count != 1:
            errmsg += f"{asset_id} contains {rast_count} layers.\n"
        else:
            # TODO: handle case where arr contains null values.
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
