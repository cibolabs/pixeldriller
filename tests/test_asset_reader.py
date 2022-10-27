"""Tests for asset_reader.py"""

from osgeo import gdal

from pixelstac import asset_reader
from .fixtures import point_one_item, real_item


def test_asset_filepath(real_item):
    """Test asset_reader.asset_filepath."""
    fpath = asset_reader.asset_filepath(real_item, 'B02')
    assert fpath == "/vsicurl/https://sentinel-cogs.s3.us-west-2.amazonaws.com/" \
            "sentinel-s2-l2a-cogs/53/H/PV/2022/7/S2B_53HPV_20220728_0_L2A/B02.tif"


def test_asset_info(real_item):
    """Test asset_reader.asset_info."""
    a_info = asset_reader.asset_info(real_item, 'B02')
    # The asset's properties are set in ImageInfo. See test_image_info
    # for a more complete test.
    assert a_info.x_min == 600000



def test_image_info():
    """Test asset_reader.ImageInfo."""
    href = "/vsicurl/https://sentinel-cogs.s3.us-west-2.amazonaws.com/" \
        "sentinel-s2-l2a-cogs/54/H/VE/2022/7/S2A_54HVE_20220730_0_L2A/B02.tif"
    a_info = asset_reader.ImageInfo(href)
    assert a_info.raster_count == 1
    assert a_info.x_min == 399960
    assert a_info.x_max == 509760
    assert a_info.y_min == 5890240
    assert a_info.y_max == 6000040
    assert a_info.nrows == 10980
    assert a_info.ncols == 10980
    assert a_info.x_res == 10
    assert a_info.y_res == 10
    assert a_info.nodataval == [0.0]
    assert a_info.transform == (399960.0, 10.0, 0.0, 6000040.0, 0.0, -10.0)
    assert a_info.data_type == gdal.GDT_UInt16
    assert a_info.data_type_name == 'UnsignedInt16'
    # Missing from test is checking value of a_info.projection.


def test_get_pix_window(real_item, point_one_item):
    """Test asset_reader.get_pix_window"""
    a_info = asset_reader.asset_info(real_item, 'B02') # 10 m pixels
    xoff, yoff, win_xsize, win_ysize = asset_reader.get_pix_window(
        point_one_item, a_info)
    assert xoff == 3428
    assert yoff == 4044
    assert win_xsize == 11
    assert win_ysize == 11
    a_info = asset_reader.asset_info(real_item, 'B11') # 20 pixels
    xoff, yoff, win_xsize, win_ysize = asset_reader.get_pix_window(
        point_one_item, a_info)
    assert xoff == 1714
    assert yoff == 2022
    assert win_xsize == 6
    assert win_ysize == 6


def test_read_roi(real_item, point_one_item):
    """Test asset_reader.read_roi()."""
    # point_one_item intersects this file
#    href = "/vsicurl/https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/53/H/PV/2022/7/S2B_53HPV_20220728_0_L2A/B02.tif"
#    href = asset_reader.asset_filepath(real_item, 'B02')
    asset_reader.read_roi(real_item, 'B02', point_one_item) # 10 m pixels
    asset_reader.read_roi(real_item, 'B11', point_one_item) # 20 m pixels

