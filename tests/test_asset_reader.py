"""Tests for asset_reader.py"""

from pixelstac import asset_reader

from osgeo import gdal

def test_image_info():
    """Test asset_reader.ImageInfo."""
    href = "/vsicurl/https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/54/H/VE/2022/7/S2A_54HVE_20220730_0_L2A/B02.tif"
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
