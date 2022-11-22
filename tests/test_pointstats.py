"""Tests for pointstats.py"""

import pytest
import numpy
from osgeo import osr

from pixelstac import pointstats
from .fixtures import point_albers
from .fixtures import point_one_item, point_partial_nulls, point_all_nulls
from .fixtures import point_straddle_bounds_1, point_outside_bounds_1
from .fixtures import fake_item, real_item


def test_point(point_albers):
    """Test pointstats.Point constructor."""
    assert point_albers.x == 0
    assert point_albers.y == -1123600
    assert point_albers.x_y == (0, -1123600)
    assert point_albers.t.strftime("%Y-%m-%d") == "2022-07-28"
    assert point_albers.start_date.strftime("%Y-%m-%d") == "2022-07-25"
    assert point_albers.end_date.strftime("%Y-%m-%d") == "2022-07-31"
    assert point_albers.buffer == 50
    assert point_albers.shape == pointstats.ROI_SHP_SQUARE
    assert getattr(point_albers, "other_atts") == {"PointID": "def456", "OwnerID": "uvw000"}
    assert point_albers.item_stats == {}
    # Also tests Point.to_wgs84()
    assert round(point_albers.wgs84_x, 1) == 132.0
    assert round(point_albers.wgs84_y, 1) == -10.7


def test_point_transform(point_albers):
    """Test Point.transform_point."""
    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(28353)
    easting, northing = point_albers.transform(dst_srs)
    assert round(easting, 2) == 171800.62
    assert round(northing, 2) == 8815628.66


def test_item_stats(point_one_item, real_item):
    """Test construction of the ItemStats object."""
    # PointStats creates a list of ItemStats objects.
    item_stats = pointstats.ItemStats(point_one_item, real_item)
    assert item_stats.item.id == "S2B_53HPV_20220728_0_L2A"
    assert item_stats.stats == {}


def test_read_data(point_one_item, real_item):
    """
    Test ItemPoints.read_data() and Point.add_data() function.

    """
    point_one_item.add_items([real_item])
    ip = pointstats.ItemPoints(real_item)
    ip.add_point(point_one_item)
    ip.read_data(['B02', 'B11'])
    item_stats = point_one_item.get_item_stats(real_item.id)
    raw_stats = item_stats.get_stats(pointstats.STATS_RAW)
    assert len(raw_stats) == 2
    assert raw_stats[0].shape == (1, 11, 11)
    assert raw_stats[1].shape == (1, 6, 6)
    assert raw_stats[0][0, 0, 0] == 406 # Top-left array element.
    assert raw_stats[1][0, 5, 5] == 135 # Bottom-right array element.


def test_calc_stats(point_one_item, real_item):
    """Test the calc_stats methods of both PointStats and ItemStats."""
    # Standard functions.
    std_stats = [
        pointstats.STATS_RAW, pointstats.STATS_MEAN,
        pointstats.STATS_COUNT, pointstats.STATS_COUNTNULL]
    # Couple of user functions. stat_1 is the sum of the mean of the two arrays.
    # stat_2 is a list with the min value of each array.
    def test_stat_1(array_info, item, pt):
        stat_1 = array_info[0].data.mean() + array_info[1].data.mean()
        return stat_1
    def test_stat_2(array_info, item, pt):
        stat_2 = [a_info.data.min() for a_info in array_info]
        return stat_2
    user_stats = [
        ("TEST_STAT_1", test_stat_1), ("TEST_STAT_2", test_stat_2)]
    point_one_item.add_items([real_item])
    ip = pointstats.ItemPoints(real_item)
    ip.add_point(point_one_item)
    ip.read_data(['B02', 'B11'])
    ip.calc_stats(std_stats, user_stats)
    item_stats = point_one_item.get_item_stats(real_item.id)
    # Standard stats
    assert pointstats.STATS_RAW in item_stats.stats
    assert pointstats.STATS_MEAN in item_stats.stats
    assert pointstats.STATS_COUNT in item_stats.stats
    assert pointstats.STATS_COUNTNULL in item_stats.stats
    mean_vals = item_stats.get_stats(pointstats.STATS_MEAN)
    counts = item_stats.get_stats(pointstats.STATS_COUNT)
    null_counts = item_stats.get_stats(pointstats.STATS_COUNTNULL)
    assert list(mean_vals.round(2)) == [441.41, 135.19]
    assert list(counts) == [121, 36]
    assert list(null_counts) == [0, 0]
    # User stats
    test_stat_1 = item_stats.get_stats("TEST_STAT_1")
    test_stat_2 = item_stats.get_stats("TEST_STAT_2")
    assert round(test_stat_1, 2) == 576.61
    assert test_stat_2 == [364, 75]


def test_check_std_arrays(fake_item):
    """Test that a Multiband array will raise an exception."""
    a1 = numpy.ma.arange(10).reshape((1,2,5))
    mba = numpy.ma.arange(20).reshape((2,2,5))
    a3 = numpy.ma.arange(4,16).reshape((1,4,3))
    with pytest.raises(pointstats.MultibandAssetError) as excinfo:
        pointstats.check_std_arrays(fake_item, [a1, mba, a3])
    assert "Array at index 1 in asset_arrays contains 2 layers" in str(excinfo.value)


@pytest.mark.filterwarnings("ignore:.*converting a masked element to nan.:UserWarning")
def test_std_stat_mean():
    """Test pointstats.std_stat_mean."""
    # All arrays are 3D.
    # All arrays must only contain one layer, so a.shape[0]=1.
    # Different lengths in the other dimensions are permitted.
    # Arrays must be masked arrays.
    a1 = numpy.ma.arange(10).reshape((1,2,5))
    a2 = numpy.ma.arange(3,12).reshape((1,3,3))
    a3 = numpy.ma.arange(4,16).reshape((1,4,3))
    mean_vals = pointstats.std_stat_mean([a1, a2, a3])
    assert list(mean_vals) == [4.5, 7.0, 9.5]
    # Test use of a mask. Mask the nine out of a1.
    m_a1 = numpy.ma.masked_array(a1, mask=a1==9, fill_value=-1)
    mean_vals = pointstats.std_stat_mean([m_a1, a2, a3])
    assert list(mean_vals) == [4.0, 7.0, 9.5]
    # Test empty arrays.
    e1 = numpy.ma.masked_array([], mask=True)
    mean_vals = pointstats.std_stat_mean([e1, m_a1, a2])
    assert numpy.isnan(mean_vals[0])
    assert list(mean_vals)[1:] == [4.0, 7.0]


def test_std_stat_count():
    """Test pointstats.std_stat_count."""
    a1 = numpy.arange(10).reshape((1,2,5))
    m_a1 = numpy.ma.masked_array(a1, mask=a1==0)
    m_a2 = numpy.ma.arange(4,20).reshape((1,4,4))
    m_a3 = numpy.ma.masked_array([], mask=True)
    counts = pointstats.std_stat_count([m_a1, m_a2, m_a3])
    assert list(counts) == [9, 16, 0]


def test_std_stat_countnull():
    """Test pointstats.std_stat_countnull."""
    a1 = numpy.arange(10).reshape((1,2,5))
    m_a1 = numpy.ma.masked_array(a1, mask=a1<3)
    m_a2 = numpy.ma.arange(4,20).reshape((1,4,4))
    m_a3 = numpy.ma.masked_array([], mask=True)
    counts = pointstats.std_stat_countnull([m_a1, m_a2, m_a3])
    assert list(counts) == [3, 0, 0]


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
    # Partials. Assumes the asets' no data values are set.
    std_stats = [pointstats.STATS_MEAN]
    point_partial_nulls.add_items([real_item])
    ip = pointstats.ItemPoints(real_item)
    ip.add_point(point_partial_nulls)
    ip.read_data(['B02', 'B11'])
    ip.calc_stats(std_stats, None)
    item_stats = point_partial_nulls.get_item_stats(real_item.id)
    mean_vals = item_stats.get_stats(pointstats.STATS_MEAN)
    assert list(mean_vals.round(2)) == [1473.43, 1019.69]
    # All nulls. Assumes the assets' no data values are set.
    point_all_nulls.add_items([real_item])
    ip = pointstats.ItemPoints(real_item)
    ip.add_point(point_all_nulls)
    ip.read_data(['B02', 'B11'])
    ip.calc_stats(std_stats, None)
    item_stats = point_all_nulls.get_item_stats(real_item.id)
    mean_vals = item_stats.get_stats(pointstats.STATS_MEAN)
    assert numpy.isnan(mean_vals[0])
    assert numpy.isnan(mean_vals[1])


def test_user_nulls(point_all_nulls, real_item):
    """
    Test hanlding null values in the array when the user specifies the
    null value. A user specified null value overrides the asset's no data
    value if it is set.

    """
    # The test assumes that the asset's no-data value=0, thus giving a mean of 0.
    std_stats = [pointstats.STATS_MEAN]
    point_all_nulls.add_items([real_item])
    ip = pointstats.ItemPoints(real_item)
    ip.add_point(point_all_nulls)
    with pytest.raises(AssertionError) as excinfo:
        ip.read_data(['B02', 'B11'], ignore_val=[-9999])
    assert "ignore_val list must be the same length as asset_ids" in str(excinfo.value)
    ip.read_data(['B02', 'B11'], ignore_val=-9999)
    ip.calc_stats(std_stats, None)
    item_stats = point_all_nulls.get_item_stats(real_item.id)
    mean_vals = item_stats.get_stats(pointstats.STATS_MEAN)
    assert list(mean_vals) == [0, 0]
    

def test_handle_outofrange(
    point_straddle_bounds_1, point_outside_bounds_1, real_item):
    """
    Test handling of the cases where some or all of the ROI extends beyond the
    extents of the image. The tests are based on the std_stat_mean function.

    """
    std_stats = [pointstats.STATS_MEAN]
    # Case: the ROI straddles the image extents.
    point_straddle_bounds_1.add_items([real_item])
    ip = pointstats.ItemPoints(real_item)
    ip.add_point(point_straddle_bounds_1)
    ip.read_data(['B02', 'B11'])
    ip.calc_stats(std_stats, None)
    item_stats = point_straddle_bounds_1.get_item_stats(real_item.id)
    raw_b02 = item_stats.get_stats(pointstats.STATS_RAW)[0]
    assert raw_b02.shape == (1, 6, 6)
    assert raw_b02[0, 0, 0] == 3852
    mean_vals = item_stats.get_stats(pointstats.STATS_MEAN)
    assert list(mean_vals.round(2)) == [3520.44, 2146.22]
    # Case: the ROI is entirely outside the image extents.
    point_outside_bounds_1.add_items([real_item])
    ip = pointstats.ItemPoints(real_item)
    ip.add_point(point_outside_bounds_1)
    ip.read_data(['B02', 'B11'])
    ip.calc_stats(std_stats, None)
    item_stats = point_outside_bounds_1.get_item_stats(real_item.id)
    raw_b02 = item_stats.get_stats(pointstats.STATS_RAW)[0]
    assert raw_b02.shape == (0,)
    mean_b02 = item_stats.get_stats(pointstats.STATS_MEAN)[0]
    assert numpy.isnan(mean_b02)
