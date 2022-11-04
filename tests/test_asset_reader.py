"""Tests for asset_reader.py"""

import math

from osgeo import gdal

from pixelstac import asset_reader
from .fixtures import point_one_item, point_partial_nulls, point_all_nulls
from .fixtures import real_item


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
    assert a_info.data_type_name == 'UInt16'
    # Missing from test is checking value of a_info.projection.


def test_wld2pix(real_item, point_one_item):
    """Test asset_readet.wld2pix."""
    a_info = asset_reader.asset_info(real_item, 'B02') # 10 m pixels
    x, y = asset_reader.wld2pix(a_info.transform, a_info.x_min, a_info.y_max)
    assert math.isclose(x, 0, abs_tol=1e-9)
    assert math.isclose(y, 0, abs_tol=1e-9)
    x, y = asset_reader.wld2pix(a_info.transform, a_info.x_max, a_info.y_min)
    assert math.isclose(x, 10980, abs_tol=1e-9)
    assert math.isclose(y, 10980, abs_tol=1e-9)


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
#    print(href)
    # Sentinel-2 10 m pixels, 100 m square ROI, check the 4 pixels in top left.
    arr = asset_reader.read_roi(real_item, 'B02', point_one_item)
    assert arr.shape == (1, 11, 11)
    assert arr[0, 0, 0] == 406
    assert arr[0, 0, 1] == 426
    assert arr[0, 1, 0] == 372
    assert arr[0, 1, 1] == 416
    # Sentinel-2 20 m pixels, 100 m square ROI, check the 4 pixels in bottom right.
    arr = asset_reader.read_roi(real_item, 'B11', point_one_item)
    assert arr.shape == (1, 6, 6)
    assert arr[0, 4, 4] == 144
    assert arr[0, 4, 5] == 133
    assert arr[0, 5, 4] == 159
    assert arr[0, 5, 5] == 135


def test_read_roi_with_nulls(real_item, point_partial_nulls, point_all_nulls):
    """
    Test asset_reader.read_roi() for two special cases:
    1. where the point's ROI is on the edge of the imaged region so
       that the returned array contains a mix of valid and invalid values
    2. where the point's ROI is outside of the imaged region (but still within
       the image) extents so that the returned array is full of invalid values.

    This test assumes that the no data value is set in the metadata of
    the Item's assets.

    See also test_read_roi_outofrange.

    """
    arr = asset_reader.read_roi(real_item, 'B11', point_partial_nulls)
    assert arr.shape == (1, 6, 6)
    # assert the mask is as we expect it where the ROI begins to
    # overlap the null region.
    assert arr.mask[0, 0, 0] == False
    assert arr.mask[0, 3, 1] == False
    assert arr.mask[0, 4, 1] == True
    assert arr.mask[0, 4, 2] == False
    # assert that every pixel is masked where the ROI contains all nulls.
    arr = asset_reader.read_roi(real_item, 'B02', point_all_nulls)
    assert arr.shape == (1, 11, 11)
    assert arr.mask.all()
    # Now, explicitly set the null value, which overrides the ignore value
    # set on the assets.
    arr = asset_reader.read_roi(
        real_item, 'B11', point_partial_nulls, ignore_val=-9999)
    assert arr.shape == (1, 6, 6)
    # assert the mask is as we expect it where the ROI begins to
    # overlap the null region.
    assert arr.mask[0, 0, 0] == False
    assert arr.mask[0, 3, 1] == False
    assert arr.mask[0, 4, 1] == False
    assert arr.mask[0, 4, 2] == False
    # assert that every pixel is masked where the ROI contains all nulls.
    arr = asset_reader.read_roi(
        real_item, 'B02', point_all_nulls, ignore_val=-9999)
    assert arr.shape == (1, 11, 11)
    assert arr.mask.any() == False


#def test_read_roi_outofrange(real_item, point_straddles_range, point_outofrange):
#    """
#    Test asset_reader.read_roi() for two special cases:
#    1. where the point's ROI straddles the image extents.
#    2. where the point's ROI is entirely outside of the image extents.
#
#    """
#    pass
