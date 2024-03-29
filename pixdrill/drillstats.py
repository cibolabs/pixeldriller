"""
Contains the :class:`~pixdrill.drillstats.PointStats` class and standard
functions for calculating and storing the drilled pixel data and statistics
for a :class:`~pixdrill.drillpoints.Point`.

"""

# This file is part of Pixel Driller - for extracting pixels from
# imagery that correspond to survey field sites.
# Copyright (C) 2023 Cibolabs.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
"""
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
reference to the ``Item`` in :class:`~pixdrill.drillstats.PointStats`.
"""


class PointStats:
    """
    Holds the statistics of the pixel arrays for a Point for one or more Items.

    Parameters
    ----------
    pt : :class:`~pixdrill.drillpoints.Point` object
        The point associated with this ``PointStats`` object.

    Attributes
    ----------
    pt : the :class:`~pixdrill.drillpoints.Point` object
    item_stats : dictionary
        a dictionary containing the raster statistics within the region
        of interest of the associated point. The key is the Item ID, and the
        value is another dictionary. The second dictionary's keys are the names
        of the std_stats and user_stats passed to
        :func:`~pixdrill.drillstats.PointStats.calc_stats()`. Its values are
        a list of the return values of the corresponding stats
        functions. If the item is a :class:`pystac:pystac.Item`, there may be
        multiple elements in the list corresponding to the drilled
        ``Item's`` ``assets``.
    
    """
    def __init__(self, pt):
        """Constructor."""
        self.pt = pt
        self.item_stats = {}

    def add_data(self, item, arr_info):
        """
        Add the :class:`~pixdrill.image_reader.ArrayInfo` object as read from
        an ``Item's`` raster.

        Parameters
        ----------
        item : :class:`~pixdrill.drill.ImageItem` or :class:`pystac:pystac.Item`
        arr_info : :class:`pixdrill.image_reader.ArrayInfo`

        Notes
        -----
        Elements are appended to the lists that store the ``Item's``
        statistics::

            item_stats[item.id][STATS_RAW].append(arr_info.data)
            item_stats[item.id][STATS_ARRAYINFO].append(arr_info)

        where ``arr_info.data`` is the :ref:`masked array <numpy:maskedarray>`
        of data containing the pixels for one of the assets of the item.
        
        If item is a :class:`pystac:pystac.Item`, then
        :func:`~pixdrill.drillstats.PointStats.add_data()` may be called
        multiple times, once for each raster asset that is drilled.

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

        Parameters
        ----------
        item_id: str
            The ``Item's`` ID, for which stats will be calculated.
        std_stats : int, optional
            A list of ``STATS_*`` constants defined in the
            :mod:`pixdrill.drillstats` module, defining the standard stats
            to calculate.
        user_stats : list of ``(name, func)`` tuples, optional
            ``name`` is the name of the statistic.
            ``func`` is the user-defined function to calculate the statistic.

        Notes
        -----
        One of two of this class's functions must have been called first:

        #. :func:`~pixdrill.drillstats.PointStats.add_data` for each raster
           asset in the ``Item``
        #. :func:`~pixdrill.drillstats.PointStats.reset` to clear the stats

        See Also
        --------
        :func:`pixdrill.drill.drill` : for the signature of a user-supplied
            statistics function
            and how to retrieve the statistics from a
            :class:`~pixdrill.drillstats.Point`.

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
                message='Warning: converting a masked element to nan')
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
            The ID of the ``Item`` to retrieve the statistics for.
        stat_name : string
            The name of the statistic to get.

        Returns
        -------
        The requested statistic
            See the notes below

        Notes
        -----
        The return type varies depending on the parameters:

        - the value returned from the statistic's function
          if both ``item_id`` and ``stat_name`` are given
        - a dictionary, keyed by the statistic names if only ``item_id`` is
          given; the values are those returned from the statistic's function
        - a dictionary, keyed by item ID if only ``stat_name`` is given;
          the values are those returned from the statistics' functions
        - this object's ``self.item_stats`` dictionary if both parameters
          are ``None``; this dictionary is keyed by the ``item_id``, and each
          value is another dictionary, keyed by the statistic name
        
        If one or both of the ``item_id`` or ``stat_name`` are not present in
        this object's statistics, then the stats returned in the above data
        structures will be one of:

        - an empty list if ``stat_name`` is a standard statistic or
          :attr:`~pixdrill.drillstats.STATS_RAW` or
          :attr:`~pixdrill.drillstats.STATS_ARRAYINFO` and
          :func:`~pixdrill.drillstats.PointStats.calc_stats()` was not called
          or :func:`~pixdrill.drillpoints.ItemDriller.read_data` failed
        - ``None`` if ``stat_name`` is a user statistic and
          :func:`~pixdrill.drillstats.PointStats.calc_stats()` was not called
          or :func:`~pixdrill.drillpoints.ItemDriller.read_data` failed

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
        and reset the ``STATS_RAW`` and ``STATS_ARRAYINFO`` lists
        for ``self.item_stats[item.id]``.

        If the Item is supplied, then reset the stats for that Item only.

        Parameters
        ----------
        item : :class:`~pixdrill.drill.ImageItem` or :class:`pystac:pystac.Item`, optional

        Notes
        -----
        If the supplied ``item`` is not in ``self.item_stats``, then add it.
        This is convenient if a call to
        :func:`~pixdrill.drillpoints.ItemDriller.read_data` failed and
        :func:`~pixdrill.drillstats.PointStats.add_data` was not subsequently
        called. This allows the user to progress through failed reads,
        delaying the checks until after all reads are done and the stats
        calculated. To help, users can check the return value of
        :func:`~pixdrill.drillpoints.ItemDriller.read_data`.

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
    item : :class:`pystac:pystac.Item` or :class:`~pixdrill.drill.ImageItem`
        Item the arrays belong to.
    asset_arrays : numpy array of shape ``(n_bands, ysize, xsize)``
        Arrays to check.

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
    asset_arrays : list of :ref:`numpy:maskedarray` of shape (1, ysize, xsize)
        Arrays to find the mean for.

    Returns
    -------
    numpy array of float
        The mean values - one for each input array.

    """
    # Calculate the stat for each array because their x and y sizes will
    # differ if their pixel sizes are different.
    # If all values in an array are masked, then mean=numpy.nan.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            'ignore', category=UserWarning,
            message='Warning: converting a masked element to nan')
        mean_vals = [arr.mean() for arr in asset_arrays]
        return_val = numpy.array(mean_vals)
    return return_val


def std_stat_stdev(asset_arrays):
    """
    Return a 1D array with the standard deviation for each masked array
    in the list of asset_arrays.

    Parameters
    ----------
    asset_arrays : list of :ref:`numpy:maskedarray` of shape (1, ysize, xsize)
        Arrays to find the stdev for.

    Returns
    -------
    numpy array of float
        The stdev values - one for each input array.

    """
    # Calculate the stat for each array because their x and y sizes will
    # differ if their pixel sizes are different.
    # If all values in an array are masked, then stdev=numpy.nan.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            'ignore', category=UserWarning,
            message='Warning: converting a masked element to nan')
        stdev_vals = [arr.std() for arr in asset_arrays]
        return_val = numpy.array(stdev_vals)
    return return_val


def std_stat_count(asset_arrays):
    """
    Return a 1D array with the number of non-null pixels in each masked array
    in the list of asset_arrays.

    Parameters
    ----------
    asset_arrays : list of :ref:`numpy:maskedarray` of shape (1, ysize, xsize)
        Arrays to find the count for.

    Returns
    -------
    numpy array of float
        The count values - one for each input array.

    """
    counts = [arr.count() for arr in asset_arrays]
    return numpy.array(counts)


def std_stat_countnull(asset_arrays):
    """
    Return a 1D array with the number of null pixels in each masked array
    in the list of asset_arrays.

    Parameters
    ----------
    asset_arrays : list of :ref:`numpy:maskedarray` of shape (1, ysize, xsize)
        Arrays to find the null count for.

    Returns
    -------
    numpy array of float
        The null counts - one for each input array.

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
