#!/usr/bin/env python

import datetime
from osgeo import osr

from pixelstac import pixelstac
from pixelstac import pointstats
from pixelstac import point

def my_func(list_of_asset_arrays):
    """
    A user-defined function for calculating zonal statistics. It takes a
    list of 3D arrays. Each 3D array is the raster data for an asset of
    a STAC Item, within the region of interest of a Point.
    len(list_of_asset_arrays)==len(asset_ids). The order of the arrays
    matches the order of the asset_ids.

    The return value can be anything.

    """
    pass


time_zone = datetime.timezone(datetime.timedelta(hours=10))
date = datetime.datetime(2022, 7, 28, tzinfo=time_zone)
t_delta = datetime.timedelta(days=3)
sp_ref_1 = osr.SpatialReference()
sp_ref_1.ImportFromEPSG(3577)
x_1 = 0
y_1 = -1123600
sp_ref_2 = osr.SpatialReference()
sp_ref_2.ImportFromEPSG(4326)
x_2 = 140
y_2 = -36.5
p1 = point.Point((x_1, y_1, date), sp_ref_1, t_delta)
p2 = point.Point((x_2, y_2, date), sp_ref_2, t_delta)
points = [p1, p2]

# Tile 54JVR
zone = 54
lat_band = 'J'
grid_sq = 'VR'
item_props = [
        f'sentinel:utm_zone={zone}',
        f'sentinel:latitude_band={lat_band}',
        f'sentinel:grid_square={grid_sq}']
buffer = 50
asset_ids = ["B02", "B03", "B04"]
results = pixelstac.query(
    "https://earth-search.aws.element84.com/v0",
    points, buffer, asset_ids, item_properties=item_props,
    std_stats=[pointstats.STATS_RAW, pointstats.STATS_MEAN],
    user_stats=[("MY_STAT", my_func)])

# There is a set of statistics for each point. The size of the set
# is the number of STAC items (images) returned from the query for the point.
for point_stats in results:
    point_stats.asset_ids # The list of assets passed to pixelstac.query
    for item_stats in point_stats:
        item_stats.item # The pystac.item.Item
        item_stats.item.assets['B02'].href # The url to the item's B02 asset.
        # A list of URLs to all of the item's assets of interest
        urls = [item_stats.item.assets[a_id].href for \
                a_id in point_stats.asset_ids]
        # The data type of MY_STAT is defined by the return value of my_func
        item_stats.stats["MY_STAT"] # array (shape as defined by return value of my_func)
        # If all assets are single-layer rasters, then this is a 3D array
        # with shape=(len(asset_ids, nrows, ncols)). If not, then... TBD.
        item_stats.stats[pointstats.STATS_RAW]
        # If all assets are single-layer rasters, then this is a 1D array with
        # the mean pixel value for each asset. If not, then... TBD.
        item_stats.stats[pointstats.STATS_MEAN]
