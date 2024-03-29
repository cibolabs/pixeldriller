"""Tests for image_reader.py"""

import math

from osgeo import gdal

from pixdrill import image_reader
from .fixtures import point_one_item, point_partial_nulls, point_all_nulls
from .fixtures import point_straddle_bounds_1, point_straddle_bounds_2
from .fixtures import point_outside_bounds_1, point_outside_bounds_2
from .fixtures import point_outside_bounds_3, point_one_item_circle
from .fixtures import real_item, point_wgs84_buffer_degrees
from .fixtures import point_one_item_circle_small, point_one_item_singular


def test_image_reader(real_item):
    """test the ImageReader constructor."""
    reader = image_reader.ImageReader(real_item, asset_id='blue')
    assert reader.filepath == \
        "/vsicurl/https://sentinel-cogs.s3.us-west-2.amazonaws.com/" \
        "sentinel-s2-l2a-cogs/53/H/PV/2022/7/S2B_53HPV_20220728_0_L2A/B02.tif"
    assert reader.asset_id == 'blue'
    assert reader.info.x_min == 600000
    assert reader.info.x_max == 709800
    assert reader.info.y_min == 5890240
    assert reader.info.y_max == 6000040
    assert reader.info.nodataval == [0]
    assert reader.info.raster_count == 1
    assert reader.info.nrows == 10980
    assert reader.info.ncols == 10980
    assert reader.info.x_res == 10
    assert reader.info.y_res == 10
    assert reader.info.nodataval == [0.0]
    assert reader.info.transform == (
        600000.0, 10.0, 0.0, 6000040.0, 0.0, -10.0)
    assert reader.info.data_type == gdal.GDT_UInt16
    assert reader.info.data_type_name == 'UInt16'
    # Missing from test is checking value of a_info.projection.


def test_wld2pix(real_item):
    """Test ImageReader.wld2pix."""
    reader = image_reader.ImageReader(real_item, asset_id='blue')  # 10 m pixels
    a_info = reader.info
    x, y = reader.wld2pix(a_info.x_min, a_info.y_max)
    assert math.isclose(x, 0, abs_tol=1e-9)
    assert math.isclose(y, 0, abs_tol=1e-9)
    x, y = reader.wld2pix(a_info.x_max, a_info.y_min)
    assert math.isclose(x, 10980, abs_tol=1e-9)
    assert math.isclose(y, 10980, abs_tol=1e-9)


def test_pix2wld(real_item):
    """
    Test ImageReader.pix2wld.
    """
    reader = image_reader.ImageReader(real_item, asset_id='blue')  # 10 m pixels
    a_info = reader.info
    px, py = reader.pix2wld(0, 0)
    assert math.isclose(px, a_info.x_min, abs_tol=1e-9)
    assert math.isclose(py, a_info.y_max, abs_tol=1e-9)
    px, py = reader.pix2wld(a_info.ncols, a_info.nrows)
    assert math.isclose(px, a_info.x_max, abs_tol=1e-9)
    assert math.isclose(py, a_info.y_min, abs_tol=1e-9)


def test_get_pix_window(real_item, point_one_item, point_wgs84_buffer_degrees):
    """Test ImageReader.get_pix_window"""
    reader = image_reader.ImageReader(real_item, asset_id='blue')  # 10 m pixels
    xoff, yoff, win_xsize, win_ysize = reader.get_pix_window(point_one_item)
    assert xoff == 3428
    assert yoff == 4044
    assert win_xsize == 11
    assert win_ysize == 11
    reader = image_reader.ImageReader(real_item, asset_id='swir16')  # 20 m pixels
    xoff, yoff, win_xsize, win_ysize = reader.get_pix_window(point_one_item)
    assert xoff == 1714
    assert yoff == 2022
    assert win_xsize == 6
    assert win_ysize == 6
    # The following forces the point's buffer to be transformed from
    # degrees to metres.
    xoff, yoff, win_xsize, win_ysize = reader.get_pix_window(
        point_wgs84_buffer_degrees)
    assert xoff == 1714
    assert yoff == 2022
    assert win_xsize == 6
    assert win_ysize == 6


def test_read_roi(real_item, point_one_item):
    """Test ImageReader.read_roi()."""
    # point_one_item intersects this file
#    href = "/vsicurl/https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/53/H/PV/2022/7/S2B_53HPV_20220728_0_L2A/B02.tif"
#    href = image_reader.asset_filepath(real_item, 'blue')
#    print(href)
    # Sentinel-2 10 m pixels, 100 m square ROI, check the 4 pixels in top left.
    reader = image_reader.ImageReader(real_item, asset_id='blue')  # 10 m pixels
    arr_info = reader.read_roi(point_one_item)
    arr = arr_info.data
    assert arr.shape == (1, 11, 11)
    assert arr[0, 0, 0] == 406
    assert arr[0, 0, 1] == 426
    assert arr[0, 1, 0] == 372
    assert arr[0, 1, 1] == 416
    assert arr_info.asset_id == 'blue'
    assert arr_info.xoff ==3428
    assert arr_info.yoff ==4044
    assert arr_info.win_xsize == 11
    assert arr_info.win_ysize == 11
    assert arr_info.ulx == 634280.0
    assert arr_info.uly == 5959600.0
    assert arr_info.lrx == 634390.0
    assert arr_info.lry == 5959490.0
    assert arr_info.x_res == 10.0
    assert arr_info.y_res == 10.0

    # Sentinel-2 20 m pixels, 100 m square ROI, check the 4 pixels
    # in the bottom right.
    reader = image_reader.ImageReader(real_item, asset_id='swir16')  # 20 m pixels
    arr_info = reader.read_roi(point_one_item)
    arr = arr_info.data
    assert arr.shape == (1, 6, 6)
    assert arr[0, 4, 4] == 144
    assert arr[0, 4, 5] == 133
    assert arr[0, 5, 4] == 159
    assert arr[0, 5, 5] == 135
    assert arr_info.asset_id == 'swir16'
    assert arr_info.xoff == 1714
    assert arr_info.yoff == 2022
    assert arr_info.win_xsize == 6
    assert arr_info.win_ysize == 6
    assert arr_info.ulx == 634280.0
    assert arr_info.uly == 5959600.0
    assert arr_info.lrx == 634400.0
    assert arr_info.lry == 5959480.0
    assert arr_info.x_res == 20.0
    assert arr_info.y_res == 20.0


def test_read_roi_with_nulls(real_item, point_partial_nulls, point_all_nulls):
    """
    Test ImageReader.read_roi() for two special cases:
    1. where the point's ROI is on the edge of the imaged region so
       that the returned array contains a mix of valid and invalid values
    2. where the point's ROI is outside of the imaged region (but still within
       the image) extents so that the returned array is full of invalid values.

    This test assumes that the no data value is set in the metadata of
    the Item's assets.

    See also test_read_roi_outofrange.

    """
    reader = image_reader.ImageReader(real_item, asset_id='swir16')  # 20 m pixels
    arr_info = reader.read_roi(point_partial_nulls)
    arr = arr_info.data
    assert arr.shape == (1, 6, 6)
    # assert the mask is as we expect it where the ROI begins to
    # overlap the null region.
    assert bool(arr.mask[0, 0, 0]) is False
    assert bool(arr.mask[0, 3, 1]) is False
    assert bool(arr.mask[0, 4, 1]) is True
    assert bool(arr.mask[0, 4, 2]) is False
    # assert that every pixel is masked where the ROI contains all nulls.
    arr_info = reader.read_roi(point_all_nulls)
    arr = arr_info.data
    assert arr.shape == (1, 6, 6)
    assert arr.mask.all()
    # Now, explicitly set the null value, which overrides the ignore value
    # set on the assets.
    arr_info = reader.read_roi(point_partial_nulls, ignore_val=-9999)
    arr = arr_info.data
    assert arr.shape == (1, 6, 6)
    # assert the mask is as we expect it where the ROI begins to
    # overlap the null region.
    assert bool(arr.mask[0, 0, 0]) is False
    assert bool(arr.mask[0, 3, 1]) is False
    assert bool(arr.mask[0, 4, 1]) is False
    assert bool(arr.mask[0, 4, 2]) is False
    # Assert that no pixels in the returned array are masked, because
    # all pixel values are 0, and we've specified a different no data value.
    arr_info = reader.read_roi(point_all_nulls, ignore_val=-9999)
    arr = arr_info.data
    assert arr.shape == (1, 6, 6)
    assert bool(arr.mask.any()) is False


def test_read_roi_outofrange(
    real_item, point_straddle_bounds_1, point_straddle_bounds_2,
    point_outside_bounds_1, point_outside_bounds_2,
    point_outside_bounds_3):
    """
    Test ImageReader.read_roi() for two special cases:

    1. where the point's ROI straddles the image extents.
    2. where the point's ROI is entirely outside of the image extents.

    """
    # The first ROI straddles the UL pixel of the image. Its size is 
    # smaller than the nominal ROI size of (1, 11, 11).
    reader = image_reader.ImageReader(real_item, asset_id='blue')
    arr_info = reader.read_roi(point_straddle_bounds_1)
    arr = arr_info.data
    assert arr.shape == (1, 6, 6)
    assert arr[0, 0, 0] == 3852
    assert not arr_info.isempty()
    # The next ROI straddles the lower right corner. Note that the area
    # within the image bounds contains null pixels.
    arr_info = reader.read_roi(point_straddle_bounds_2)
    arr = arr_info.data
    assert arr.shape == (1, 5, 5)
    assert arr.size == 25  # number of pixel read from file
    assert arr.count() == 0  # number of valid (not-masked) pixels
    assert not arr_info.isempty()
    # The next ROI is entirely outside the UL corner
    arr_info = reader.read_roi(point_outside_bounds_1)
    arr = arr_info.data
    assert arr.count() == 0
    assert arr.shape == (0,)
    assert arr_info.isempty()
    # The next ROI is outside the eastern extents of the image.
    arr_info = reader.read_roi(point_outside_bounds_2)
    arr = arr_info.data
    assert arr.count() == 0
    assert arr.shape == (0,)
    assert arr_info.isempty()
    # The next ROI is outside the LR corner
    arr_info = reader.read_roi(point_outside_bounds_3)
    arr = arr_info.data
    assert arr.count() == 0
    assert arr.shape == (0,)
    assert arr_info.isempty()


def test_mask_roi_shape(
    real_item, point_one_item_circle, point_one_item_circle_small,
    point_one_item_singular):
    """
    Test reading of an array of data when the point's shape is a circle.
    Tests image_reader.read_roi() and mask_roi_shape().

    """
    # Sentinel-2 10 m pixels, 100 m square ROI, check the 4 pixels in top left.
    reader = image_reader.ImageReader(real_item, asset_id='blue') # 10 m pixels
    arr_info = reader.read_roi(point_one_item_circle)
    arr = arr_info.data
    assert arr.shape == (1, 11, 11)
    # Check values of the first and last rows
    assert arr.data[0, 0, :].tolist() == [
        0, 0, 0, 417, 410, 408, 425, 404, 398, 0, 0]
    assert arr.mask[0, 0, :].tolist() == [
        True, True, True, False, False, False, False, False, False, True, True]
    assert arr.data[0, 10, :].tolist() == [
        0, 0, 0, 456, 493, 469, 444, 444, 0, 0, 0]
    assert arr.mask[0, 10, :].tolist() == [
        True, True, True, False, False, False, False, False, True, True, True]
    # ROI is small relative to the pixel size.
    arr_info = reader.read_roi(point_one_item_circle_small)
    arr = arr_info.data
    assert arr.data[0, 0, :].tolist() == [482, 470]
    assert arr.mask[0, 0, :].tolist() == [False, False]
    # ROI is a singular point.
    arr_info = reader.read_roi(point_one_item_singular)
    arr = arr_info.data
    assert arr.data[0, 0, 0] == 482
    assert bool(arr.mask[0, 0, 0]) is False
