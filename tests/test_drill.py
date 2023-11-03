"""Tests for drill.py"""

# TODO: add tests that handle geometry that cuts across the anti-meridian.
# See section 3.1.9 in https://www.rfc-editor.org/rfc/rfc7946#section-3.1

from datetime import timezone

from pixdrill import drill
from pixdrill import drillstats

from .fixtures import point_albers, point_wgs84
from .fixtures import point_one_item, point_outside_bounds_1
from .fixtures import point_intersects, real_item, real_image_path
from .fixtures import COLLECTIONS, STAC_ENDPOINT, get_stac_client


def test_assign_points_to_stac_items(point_wgs84):
    """Test drill.assign_points_to_stac_items."""
    # point_wgs84 intersects two items in the time range.
    drillers = drill.create_stac_drillers(
        get_stac_client(), [point_wgs84], COLLECTIONS)
    # curl -s https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2A_54HVE_20220730_0_L2A | jq | less
    assert len(drillers) == 2
    assert drillers[0].get_item().assets['blue'].href == \
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/" \
        "sentinel-s2-l2a-cogs/54/H/VE/2022/7/S2A_54HVE_20220730_0_L2A/B02.tif"
    assert drillers[1].get_item().assets['blue'].href == \
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/" \
        "sentinel-s2-l2a-cogs/54/H/VE/2022/7/S2B_54HVE_20220725_0_L2A/B02.tif"
    # Test the nearest_n parameter.
    drillers = drill.create_stac_drillers(
        get_stac_client(), [point_wgs84], COLLECTIONS, nearest_n=1)
    assert len(drillers) == 1
    assert drillers[0].item.id == "S2A_54HVE_20220730_0_L2A"


def test_drill(point_albers, point_wgs84, point_intersects, real_image_path):
    """Test drill.drill."""
    # The test is fairly simple, just see that the expected number of
    # PointStats and ItemStats instances were created. The other tests cover
    # the other functions that test_query calls.
    std_stats = [
        drillstats.STATS_MEAN,
        drillstats.STATS_COUNT, drillstats.STATS_COUNTNULL]

    def user_range(array_info, item, pt):
        return [a_info.data.max() - a_info.data.min() for a_info in array_info]
    user_stats = [("USER_RANGE", user_range)]
    drill.drill(
        [point_albers, point_wgs84, point_intersects],
        images=[real_image_path],
        stac_endpoint=STAC_ENDPOINT, raster_assets=['blue', 'green'],
        collections=COLLECTIONS, std_stats=std_stats, user_stats=user_stats)
    # Check that there are the same number of stats as there are Items that
    # the point intersects.
    # These points do not intersect the image given by real_image_path. They
    # only Intersect Items in the STAC Catalogue.
    assert len(point_albers.stats.item_stats) == 3
    assert len(point_wgs84.stats.item_stats) == 2
    # Check that the mean and range stats have been set for the first
    # ItemStats object attached to point_albers.
    item_stats = point_albers.stats.item_stats
    stats = list(item_stats.values())[0]
    assert len(stats[drillstats.STATS_MEAN]) == 2
    assert len(stats["USER_RANGE"]) == 2
    # point_intersects intersects one item in the STAC catalogue and the
    # image given by real_image_path.
    assert len(point_intersects.stats.item_stats) == 2
    stac_id = 'S2B_53HPV_20220728_0_L2A'
    # Check that the mean and range stats have been set for the stac Item
    # and that the length is 2, one for each of B02 and B03.
    stats = point_intersects.stats.item_stats[stac_id]
    assert len(stats[drillstats.STATS_MEAN]) == 2
    assert len(stats["USER_RANGE"]) == 2
    # Check that the mean and range stats have been set for the ImageItem
    # and that the length is 1, because the Image is a single-band raster.
    stats = point_intersects.stats.item_stats[real_image_path]
    assert len(stats[drillstats.STATS_MEAN]) == 1
    assert len(stats["USER_RANGE"]) == 1


def test_user_nulls(point_albers):
    """
    Test passing the null values through from the drill function.
    There's another test, test_drillstats.py::test_user_nulls, 
    which is a more comprehensive, downstream test.
    """
    drill.drill(
        [point_albers], stac_endpoint=STAC_ENDPOINT,
        raster_assets=['blue', 'green'],
        collections=COLLECTIONS, std_stats=[drillstats.STATS_MEAN],
        ignore_val=[434, 195])
    stats = point_albers.stats.get_stats(
        item_id="S2B_52LHP_20220730_0_L2A", stat_name=drillstats.STATS_RAW)
    # Four pixels are masked from blue and three from green.
    #assert stats[0].mask.sum() == 4
    assert stats[1].mask.sum() == 3


def test_assign_points_to_images(
    point_intersects, point_outside_bounds_1, real_image_path):
    """Test drill.assign_points_to_images."""
    drillers = drill.create_image_drillers(
        [point_intersects, point_outside_bounds_1], [real_image_path])
    assert len(drillers) == 1
    drlr = drillers[0]
    assigned_points = drlr.get_points()
    assert len(assigned_points) == 1
    ap = assigned_points[0]
    assert ap == point_intersects
    # The same test, but this time explicitly set the image IDs.
    # Remove the previous items from the point first.
    ap.items = {}
    drillers = drill.create_image_drillers(
        [point_intersects, point_outside_bounds_1], [real_image_path],
        image_ids=['real_image'])
    assert len(drillers) == 1
    drlr = drillers[0]
    assigned_points = drlr.get_points()
    assert len(assigned_points) == 1
    ap = assigned_points[0]
    assert ap == point_intersects


def test_time_diff(real_item, point_one_item):
    """Test drill._time_diff."""
    n_secs = drill._time_diff(real_item, point_one_item)
    assert n_secs == 39440.421
