"""Tests for pointstats.py"""

import pytest
import numpy

from pixelstac import pointstats
from .fixtures import point_one_item, real_item


def test_pointstats(point_one_item, real_item):
    """
    Test construction of PointStats object, and that the basic
    attributes are set.

    Note that the item real_item is returned from a search of
    the earth-search-stac using the point point_one_item.

    """
    pt_stats = pointstats.PointStats(
        point_one_item, [real_item], ['B02', 'B03'])
    assert pt_stats.pt.x == 136.5
    assert pt_stats.pt.y == -36.5
    assert pt_stats.asset_ids == ['B02', 'B03']


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
    """Test pointstats.std_stat_raw."""
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