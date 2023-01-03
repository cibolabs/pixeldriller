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


class PointStats:
    """
    A data structure that holds the statistics of the pixel arrays
    extracted from each image for a single item about a Point.

    Attributes
    ----------

    pt : Point object
        the point associated with this PointStats object
    item : pystac.item.Item or ImageItem
        the item to hold the stats for
    stats : dictionary
        a dictionary containing the raster statistics within the region
        of interest of the associated point.
        The dictionary's keys are defined by names of the std_stats and
        user_stats passed to PointStats.calc_stats(). The dictionary's values are
        a list of the return values of the corresponding stats functions. There
        is one element in the list for each raster asset.
    
    """
    def __init__(self, pt, item):
        """Constructor."""
        self.pt = pt
        self.item = item
        self.reset()

    
    def add_data(self, arr_info):
        """
        Add the image_reader.ArrayInfo object.

        Elements are added to two of the stats dictionary's entries::

            stats["STATS_RAW"].append(arr_info.data)
            stats["STATS_ARRAYINFO"].append(arr_info)

        arr_info.data is the numpy masked array of data, which contains the
        pixels for one of the assets of the item.

        Parameters
        ----------
        arr_info : image_reader.ArrayInfo

        """
        self.stats[STATS_RAW].append(arr_info.data)
        self.stats[STATS_ARRAYINFO].append(arr_info)

    
    def calc_stats(self, std_stats=None, user_stats=None):
        """
        Calculate the given list of standard and user-defined statistics
        on each asset's array of data.

        add_data() must be called first, for each raster asset.

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
        std_stats : int
            A list of STATS_* constants defined in the drillstats module
        user_stats : list of (name, func) tuples
            where func is the user functional to calculate a statistic
        
        """
        if std_stats:
            # Check that all arrays are single-band.
            # TODO: Permit std stats being calculated on multi-band images.
            # See https://github.com/cibolabs/pixelstac/issues/30.
            check_std_arrays(self.item, self.stats[STATS_RAW])
            warnings.filterwarnings(
                'ignore', message='Warning: converting a masked element to nan.',
                category=UserWarning)
            # STATS_RAW is already populated, or it is an empty list.
            stats_list = [
                s_s for s_s in std_stats if \
                s_s not in [STATS_RAW, STATS_ARRAYINFO]]
            for stat_name in stats_list:
                std_stat_func = STD_STATS_FUNCS[stat_name]
                self.stats[stat_name] = std_stat_func(
                    self.stats[STATS_RAW])
        if user_stats:
            for stat_name, stat_func in user_stats:
                self.stats[stat_name] = stat_func(
                    self.stats[STATS_ARRAYINFO], self.item, self.pt)


    def get_stats(self, stat_name):
        """
        Return the values for the requested statistic.
        
        Parameters
        ----------
        stat_name : string
            The name of the statistic to get

        Returns
        -------
        The return type for the requested statistic
            Or return an empty list if stat_name is a standard statistic, or
            stat_name is STATS_RAW or STATS_ARRAYINFO, and
            calc_stats() was not called or read_data() failed.
            Return None if stat_name is a user statistic and
            calc_stats() was not called or read_data() failed.

        """
        ret_val = [] if stat_name in STATS_STD else None
        if stat_name in self.stats:
            ret_val = self.stats[stat_name]
        return ret_val


    def reset(self):
        """
        Delete all previously calculated stats and raw arrays for this item,
        and reset the STATS_RAW and STATS_ARRAYINFO stats to empty lists.

        """
        self.stats = {}
        self.stats[STATS_RAW] = []
        self.stats[STATS_ARRAYINFO] = []


class MultibandAssetError(Exception):
    """Raised by the std stats functions when an asset has multiple bands."""
    pass


def check_std_arrays(item, asset_arrays):
    """
    Raise a MultibandAssetError if at least one of the arrays in
    asset_arrays contains multiple bands.

    Parameters
    ----------
    item : pystac.item.Item or ImageItem
        Item the arrays belong to
    asset_arrays : numpy array of shape (layers, ysize, xsize)
        Arrays to check

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
STATS_RAW is a special cased and handled in PointStats.add_data().
"""
