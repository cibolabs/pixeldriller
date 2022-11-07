"""Tests for pointstats.py"""

import pytest
import numpy

from pixelstac import pointstats
from .fixtures import point_one_item, point_partial_nulls, point_all_nulls
from .fixtures import point_straddle_bounds_1, point_outside_bounds_1
from .fixtures import real_item


def test_pointstats(point_one_item, real_item):
    """
    Test construction of PointStats object, and that the basic
    attributes are set.

    Note that the item real_item is returned from a search of
    the earth-search-stac using the point point_one_item.

    """
    # The first attempt to create PointStats object should fail
    # because the ignore list is a different length to the assets list.
    with pytest.raises(AssertionError):
        pt_stats = pointstats.PointStats(
            point_one_item, [real_item], ['B02', 'B03'], ignore=[-9999])
    pt_stats = pointstats.PointStats(
        point_one_item, [real_item], ['B02', 'B03'], ignore=-9999)
    assert pt_stats.pt.x == 136.5
    assert pt_stats.pt.y == -36.5
    assert pt_stats.asset_ids == ['B02', 'B03']
    assert pt_stats.ignore_vals == [-9999, -9999]


def test_itemstats(point_one_item, real_item):
    """Test construction of the ItemStats object."""
    # PointStats creates a list of ItemStats objects.
    pt_stats = pointstats.PointStats(
        point_one_item, [real_item], ['B02', 'B03'])
    it_stats = pt_stats.item_stats_list[0]
    assert it_stats.item.id == "S2B_53HPV_20220728_0_L2A"
    assert it_stats.pt_stats.pt.x == 136.5


def test_calc_stats(point_one_item, real_item):
    """Test the calc_stats methods of both PointStats and ItemStats."""
    pt_stats = pointstats.PointStats(
        point_one_item, [real_item], ['B02', 'B11'],
        std_stats=[pointstats.STATS_RAW, pointstats.STATS_MEAN])
    pt_stats.calc_stats()
    assert len(pt_stats.item_stats_list) == 1
    item_stats = pt_stats.item_stats_list[0]
    assert pointstats.STATS_RAW in item_stats.stats
    assert pointstats.STATS_MEAN in item_stats.stats
    assert len(item_stats.stats[pointstats.STATS_RAW]) == 2
    assert len(item_stats.stats[pointstats.STATS_MEAN]) == 2
    mean_b02 = item_stats.stats[pointstats.STATS_MEAN][0]
    assert round(mean_b02, 2) == 441.41
    mean_b11 = item_stats.stats[pointstats.STATS_MEAN][1]
    assert round(mean_b11, 2) == 135.19


def test_std_stat_mean():
    """Test pointstats.std_stat_mean."""
    # All arrays are 3D.
    # All arrays must only contain one layer, so a.shape[0]=1.
    # Different lengths in the other dimensions are permitted.
    a1 = numpy.arange(10).reshape((1,2,5))
    a2 = numpy.arange(3,12).reshape((1,3,3))
    a3 = numpy.arange(4,16).reshape((1,4,3))
    mean_vals = pointstats.std_stat_mean([a1, a2, a3], ['B02', 'B08', 'B12'])
    assert list(mean_vals) == [4.5, 7.0, 9.5]
    # Multiband array will raise an exception.
    mba = numpy.arange(20).reshape((2,2,5))
    with pytest.raises(pointstats.MultibandAssetError) as excinfo:
        mean_vals = pointstats.std_stat_mean(
            [a1, mba, a3], ['B02', 'MBA', 'B08'])
    assert "MBA contains 2 layers" in str(excinfo.value)
    # Test use of masked-arrays. Mask the nine out of a1.
    m_a1 = numpy.ma.masked_array(a1, mask=a1==9, fill_value=-1)
    mean_vals = pointstats.std_stat_mean([m_a1, a2, a3], ['B02', 'B08', 'B12'])
    assert list(mean_vals) == [4.0, 7.0, 9.5]


def test_handle_nulls(point_partial_nulls, point_all_nulls, real_item):
    """
    Test handling of null values in the arrays when calculating stats.
    The test is based on the std_stat_mean function.
    Test two cases:
    1. where the point's ROI is on the edge of the imaged region so
       that the returned array contains a mix of valid and invalid values
    2. where the point's ROI is outside of the imaged region (but still within
       the image) extents so that the returned array is full of invalid values.

    """
    # Partials. Assumes the null value is set on the assets.
    pt_stats = pointstats.PointStats(
        point_partial_nulls, [real_item], ['B02', 'B11'],
        std_stats=[pointstats.STATS_RAW, pointstats.STATS_MEAN])
    pt_stats.calc_stats()
    item_stats = pt_stats.item_stats_list[0]
    mean_b02 = item_stats.stats[pointstats.STATS_MEAN][0]
    mean_b11 = item_stats.stats[pointstats.STATS_MEAN][1]
    assert round(mean_b02, 2) == 1473.43
    assert round(mean_b11, 2) == 1019.69
    # All nulls. Assumes the null value is set on the assets.
    pt_stats = pointstats.PointStats(
        point_all_nulls, [real_item], ['B02', 'B11'],
        std_stats=[pointstats.STATS_RAW, pointstats.STATS_MEAN])
    pt_stats.calc_stats()
    item_stats = pt_stats.item_stats_list[0]
    mean_b02 = item_stats.stats[pointstats.STATS_MEAN][0]
    mean_b11 = item_stats.stats[pointstats.STATS_MEAN][1]
    assert numpy.isnan(mean_b02)
    assert numpy.isnan(mean_b11)
    # Now overrides the asset's null values by specifying our own.
    # Test assumes that the asset's no-data value=0, thus giving a mean of 0.
    pt_stats = pointstats.PointStats(
        point_all_nulls, [real_item], ['B02', 'B11'],
        std_stats=[pointstats.STATS_RAW, pointstats.STATS_MEAN],
        ignore=-9999)
    pt_stats.calc_stats()
    item_stats = pt_stats.item_stats_list[0]
    mean_b02 = item_stats.stats[pointstats.STATS_MEAN][0]
    mean_b11 = item_stats.stats[pointstats.STATS_MEAN][1]
    assert mean_b02 == 0
    assert mean_b11 == 0
    

def test_handle_outofrange(
    point_straddle_bounds_1, point_outside_bounds_1, real_item):
    """
    Test handling of the cases where some or all of the ROI extends beyond the
    extents of the image. The tests are based on the std_stat_mean function.

    """
    # Case: the ROI straddles the image extents.
    pt_stats = pointstats.PointStats(
        point_straddle_bounds_1, [real_item], ['B02', 'B11'],
        std_stats=[pointstats.STATS_RAW, pointstats.STATS_MEAN])
    pt_stats.calc_stats()
    item_stats = pt_stats.item_stats_list[0]
    raw_b02 = item_stats.stats[pointstats.STATS_RAW][0]
    assert raw_b02.shape == (1, 6, 6)
    assert raw_b02[0, 0, 0] == 3852
    mean_b02 = item_stats.stats[pointstats.STATS_MEAN][0]
    assert round(mean_b02, 2) == 3520.44
    # Case: the ROI is entirely outside the image extents.
    # asset_reader.read_roi() returns an empty masked array when the ROI sits
    # entirely beyond the image's extents.
    pt_stats = pointstats.PointStats(
        point_outside_bounds_1, [real_item], ['B02', 'B11'],
        std_stats=[pointstats.STATS_RAW, pointstats.STATS_MEAN])
    pt_stats.calc_stats()
    item_stats = pt_stats.item_stats_list[0]
    raw_b02 = item_stats.stats[pointstats.STATS_RAW][0]
    assert raw_b02.shape == (0,)
    mean_b02 = item_stats.stats[pointstats.STATS_MEAN][0]
    assert numpy.isnan(mean_b02)
