"""Tests for point.py"""

from osgeo import osr

from pixelstac import point
#from pixelstac.point import Point

from .fixtures import point_albers, fake_item


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
    assert point_albers.buffer == 50
    assert point_albers.shape == point.ROI_SHP_SQUARE
    # Test the ROI creation.
#    point_albers.make_roi(50, point.ROI_SHP_SQUARE, fake_item, "B02")
#    assert point_albers.roi_shape == point.ROI_SHP_SQUARE
#    ulx, uly, lrx, lry = point_albers.roi_bbox
#    assert round(ulx, 2) == 171751.55
#    assert round(uly, 2) == 8815680.20
#    assert round(lrx, 2) == 171851.55
#    assert round(lry, 2) == 8815580.20


def test_point_transform(point_albers):
    """Test Point.transform_point."""
    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(28353)
    easting, northing = point_albers.transform(dst_srs)
    assert round(easting, 2) == 171800.62
    assert round(northing, 2) == 8815628.66
