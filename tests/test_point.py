"""Tests for point.py"""

from osgeo import osr

from pixelstac import point

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
    assert point_albers.other_attributes == {"PointID": "def456", "OwnerID": "uvw000"}


def test_point_transform(point_albers):
    """Test Point.transform_point."""
    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(28353)
    easting, northing = point_albers.transform(dst_srs)
    assert round(easting, 2) == 171800.62
    assert round(northing, 2) == 8815628.66
