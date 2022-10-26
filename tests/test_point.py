"""Tests for point.py"""

import datetime

import pytest
from osgeo import osr

from pixelstac import point
from pixelstac.point import Point

@pytest.fixture
def point_albers():
    """Create a point in Australian albers."""
    sp_ref = osr.SpatialReference()
    sp_ref.ImportFromEPSG(3577)
    x = 0
    y = -1123600
    # The pystac_client docs state that
    # timezone unaware datetime objects are assumed to be utc. But initial
    # testing showed that wasn't the case (need to revisit to confirm).
    # It's best to specify the timezone.
    # If a non-utc timezone is given pystac-client converts it to utc.
    time_zone = datetime.timezone(datetime.timedelta(hours=10))
    date = datetime.datetime(2022, 7, 28, tzinfo=time_zone)
    t_delta = datetime.timedelta(days=3)
    pt = Point((x, y, date), sp_ref, t_delta)
    return pt

@pytest.fixture
def fake_item():
    """Return a dummy pystac Item with attributes needed for the tests."""
    # curl -s https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2B_53HPV_20220728_0_L2A | jq | less
    class Item: pass
    class Asset: pass
    item = Item()
    item.assets = {"B02":Asset()}
    item.assets["B02"].href = \
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/" \
        "sentinel-s2-l2a-cogs/53/H/PV/2022/7/S2B_53HPV_20220728_0_L2A/B02.tif"
    return item


def test_point(point_albers, fake_item):
    """Test point.Point and its methods."""
    assert point_albers.x == 0
    assert point_albers.y == -1123600
    assert point_albers.t.strftime("%Y-%m-%d") == "2022-07-28"
    # Also tests Point.to_wgs84()
    assert round(point_albers.wgs84_x, 1) == 132.0
    assert round(point_albers.wgs84_y, 1) == -10.7
    assert point_albers.start_date.strftime("%Y-%m-%d") == "2022-07-25"
    assert point_albers.end_date.strftime("%Y-%m-%d") == "2022-07-31"
    # Test the ROI creation.
    point_albers.make_roi(50, point.ROI_SHP_SQUARE, fake_item, "B02")
    assert point_albers.roi_shape == point.ROI_SHP_SQUARE
    ulx, uly, lrx, lry = point_albers.roi_bbox
    assert round(ulx, 2) == 171751.55
    assert round(uly, 2) == 8815680.20
    assert round(lrx, 2) == 171851.55
    assert round(lry, 2) == 8815580.20


def test_transform_point(point_albers):
    """Test Point.transform_point."""
    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(28353)
    easting, northing = Point.transform_point(
        point_albers.x, point_albers.y, point_albers.sp_ref, dst_srs)
    assert round(easting, 2) == 171800.62
    assert round(northing, 2) == 8815628.66
