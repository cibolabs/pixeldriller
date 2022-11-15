#!/usr/bin/env python

import datetime
from osgeo import osr

from pixelstac import pixelstac
from pixelstac import pointstats


def pt_1():
    """Create a point in Australian albers."""
    sp_ref = create_sp_ref(3577)
    x = 0
    y = -1123600
    date, t_delta = create_date(3)
    # Attach some other attributes
    other_atts = {"PointID": "abc123", "OwnerID": "xyz789"}
    pt = pointstats.Point(
        (x, y, date), sp_ref, t_delta, 50, pointstats.ROI_SHP_SQUARE,
        other_attributes=other_atts)
    return pt


def pt_2():
    """Create a point in WGS 84."""
    sp_ref = create_sp_ref(4326)
    x = 140
    y = -36.5
    date, t_delta = create_date(3)
    # Attach some other attributes
    other_atts = {"PointID": "def456", "OwnerID": "uvw000"}
    pt = pointstats.Point(
        (x, y, date), sp_ref, t_delta, 50, pointstats.ROI_SHP_SQUARE, 
        other_attributes=other_atts)
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
    pt = pointstats.Point(
        (x, y, date), sp_ref, t_delta, 50, pointstats.ROI_SHP_SQUARE,
        other_attributes=other_atts)
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
    pt = pointstats.Point(
        (x, y, date), sp_ref, t_delta, 50, pointstats.ROI_SHP_SQUARE,
        other_attributes=other_atts)
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
    Create a datetime.datetime instance for 28 July 2022 in UTC=10 hours
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


if __name__ == '__main__':
    endpoint = "https://earth-search.aws.element84.com/v0"
    collections = ['sentinel-s2-l2a-cogs']
    std_stats = [
        pointstats.STATS_RAW, pointstats.STATS_MEAN,
        pointstats.STATS_COUNT, pointstats.STATS_COUNTNULL]
    #pt_stats_list = pixelstac.query(
    points = [pt_1(), pt_2(), pt_3(), pt_4()]
    pixelstac.query(
        endpoint, points,
        ['B02', 'B11'], collections=collections,
        std_stats=std_stats)

    #for pt_stats in pt_stats_list:
    for pt in points:
        print(f"Stats for point: x={pt.x}, y={pt.y}")
        pid = pt.other_attributes["PointID"]
        print(f"with ID {pid}")
        for item_id, item_stats in pt.get_stats().items():
            print(f"    Item ID={item_id}") # The pystac.item.Item
#            print(f"        Raw arrays: {item_stats.get_stats(pointstats.STATS_RAW)}")
            print(f"        Mean values: {item_stats.get_stats(pointstats.STATS_MEAN)}")
            print(f"        Counts     : {item_stats.get_stats(pointstats.STATS_COUNT)}")
            print(f"        Null Counts: {item_stats.get_stats(pointstats.STATS_COUNTNULL)}")


# For future implementation.
#def my_func(list_of_asset_arrays):
#    """
#    A user-defined function for calculating zonal statistics. It takes a
#    list of 3D arrays. Each 3D array is the raster data for an asset of
#    a STAC Item, within the region of interest of a Point.
#    len(list_of_asset_arrays)==len(asset_ids). The order of the arrays
#    matches the order of the asset_ids.
#
#    The return value can be anything.
#
#    """
#    pass
