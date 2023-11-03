"""Tests for drillpoints.py"""

import pytest
from osgeo import osr

from pixdrill import drill
from pixdrill import drillstats
from pixdrill import drillpoints
from .fixtures import point_wgs84, point_wgs84_buffer_degrees
from .fixtures import point_albers, point_albers_buffer_degrees
from .fixtures import point_one_item
from .fixtures import point_outside_bounds_1
from .fixtures import real_item, real_image_path


def test_point(point_albers):
    """Test drillpoints.Point constructor."""
    assert point_albers.x == 0
    assert point_albers.y == -1123600
    assert point_albers.x_y == (0, -1123600)
    assert point_albers.t.strftime("%Y-%m-%d") == "2022-07-28"
    assert point_albers.start_date.strftime("%Y-%m-%d") == "2022-07-25"
    assert point_albers.end_date.strftime("%Y-%m-%d") == "2022-07-31"
    assert point_albers.buffer == 50
    assert point_albers.shape == drillpoints.ROI_SHP_SQUARE
    assert getattr(point_albers, "other_atts") == {
        "PointID": "def456", "OwnerID": "uvw000"}
    assert point_albers.stats.item_stats == {}
    # Also tests Point.to_wgs84()
    assert round(point_albers.wgs84_x, 1) == 132.0
    assert round(point_albers.wgs84_y, 1) == -10.7


def test_point_transform(point_albers):
    """Test Point.transform."""
    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(28353)
    easting, northing = point_albers.transform(dst_srs)
    assert round(easting, 2) == 171800.62
    assert round(northing, 2) == 8815628.66
    # Use the transform function to reproject a different coordinate.
    # The coordinate is offset from point_albers by 10 m in each direction.
    easting, northing = point_albers.transform(dst_srs, x=10, y=-1123610)
    assert round(easting, 2) == 171810.48
    assert round(northing, 2) == 8815618.49
    # Supply a src_srs and alternative x, y coords, effectively
    # reversing the first transformation.
    src_srs = osr.SpatialReference()
    src_srs.ImportFromEPSG(28353)
    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(3577)
    t_x, t_y = point_albers.transform(
        dst_srs, src_srs=src_srs, x=171800.62, y=8815628.66)
    assert round(t_x, 2) == 0.00
    assert round(t_y, 2) == -1123600.00


def test_point_change_buffer_units(
    point_albers, point_albers_buffer_degrees,
    point_wgs84, point_wgs84_buffer_degrees):
    """Test Point.change_buffer_units."""
    # There are five cases:
    # 1. convert buffer distance from metres to degrees where point
    #    is projected
    # 2. convert buffer distance from metres to degrees where point
    #    is geographic
    # 3. convert buffer distance from degrees to metres where point
    #    is projected
    # 4. convert buffer distance from degrees to metres where point
    #    is geographic
    # 5. no conversion needed, because the buffer units and destination
    #    spatial reference system are compatible.
    # Case 1.
    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(4326)
    t_buffer = point_albers.change_buffer_units(dst_srs)
    assert round(t_buffer, 6) == 0.000446
    # Case 2.
    t_buffer = point_wgs84.change_buffer_units(dst_srs)
    assert round(t_buffer, 6) == 0.000558
    # Case 3.
    dst_srs.ImportFromEPSG(28353)
    t_buffer = point_albers_buffer_degrees.change_buffer_units(dst_srs)
    assert round(t_buffer, 2) == 54.75
    # Case 4.
    dst_srs.ImportFromEPSG(28354)
    t_buffer = point_wgs84_buffer_degrees.change_buffer_units(dst_srs)
    assert round(t_buffer, 2) == 50.20
    # Case 5.
    # 5a. buffer in metres and a projected CRS.
    dst_srs.ImportFromEPSG(28354)
    t_buffer = point_albers.change_buffer_units(dst_srs)
    assert t_buffer == 50
    # 5b. buffer in degrees and a geographic CRS.
    dst_srs.ImportFromEPSG(4326)
    t_buffer = point_albers_buffer_degrees.change_buffer_units(dst_srs)
    assert t_buffer == 0.0005


def test_point_intersects(
        point_one_item, point_outside_bounds_1, real_image_path):
    """Test Point.intersects."""
    assert point_one_item.intersects(real_image_path)
    assert not point_outside_bounds_1.intersects(real_image_path)


def test_item_driller(real_item):
    """Test the ItemDriller constructor."""
    drlr = drillpoints.ItemDriller(real_item)
    with pytest.raises(drillpoints.ItemDrillerError) as excinfo:
        drlr.read_data()
    assert "Cannot read data from pystac.Item objects without " in str(excinfo)
    drlr.set_asset_ids(['blue', 'swir16'])
    drlr.read_data()
    assert drlr.item.id == "S2B_53HPV_20220728_0_L2A"
    assert drlr.asset_ids == ['blue', 'swir16']
    with pytest.raises(drillpoints.ItemDrillerError) as excinfo:
        drillpoints.ItemDriller(
            drill.ImageItem("fake_path"), asset_ids=['blue'])
    assert "do not set asset_ids when item is an ImageItem" in \
        str(excinfo.value)


def test_read_data(caplog, point_one_item, real_item):
    """
    Test the ItemDriller.read_data() and PointStats.add_data() functions.

    """
    drlr = drillpoints.ItemDriller(real_item, asset_ids=['blue', 'swir16'])
    drlr.add_point(point_one_item)
    read_ok = drlr.read_data()
    assert read_ok
    raw_stats = point_one_item.stats.get_stats(
        item_id=real_item.id, stat_name=drillstats.STATS_RAW) 
    assert len(raw_stats) == 2
    assert raw_stats[0].shape == (1, 11, 11)
    assert raw_stats[1].shape == (1, 6, 6)
    assert raw_stats[0][0, 0, 0] == 406  # Top-left array element.
    assert raw_stats[1][0, 5, 5] == 135  # Bottom-right array element.
    # The following fails because we give it the non-image, metadata, asset.
    # read_data() fails with a message being written to the log, and
    # the stats should return empty lists.
    point_one_item.stats.reset()  # scrub the stats.
    drlr = drillpoints.ItemDriller(
        real_item, asset_ids=['blue', 'swir16', 'granule_metadata'])
    drlr.add_point(point_one_item)
    read_ok = drlr.read_data()
    assert not read_ok
    assert "not recognized as a supported" in caplog.text
    drlr.calc_stats(std_stats=[drillstats.STATS_COUNT])
    raw_stats = point_one_item.stats.get_stats(
        item_id=real_item.id, stat_name=drillstats.STATS_RAW)
    assert len(raw_stats) == 0
    counts = point_one_item.stats.get_stats(
        item_id=real_item.id, stat_name=drillstats.STATS_COUNT)
    assert len(counts) == 0
