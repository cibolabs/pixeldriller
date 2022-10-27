"""
Statistics and data extracted from the raster assets returned from
a pixelstac query.

"""

from . import asset_reader

# TODO: expand the set of stats
STATS_RAW = 'raw'
STATS_MEAN = 'mean'
STATS_STDDEV = 'stddev'


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
#        self.items = items
        self.asset_ids = asset_ids
        self.std_stats = std_stats
        self.user_stats = user_stats
        self.item_stats_list = [ItemStats(item, self) for item in items]
        # Can I send my'self' to ItemStats before exiting this constructor?
        # If not, add a second function, calc_stats, that creates the ItemStats objects.
        #self.item_stats = [ItemStats(item, self) for item in items]

    
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
    def __init__(self, item, point_stats):
        """Constructor."""
        self.item = item
        self.point_stats = point_stats
        self.stats = {}
        # Determine the pixel coordinates and mask from the Point's ROI.
        # The bounding box is used to extract the pixels from a region of
        # a raster and the shape is used as a mask, ignoring pixels outside
        # shape's boundary.

    
    def calc_stats(self):
        """
        Using the point's region of interest, read the array of pixels from
        all bands in each raster asset. Store the arrays in this instance's
        stats dictionary, with STATS_RAW as the key.

        Then calculate this instance's list of standard stats and user stats.

        """
        # # Create a gdal dataset for each asset in point_stats.asset_ids.
        # datasets = []
        # asset_arrays = []
#        for asset_id in self.asset_ids:
#            bbox = self.point_stats.pt.roi_bbox
            # filename = ... filename for asset
#            asset_reader.read_roi(filename, self.point_stats.pt)
#            asset_reader.read_roi(filename, asset_id, point_stats.pt)

        #     open ds for reading
        #     create 3D array by reading pixel values from each layer of
        #       the asset.
        #     append the array to asset_arrays list.
        # # Next, populate the self.stats dictionary, something like:
        # for std_stat in point_stats.std_stats:
        #     std_stat_func = STD_STAT_FUNCS[std_stat]
        #     self.stats[std_stat] = std_stat_func(asset_arrays)
        # for stat_name, stat_func in point_stats.user_stats:
        #     self.stats[stat_name] = stat_func(asset_arrays)
        pass



def std_stat_raw(asset_arrays):
    """
    The function used to calculate the zonal stats for STATS_RAW.

    Can only be used if all assets are single-layer rasters.

    Return a 3D array with shape=(len(asset_ids, nrows, ncols)).

    Raise a MultibandAssetError if at least one asset contains multiple bands.

    """
    pass


def std_stat_mean(asset_arrays):
    """
    The function used to calculate zonal stats for STATS_MEAN.
    It calculates the mean value for every layer in each array of asset_arrays.
    
    Can only be used if all assets are single-layer rasters.

    Return a 1D array containing the mean value of the pixels for each asset.
    
    Raise a MultibandAssetError if at least one asset contains multiple bands.

    """
    pass


# The standard stats and their functions.
STD_STATS_FUNCS = {
    STATS_RAW, std_stat_raw,
    STATS_MEAN, std_stat_mean
}


# I expect we'll use wld2pix when reading data from gdal datasets.
# I'm not sure if we'll need pix2wld.
# Both functions taken from rios.

#def wld2pix(transform, geox, geoy):
#    """converts a set of map coords to pixel coords"""
#    x = (transform[0] * transform[5] - 
#        transform[2] * transform[3] + transform[2] * geoy - 
#        transform[5] * geox) / (transform[2] * transform[4] - transform[1] * transform[5])
#    y = (transform[1] * transform[3] - transform[0] * transform[4] -
#        transform[1] * geoy + transform[4] * geox) / (transform[2] * transform[4] - transform[1] * transform[5])
#    return (x, y)


#def pix2wld(transform, x, y):
#    """converts a set of pixels coords to map coords"""
#    geox = transform[0] + transform[1] * x + transform[2] * y
#    geoy = transform[3] + transform[4] * x + transform[5] * y
#
#    return (geox, geoy)

class MultibandAssetError(Exception):
    """Raised by the std stats functions when an asset has multiple bands."""
    pass
