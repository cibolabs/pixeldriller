#!/usr/bin/env python

import datetime
from osgeo import osr

from pixelstac import pixelstac

points = []
points.append((
    1547384, -3610378, datetime.datetime(2022, 9, 19, 11, 30, 0)))
points.append(...)    
...

item_props = [
        f'sentinel:utm_zone={zone}',
        f'sentinel:latitude_band={lat_band}',
        f'sentinel:grid_square={grid_sq}']
asset_ids = ["B02", "B03", "B04"]
my_func = functools.partial(func_that_takes_an_array,
    func_otherarg1=value, func_otherarg2=value) 
results = pixelstac.query(
    "https://earth-search.aws.element84.com/v0",
    points, 50, 3577, datetime.timedelta(days=8),
    asset_ids, item_properties=item_props,
    stats=["MY_STAT", pixstac.MEAN, pixstac.RAW], ignore_val=[0,0,0],
    stats_funcs=[(my_func)])

# There is a set of statistics for each point. The size of the set
# is the number of STAC items (images) returned from the query for the point.
for stats_set in results:
    for pix_stats in stats_set:
        pix_stats.item # Name of STAC Item
        pix_stats.urls # URLs to each raster asset in asset_ids ( ["B02", "B03", "B04"] ) - do we need this?
        pix_stats.stats["MY_STAT"] # array (shape as defined by return value of my_func)
        pix_stats.stats[pixelstac.MEAN] # 3D array, with raw pixels in the ROI for asset_ids ( ["B02", "B03", "B04"] )
        pix_stats.stats[pixelstac.RAW] # 3D array, with raw pixels in the ROI for asset_ids ( ["B02", "B03", "B04"] )
