"""Tests for pixelstac.py"""

# TODO: add tests that handle geometry that cuts across the anti-meridian.
# See section 3.1.9 in https://www.rfc-editor.org/rfc/rfc7946#section-3.1

from pixelstac import pixelstac
from pixelstac import pointstats

from .fixtures import point_albers, point_wgs84
from .fixtures import COLLECTIONS, STAC_ENDPOINT, get_stac_client


def test_stac_search(point_wgs84):
    """Test pixelstac.stac_search."""
    # point_wgs84 intersects two items in the time range.
#    items = pixelstac.stac_search(get_stac_client(), point_wgs84, COLLECTIONS)
    item_points_list = pixelstac.stac_search(
        get_stac_client(), [point_wgs84], COLLECTIONS)
    # curl -s https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2A_54HVE_20220730_0_L2A | jq | less
#    assert len(items) == 2
    assert len(item_points_list) == 2
#    assert items[0].assets['B02'].href == \
    assert item_points_list[0].get_item().assets['B02'].href == \
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/" \
        "sentinel-s2-l2a-cogs/54/H/VE/2022/7/S2A_54HVE_20220730_0_L2A/B02.tif"
#    assert items[1].assets['B02'].href == \
    assert item_points_list[1].get_item().assets['B02'].href == \
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/" \
        "sentinel-s2-l2a-cogs/54/H/VE/2022/7/S2B_54HVE_20220725_0_L2A/B02.tif"


def test_drill(point_albers, point_wgs84):
    """Test pixelstac.query."""
    # The test is fairly simple, just see that the expected number of
    # PointStats and ItemStats instances were created. The other tests cover
    # the other functions that test_query calls.
    std_stats = [
        pointstats.STATS_MEAN,
        pointstats.STATS_COUNT, pointstats.STATS_COUNTNULL]
    def user_range(array_info, item, pt):
        return [a_info.data.max() - a_info.data.min() for a_info in array_info]
    user_stats = [("USER_RANGE", user_range)]
    pixelstac.drill(
        STAC_ENDPOINT, [point_albers, point_wgs84], ['B02', 'B03'],
        collections=COLLECTIONS, std_stats=std_stats, user_stats=user_stats)
    # Check that there are the same number of stats as there are Items that
    # the point intersects.
    assert len(point_albers.get_stats()) == 3
    assert len(point_wgs84.get_stats()) == 2
    # Check that the mean and range stats have been set for one item on 
    # one of the points.
    item_stats_dict = point_albers.get_stats()
    item_stats_obj = list(item_stats_dict.values())[0]
    assert len(item_stats_obj.get_stats(pointstats.STATS_MEAN)) == 2
    assert len(item_stats_obj.get_stats("USER_RANGE")) == 2
