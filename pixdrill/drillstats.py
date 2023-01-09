"""
Contains classes and functions for calculating and holding the statistics
extracted from an Item around Points.

"""

# The Set of standard statistics. See the STD_STATS_FUNCS dictionary at
# the end of this module, which maps the statistic to a function.
import numpy
import warnings


STATS_RAW = 'raw'
"""
Raw Data to be passsed to userFunc
"""
STATS_ARRAYINFO = 'arrayinfo'
"""
Information about the array
"""
STATS_MEAN = 'mean'
""""
Calculate the mean
"""
STATS_STDEV = 'stddev'
"""
Calculate the standard deviation
"""
STATS_COUNT = 'count'
"""
The number of non-null pixels used in stats calcs.
"""
STATS_COUNTNULL ='countnull'
"""
The number of null pixels in an array.
Together, STATS_COUNT and STATS_COUNTNULL sum to the size of the array.
"""
STATS_STD=[STATS_MEAN, STATS_STDEV, STATS_COUNT, STATS_COUNT]
"""
List of standard statistics.
"""
ITEM_KEY="ITEM"
"""
For internal use only, it is the symbol used as the key for storing the
reference to the Item in PointStats.
"""


class PointStats:
    """
    Holds the statistics of the pixel arrays for a Point for one or more Items.

    Attributes
    ----------

    pt : Point object
        the point associated with this PointStats object
    item : pystac.item.Item or drill.ImageItem
        the item to hold the stats for
    item_stats : dictionary
        a dictionary containing the raster statistics within the region
        of interest of the associated point. The key is the Item ID, and the
        value is another dictionary. The second dictionary's keys are the names
        of the std_stats and user_stats passed to PointStats.calc_stats().
        Its values are a list of the return values of the corresponding stats
        functions. If the item is a STAC Item, there may be multiple elements
        in the list corresponding to the drilled raster assets.
    
    """
    def __init__(self, pt):
        """Constructor."""
        self.pt = pt
        self.item_stats = {}

    def add_data(self, item, arr_info):
        """
        Add the image_reader.ArrayInfo object as read from an Item's raster.

        Elements are appended to the lists that store the Item's statistics::

            item_stats[item.id][STATS_RAW].append(arr_info.data)
            item_stats[item.id][STATS_ARRAYINFO].append(arr_info)

        where arr_info.data is the numpy masked array of data containing the
        pixels for one of the assets of the item.
        
        If item is a STAC Item, then add_data may be called multiple times,
        once for each raster asset that is drilled.

        Parameters
        ----------
        item : drill.ImageItem or pystac.Item
        arr_info : image_reader.ArrayInfo

        """
        if item.id in self.item_stats:
            stats = self.item_stats[item.id]
        else:
            stats = {
                ITEM_KEY: item,
                STATS_RAW: [],
                STATS_ARRAYINFO: []}
            self.item_stats[item.id] = stats
        stats[STATS_RAW].append(arr_info.data)
        stats[STATS_ARRAYINFO].append(arr_info)

    def calc_stats(self, item_id, std_stats=None, user_stats=None):
        """
        Calculate the given list of standard and user-defined statistics
        for the given item.

        One of two of this class's functions must have been called first:
        #. add_data(), for each raster asset in the item
        #. reset()

        std_stats is a list of standard stats to calculate for each point's
        region of interest.
        They are a list of STATS symbols defined in this module.

        user_stats is a list of tuples. Each tuple defines:
        - the name (a string) for the statistic
        - and the function that is called to calculate it

        The user function's signature must be::

            def myfunc(array_info, item, pt)

        Where:
        - array_info is a list of ArrayInfo objects, one for each asset
        - item is the pystac.Item object
        - pt is the pointstats.Point object

        Parameters
        ----------
        item_id: str
            The Item's ID, for which stats will be calculated.
        std_stats : int
            A list of STATS_* constants defined in the drillstats module.
        user_stats : list of (name, func) tuples
            where func is the user functional to calculate a statistic.
        
        """
        stats = self.item_stats[item_id]
        item = stats[ITEM_KEY]
        if std_stats:
            # Check that all arrays are single-band.
            # TODO: Permit std stats being calculated on multi-band images.
            # See https://github.com/cibolabs/pixelstac/issues/30.
            check_std_arrays(item, stats[STATS_RAW])
            warnings.filterwarnings(
                'ignore', category=UserWarning,
                message='Warning: converting a masked element to nan.')
            # Assume that STATS_RAW and STATS_ARRAYINFO are already populated
            # or are empty lists.
            stats_list = [
                s_s for s_s in std_stats if
                s_s not in [STATS_RAW, STATS_ARRAYINFO]]
            for stat_name in stats_list:
                std_stat_func = STD_STATS_FUNCS[stat_name]
                stats[stat_name] = std_stat_func(stats[STATS_RAW])
        if user_stats:
            for stat_name, stat_func in user_stats:
                stats[stat_name] = stat_func(
                    stats[STATS_ARRAYINFO], item, self.pt)

    def get_stats(self, item_id=None, stat_name=None):
        """
        Return the values for the requested statistic.
        
        Parameters
        ----------
        item_id : string
            The ID of the Item to retrieve the statistics for.
        stat_name : string
            The name of the statistic to get.

        Returns
        -------
        The requested statistics.
            The return type varies depending on the parameters:
            - the value returned from the statistic's function
            if both item_id and stat_name are given
            - a dictionary, keyed by the statistic names if only item_id is
            given; the values are those returned from the statistic's function
            - a dictionary, keyed by item ID if only stat_name is given;
            the values are those returned from the statistics' functions
            - this object's self.item_stats dictionary if both parameters are
            None; this dictionary is keyed by the item_id, and each value is
            another dictionary, keyed by the statistic name
            If one or both of the item_id or stat_name are not present in this
            object's statistics, then the stats returned in the above data
            structures will be one of:
            - an empty list if stat_name is a standard statistic or
            STATS_RAW or STATS_ARRAYINFO and
            calc_stats() was not called or read_data() failed.
            - None if stat_name is a user statistic and
            calc_stats() was not called or read_data() failed.

        """
        if item_id and stat_name:
            # Return the stats for item_id and statistic.
            ret_val = [] if stat_name in STATS_STD else None
            if item_id in self.item_stats:
                stats = self.item_stats[item_id]
                if stat_name in stats:
                    ret_val = stats[stat_name]
        elif item_id and not stat_name:
            # Return stats for the item.
            ret_val = {}
            if item_id in self.item_stats:
                ret_val = self.item_stats[item_id]
        elif stat_name and not item_id:
            # Return the given stat for all items.
            ret_val = {}
            for item_id, stats in self.item_stats.items():
                if stat_name in stats:
                    ret_val[item_id] = stats[stat_name]
                else:
                    ret_val[item_id] = [] if stat_name in STATS_STD else None
        else:
            # Return all stats.
            ret_val = self.item_stats
        return ret_val

    def reset(self, item=None):
        """
        Delete all previously calculated stats and raw arrays,
        and reset the STATS_RAW and STATS_ARRAYINFO lists.

        If the Item is supplied, then reset the stats for that Item only.

        If the supplied Item is not in self.item_stats, then add it.
        This is convenient if a call to read_data() failed and add_data()
        was not called. This allows the user to progress through failed reads,
        delaying the checks until after all reads are done and the stats
        calculated.

        Parameters
        ----------
        item : drill.ImageItem or pystac.Item

        """
        if item is None:
            for item_id, stats in self.item_stats.items():
                clean_stats = {
                    ITEM_KEY: stats[ITEM_KEY],
                    STATS_RAW: [],
                    STATS_ARRAYINFO: []}
                self.item_stats[item_id] = clean_stats
        else:
            clean_stats = {
                ITEM_KEY: item,
                STATS_RAW: [],
                STATS_ARRAYINFO: []}
            self.item_stats[item.id] = clean_stats


class MultibandAssetError(Exception):
    """Raised by the std stats functions when an asset has multiple bands."""
    pass


def check_std_arrays(item, asset_arrays):
    """
    Raise a MultibandAssetError if at least one of the arrays in
    asset_arrays contains multiple bands.

    Parameters
    ----------
    item : pystac.item.Item or drill.ImageItem
        Item the arrays belong to
    asset_arrays : numpy array of shape (layers, ysize, xsize)
        Arrays to check

    """
    errmsg = ""
    rast_counts = [arr.shape[0] for arr in asset_arrays]
    for idx, rcount in enumerate(rast_counts):
        if rcount > 1:
            errmsg += f"Array at index {idx} in asset_arrays contains " \
                      f"{rcount} layers.\n"
    if errmsg:
        errmsg = "ERROR: Cannot calculate the standard statistics " \
                 f"because one or more assets for item {item.id} " \
                 "has more than one band:\n " + errmsg
        raise MultibandAssetError(errmsg)


def std_stat_mean(asset_arrays):
    """
    Return a 1D array with the mean values for each masked array
    in the list of asset_arrays.

    Parameters
    ----------
    asset_arrays : numpy array of shape (layers, ysize, xsize)
        Array to find the mean on

    Returns
    -------
    numpy array of float
        The mean values - one for each input

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

    Parameters
    ----------
    asset_arrays : numpy array of shape (layers, ysize, xsize)
        Array to find the stdev on

    Returns
    -------
    numpy array of float
        The stdev values - one for each input

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

    Parameters
    ----------
    asset_arrays : numpy array of shape (layers, ysize, xsize)
        Array to find the count

    Returns
    -------
    numpy array of float
        The count values - one for each input

    """
    counts = [arr.count() for arr in asset_arrays]
    return numpy.array(counts)


def std_stat_countnull(asset_arrays):
    """
    Return a 1D array with the number of null pixels in each masked array
    in the list of asset_arrays.

    Parameters
    ----------
    asset_arrays : numpy array of shape (layers, ysize, xsize)
        Array to find the count

    Returns
    -------
    numpy array of float
        The count values - one for each input

    """
    counts = [arr.mask.sum() for arr in asset_arrays]
    return numpy.array(counts)


STD_STATS_FUNCS = {
    STATS_MEAN: std_stat_mean,
    STATS_STDEV: std_stat_stdev,
    STATS_COUNT: std_stat_count,
    STATS_COUNTNULL: std_stat_countnull
}
"""
A mapping of the standard stats to their functions.
"""
