#!/usr/bin/env python

import datetime
from osgeo import osr

from pixelstac import pixstac

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
results = pixstac.query(
    "https://earth-search.aws.element84.com/v0",
    points, 50, 3577, datetime.timedelta(days=8),
    asset_ids, item_properties=item_props,
    stats=[pixstac.MEAN, pixstac.STDDEV, pixstac.RAW], ignore_val=[0,0,0],
    preproc=do_brdf)

# There is a set of statistics for each point. The size of the set
# is the number of STAC items (images) returned from the query for the point.
for stats_set in results:
    for pix_stats in stats_set:
        pix_stats.item # Name of STAC Item
        pix_stats.urls # URLs to each raster asset in asset_ids ( ["B02", "B03", "B04"] ) - do we need this?
        pix_stats.stats[pixstac.MEAN] # 1D array, with mean value of asset_ids ( ["B02", "B03", "B04"] )
        pix_stats.stats[pixstac.STDDEV] # 1D array, with stddev of asset_ids ( ["B02", "B03", "B04"] )
        pix_stats.stats[pixstac.RAW] # 3D array, with raw pixels in the ROI for asset_ids ( ["B02", "B03", "B04"] )
