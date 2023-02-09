#!/usr/bin/env python

"""
An example script::

    python3 -m pixdrill.example

Work through this example, starting in the :func:`run_typical` function,
in conjunction with the documentation for :func:`pixdrill.drill.drill`.

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

import datetime
from osgeo import osr
import numpy

from pixdrill import drill
from pixdrill import drillpoints
from pixdrill import drillstats


def pt_1():
    """Create a point in Australian albers."""
    x = 0
    y = -1123600
    date, t_delta = create_date(3)
    # Attach some other attributes
    other_atts = {"PointID": "abc123", "OwnerID": "xyz789"}
    pt = drillpoints.Point(
        x, y, date, 3577, t_delta, 50, drillpoints.ROI_SHP_SQUARE)
    setattr(pt, "other_atts", other_atts)
    return pt


def pt_2():
    """Create a point in WGS 84."""
    x = 140
    y = -36.5
    date, t_delta = create_date(3)
    # Attach some other attributes
    other_atts = {"PointID": "def456", "OwnerID": "uvw000"}
    pt = drillpoints.Point(
        x, y, date, 4326, t_delta, 50, drillpoints.ROI_SHP_SQUARE)
    setattr(pt, "other_atts", other_atts)
    return pt


def pt_3():
    """
    Create a point in WGS 84. This point intersects one item and
    contains a mix of null and non-null pixels.

    """
    sp_ref = create_sp_ref(4326)
    x = 137.3452
    y = -36.7259
    date, t_delta = create_date(1)
    # Attach some other attributes
    other_atts = {"PointID": "p-nulls", "OwnerID": "uvw000"}
    pt = drillpoints.Point(
        x, y, date, sp_ref, t_delta, 50, drillpoints.ROI_SHP_SQUARE)
    setattr(pt, "other_atts", other_atts)
    return pt


def pt_4():
    """
    Create a point in WGS 84. This point intersects two items.
    Its region of interest is only partially within the extents of
    one of the items, so the pixel counts are less than for the other
    item, which contains the entire ROI.

    """
    sp_ref = create_sp_ref(4326)
    x = 136.1115
    y = -36.1392
    date, t_delta = create_date(1)
    # Attach some other attributes
    other_atts = {"PointID": "straddle-extent", "OwnerID": "rst432"}
    pt = drillpoints.Point(
        x, y, date, sp_ref, t_delta, 50, drillpoints.ROI_SHP_SQUARE)
    setattr(pt, "other_atts", other_atts)
    return pt


def create_sp_ref(epsg_code):
    """
    Return an osr.SpatialReference instance with a coordinate reference
    system determined from the epsg code.

    """
    sp_ref = osr.SpatialReference()
    sp_ref.ImportFromEPSG(epsg_code)
    return sp_ref


def create_date(d_days):
    """
    Create a datetime.datetime instance for 28 July 2022 in UTC
    and a datetime.timedelta object of d_days.

    """
    # The pystac_client docs state that
    # timezone unaware datetime objects are assumed to be utc. But initial
    # testing showed that wasn't the case (need to revisit to confirm).
    # So it's best to explicitly specify the timezone.
    # If a non-utc timezone is given pystac-client converts it to utc.
    date = datetime.datetime(2022, 7, 28, tzinfo=datetime.timezone.utc)
    t_delta = datetime.timedelta(days=d_days)
    return date, t_delta


def user_range(array_info, item, pt):
    """
    Example of a function for a customised statistics.

    array_info is a list of image_reader.ArrayInfo objects,
    item is the pystac.Item or drill.ImageItem object, and pt
    is the drillpoints.Point object that intersects the item.

    The numpy.ma.masked_array objects are stored in ArrayInfo.data.

    The function returns a list where each element in the range (max-min)
    of the values in each array.

    item and pt are included in the function signature for use cases where
    the Item or Point's properties are needed.

    """
    return [a_info.data.max() - a_info.data.min() for a_info in array_info]


def get_image_path(stac_id, asset_id):
    """
    Get a path to the image represented by the stac_id and asset_id.

    stac_id is the ID of a item on the EarthSearch endpoint:
    https://earth-search.aws.element84.com/v0.
    For example: S2A_54HVE_20220730_0_L2A

    """
    components = stac_id.split('_')
    zone = components[1][:2]
    t1 = components[1][2]
    t2 = components[1][3:5]
    dt = datetime.datetime.strptime(components[2], "%Y%m%d")
    image_path = (
        "/vsicurl/https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/" +
        f"{zone}/{t1}/{t2}/{dt.year}/{dt.month}/{stac_id}/{asset_id}.tif")
    return image_path


def run_typical():
    """
    Demonstrate running the typical usage pattern to support
    the tutorial in the docs.
    """
    endpoint = "https://earth-search.aws.element84.com/v0"
    collections = ['sentinel-s2-l2a-cogs']
    std_stats = [
        drillstats.STATS_MEAN, drillstats.STATS_STDEV,
        drillstats.STATS_COUNT, drillstats.STATS_COUNTNULL]
    user_stats = [("USER_RANGE", user_range)]
    points = [pt_1(), pt_2(), pt_3(), pt_4()]
    # Direct-read these images that contain pt_2.
    aot_img = get_image_path("S2A_54HVE_20220730_0_L2A", "AOT")
    wvp_img = get_image_path("S2A_54HVE_20220730_0_L2A", "WVP")
    # Drill the rasters.
    drill.drill(
        points, images=[aot_img, wvp_img],
        stac_endpoint=endpoint, raster_assets=['B02', 'B11'],
        collections=collections,
        std_stats=std_stats, user_stats=user_stats)
    for pt in points:
        print(f"Stats for point: x={pt.x}, y={pt.y}")
        pid = getattr(pt, "other_atts")["PointID"]
        print(f"with ID {pid}")
        for item_id, item_stats in pt.stats.get_stats().items():
            print(f"    Item ID={item_id}")  # The pystac.Item or ImageItem ID
            array_info = item_stats[drillstats.STATS_ARRAYINFO]
            # The asset_id for arrays extracted from Images is None.
            asset_ids = [a_info.asset_id for a_info in array_info]
            print(f"        Asset IDs  : {asset_ids}")
#            print("        Raw arrays: "
#                f"{item_stats.get_stats(drillstats.STATS_RAW)}")
            print(f"        Mean values: {item_stats[drillstats.STATS_MEAN]}")
            print(f"        Std dev    : {item_stats[drillstats.STATS_STDEV]}")
            print(f"        Counts     : {item_stats[drillstats.STATS_COUNT]}")
            print("        Null Counts: "
                f"{item_stats[drillstats.STATS_COUNTNULL]}")
            print(f"        Ranges     : {item_stats['USER_RANGE']}")


def run_alternative():
    """
    Demonstrate running an alternative usage pattern
    to support the tutorial in the docs.
    """
    points = [pt_1(), pt_2(), pt_3(), pt_4()]
    endpoint = "https://earth-search.aws.element84.com/v0"
    collections = ['sentinel-s2-l2a-cogs']
    drillers = drill.create_stac_drillers(
        endpoint, points, collections)
    # Loop over each item, calculating the stats, reading the data and
    # calculating statistics on the continuous assets.
    for drlr in drillers:
        drlr.set_asset_ids(['B02', 'B11'])
        drlr.read_data()
        std_stats = [drillstats.STATS_MEAN, drillstats.STATS_STDEV]
        drlr.calc_stats(std_stats=std_stats)
    # Fetch the stats.
    for pt in points:
        stats_dict = pt.stats.get_stats()
        # Do something.
        print(f"CONTINUOUS Stats for point: x={pt.x}, y={pt.y}")
        pid = getattr(pt, "other_atts")["PointID"]
        print(f"with ID {pid}")
        for item_id, item_stats in stats_dict.items():
            print(f"    Item ID={item_id}")
            array_info = item_stats[drillstats.STATS_ARRAYINFO]
            asset_ids = [a_info.asset_id for a_info in array_info]
            print(f"        Asset IDs  : {asset_ids}")
            print(f"        Mean values: {item_stats[drillstats.STATS_MEAN]}")
            print(f"        Std dev    : {item_stats[drillstats.STATS_STDEV]}")
        pt.stats.reset()
    print("---------------------------------------\n")

    # Repeat, but this time for a categorical asset. Define a user function
    # that counts the number of pixels in category 7 or 8.
    def cat_count(array_info, item, pt):
        arr_data = array_info[0].data
        cats = [7, 8]
        cat_count = numpy.isin(arr_data, cats).sum()
        return cat_count

    for drlr in drillers:
        drlr.set_asset_ids(['SCL'])
        drlr.read_data()
        std_stats = [drillstats.STATS_COUNT]
        user_stats = [("CAT_COUNT", cat_count)]
        drlr.calc_stats(std_stats=std_stats, user_stats=user_stats)
    # Fetch the stats
    for pt in points:
        stats_dict = pt.stats.get_stats()
        # Do something.
        print(f"CATEGORICAL Stats for point: x={pt.x}, y={pt.y}")
        pid = getattr(pt, "other_atts")["PointID"]
        print(f"with ID {pid}")
        for item_id, item_stats in stats_dict.items():
            print(f"    Item ID={item_id}")
            array_info = item_stats[drillstats.STATS_ARRAYINFO]
            asset_ids = [a_info.asset_id for a_info in array_info]
            print(f"        Asset IDs: {asset_ids}")
            print(f"        Count    : {item_stats[drillstats.STATS_COUNT]}")
            print(f"        Cat count: {item_stats['CAT_COUNT']}")
        pt.stats.reset()


if __name__ == '__main__':
    print("=====================================")
    print("RUNNING TYPICAL USAGE PATTERN EXAMPLE")
    print("=====================================")
    run_typical()
    print("\n=========================================")
    print("RUNNING ALTERNATIVE USAGE PATTERN EXAMPLE")
    print("=========================================")
    run_alternative()
