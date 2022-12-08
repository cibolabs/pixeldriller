"""Tests for pointstats.py"""

import pytest
import numpy
from osgeo import osr

from pixelstac import pointstats
from .fixtures import point_wgs84, point_wgs84_buffer_degrees
from .fixtures import point_albers, point_albers_buffer_degrees
from .fixtures import point_one_item, point_partial_nulls, point_all_nulls
from .fixtures import point_straddle_bounds_1, point_outside_bounds_1
from .fixtures import fake_item, real_item, real_image_path


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
    # 1. convert buffer distance from metres to degrees where point is projected
    # 2. convert buffer distance from metres to degrees where point is geographic
    # 3. convert buffer distance from degrees to metres where point is projected
    # 4. convert buffer distance from degrees to metres where point is geographic
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
 #   dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(28353)
    t_buffer = point_albers_buffer_degrees.change_buffer_units(dst_srs)
    assert round(t_buffer, 2) == 54.75
    # Case 4.
#    dst_srs = osr.SpatialReference()
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


def test_point_intersects(point_one_item, point_outside_bounds_1, real_image_path):
    """Test Point.intersects."""
    assert point_one_item.intersects(real_image_path)
    assert not point_outside_bounds_1.intersects(real_image_path)


def test_item_stats(point_one_item, real_item):
    """Test construction of the ItemStats object."""
    # PointStats creates a list of ItemStats objects.
    item_stats = pointstats.ItemStats(point_one_item, real_item)
    assert item_stats.item.id == "S2B_53HPV_20220728_0_L2A"
    assert item_stats.stats == {}


def test_item_points(real_item):
    """Test the ItemPoints constructor."""
    ip = pointstats.ItemPoints(real_item)
    with pytest.raises(pointstats.ItemPointsError) as excinfo:
        ip.read_data()
    assert "Cannot read data from pystac.Item objects without " in str(excinfo)
    ip.set_asset_ids(['B02', 'B11'])
    ip.read_data()
    assert ip.item.id == "S2B_53HPV_20220728_0_L2A"
    assert ip.asset_ids == ['B02', 'B11']
    with pytest.raises(pointstats.ItemPointsError) as excinfo:
        pointstats.ItemPoints(pointstats.ImageItem("fake_path"), asset_ids=['B02'])
    assert "do not set asset_ids when item is an ImageItem" in str(excinfo.value)


def test_read_data(point_one_item, real_item):
    """
    Test ItemPoints.read_data() and Point.add_data() function.

    """
    point_one_item.add_items([real_item])
    ip = pointstats.ItemPoints(real_item, asset_ids=['B02', 'B11'])
    ip.add_point(point_one_item)
    ip.read_data()
    item_stats = point_one_item.get_item_stats(real_item.id)
    raw_stats = item_stats.get_stats(pointstats.STATS_RAW)
    assert len(raw_stats) == 2
    assert raw_stats[0].shape == (1, 11, 11)
    assert raw_stats[1].shape == (1, 6, 6)
    assert raw_stats[0][0, 0, 0] == 406 # Top-left array element.
    assert raw_stats[1][0, 5, 5] == 135 # Bottom-right array element.


def test_calc_stats_image(point_one_item, real_image_path):
    """
    Test reading data from a normal image and not a Stac Item,
    and also calculate stats.

    """
    image_item = pointstats.ImageItem(real_image_path, id='real_image')
    point_one_item.add_items([image_item])
    ip = pointstats.ItemPoints(image_item)
    ip.add_point(point_one_item)
    ip.read_data()
    std_stats = [pointstats.STATS_COUNT]
    # A user function, which is a nonsense calculation of the sum of the scl pixels.
    def test_stat_1(array_info, item, pt):
        assert item.id == 'real_image'
        assert item.filepath == real_image_path
        stat_1 = array_info[0].data.sum()
        return stat_1
    user_stats = [("TEST_STAT_1", test_stat_1)]
    ip.calc_stats(std_stats=std_stats, user_stats=user_stats)
    item_stats = point_one_item.get_item_stats(image_item.id)
    raw_stats = item_stats.get_stats(pointstats.STATS_RAW)
    assert len(raw_stats) == 1
    assert raw_stats[0].shape == (1, 6, 6)
    stat_1 = item_stats.get_stats("TEST_STAT_1")
    assert stat_1 == 216 # each of the 36 elements in the raw array is 6.


def test_calc_stats(point_one_item, real_item):
    """Test the calc_stats methods of both PointStats and ItemStats."""
    # Standard functions.
    std_stats = [
        pointstats.STATS_RAW, pointstats.STATS_MEAN, pointstats.STATS_STDEV,
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
    ip = pointstats.ItemPoints(real_item, asset_ids=['B02', 'B11'])
    ip.add_point(point_one_item)
    ip.read_data()
    ip.calc_stats(std_stats=std_stats, user_stats=user_stats)
    item_stats = point_one_item.get_item_stats(real_item.id)
    # Standard stats
    assert pointstats.STATS_RAW in item_stats.stats
    assert pointstats.STATS_MEAN in item_stats.stats
    assert pointstats.STATS_STDEV in item_stats.stats
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
    # Test the Point.get_stat function.
    stdev = point_one_item.get_stat(real_item.id, pointstats.STATS_STDEV)
    assert list(stdev.round(2)) == [31.05, 24.92]


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
    ip = pointstats.ItemPoints(real_item, asset_ids=['B02', 'B11'])
    ip.add_point(point_partial_nulls)
    ip.read_data()
    ip.calc_stats(std_stats=std_stats)
    item_stats = point_partial_nulls.get_item_stats(real_item.id)
    mean_vals = item_stats.get_stats(pointstats.STATS_MEAN)
    assert list(mean_vals.round(2)) == [1473.43, 1019.69]
    # All nulls. Assumes the assets' no data values are set.
    point_all_nulls.add_items([real_item])
    ip = pointstats.ItemPoints(real_item, asset_ids=['B02', 'B11'])
    ip.add_point(point_all_nulls)
    ip.read_data()
    ip.calc_stats(std_stats=std_stats)
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
    ip = pointstats.ItemPoints(real_item, asset_ids=['B02', 'B11'])
    ip.add_point(point_all_nulls)
    with pytest.raises(AssertionError) as excinfo:
        ip.read_data(ignore_val=[-9999])
    assert "ignore_val list must be the same length as asset_ids" in str(excinfo.value)
    ip.read_data(ignore_val=-9999)
    ip.calc_stats(std_stats=std_stats)
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
    ip = pointstats.ItemPoints(real_item, asset_ids=['B02', 'B11'])
    ip.add_point(point_straddle_bounds_1)
    ip.read_data()
    ip.calc_stats(std_stats=std_stats)
    item_stats = point_straddle_bounds_1.get_item_stats(real_item.id)
    raw_b02 = item_stats.get_stats(pointstats.STATS_RAW)[0]
    assert raw_b02.shape == (1, 6, 6)
    assert raw_b02[0, 0, 0] == 3852
    mean_vals = item_stats.get_stats(pointstats.STATS_MEAN)
    assert list(mean_vals.round(2)) == [3520.44, 2146.22]
    # Case: the ROI is entirely outside the image extents.
    point_outside_bounds_1.add_items([real_item])
    ip = pointstats.ItemPoints(real_item, asset_ids=['B02', 'B11'])
    ip.add_point(point_outside_bounds_1)
    ip.read_data()
    ip.calc_stats(std_stats=std_stats)
    item_stats = point_outside_bounds_1.get_item_stats(real_item.id)
    raw_b02 = item_stats.get_stats(pointstats.STATS_RAW)[0]
    assert raw_b02.shape == (0,)
    mean_b02 = item_stats.get_stats(pointstats.STATS_MEAN)[0]
    assert numpy.isnan(mean_b02)


def test_reset(point_one_item, real_item):
    """
    Test resetting of stats and calculating a new set of stats.

    """
    ip = pointstats.ItemPoints(real_item, asset_ids=['B02', 'B11'])
    ip.add_point(point_one_item)
    std_stats = [pointstats.STATS_MEAN]
    ip.read_data()
    ip.calc_stats(std_stats=std_stats)
    i_stats = list(point_one_item.get_stats().values())[0]
    assert list(i_stats.stats.keys()) == [
        pointstats.STATS_RAW, pointstats.STATS_ARRAYINFO, pointstats.STATS_MEAN]
    assert len(point_one_item.get_stat(real_item.id, pointstats.STATS_MEAN)) == 2
    # Now do another read/calc stats, appending B8A data to the ItemStats objects.
    # Note that stats for B02 and B11 are recalculated as well.
    std_stats.append(pointstats.STATS_COUNT)
    ip.set_asset_ids(['B8A'])
    ip.read_data()
    ip.calc_stats(std_stats=std_stats)
    i_stats = list(point_one_item.get_stats().values())[0]
    assert list(i_stats.stats.keys()) == [
        pointstats.STATS_RAW, pointstats.STATS_ARRAYINFO,
        pointstats.STATS_MEAN, pointstats.STATS_COUNT]
    assert len(point_one_item.get_stat(real_item.id, pointstats.STATS_MEAN)) == 3
    # Now, reset the stats. This will wipe the ItemStats object from the point.
    # Then calculate stats on a different asset.
    ip.reset()
    std_stats = [pointstats.STATS_COUNT]
    ip.set_asset_ids(['SCL'])
    ip.read_data()
    ip.calc_stats(std_stats=std_stats)
    i_stats = list(point_one_item.get_stats().values())[0]
    assert list(i_stats.stats.keys()) == [
        pointstats.STATS_RAW, pointstats.STATS_ARRAYINFO, pointstats.STATS_COUNT]
    assert len(point_one_item.get_stat(real_item.id, pointstats.STATS_COUNT)) == 1
