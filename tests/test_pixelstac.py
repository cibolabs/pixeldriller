"""Tests for pixelstac.py"""

# TODO: add tests that handle geometry that cuts across the anti-meridian.
# See section 3.1.9 in https://www.rfc-editor.org/rfc/rfc7946#section-3.1

from pixelstac import pixelstac
from pixelstac import point

from .fixtures import point_albers, point_wgs84


def test_stac_search(point_wgs84):
    """Test pixelstac.stac_search."""
    # point_wgs84 intersects two items in the time range.
    endpoint = "https://earth-search.aws.element84.com/v0"
    collections = ['sentinel-s2-l2a-cogs']
    items = pixelstac.stac_search(endpoint, point_wgs84, collections)
    # curl -s https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2A_54HVE_20220730_0_L2A | jq | less
    assert len(items) == 2
    assert items[0].assets['B02'].href == \
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/" \
        "sentinel-s2-l2a-cogs/54/H/VE/2022/7/S2A_54HVE_20220730_0_L2A/B02.tif"
    assert items[1].assets['B02'].href == \
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/" \
        "sentinel-s2-l2a-cogs/54/H/VE/2022/7/S2B_54HVE_20220725_0_L2A/B02.tif"


def test_query(point_albers, point_wgs84):
    """Test pixelstac.query."""
    # TODO: complete implementation of this test.
    # The test is fairly simple, just see that the expected number of
    # PointStats and ItemStats instances were created. The other tests cover
    # the other functions that test_query calls.
    endpoint = "https://earth-search.aws.element84.com/v0"
    collections = ['sentinel-s2-l2a-cogs']
    pt_stats_list = pixelstac.query(
        endpoint, [point_albers, point_wgs84], ['B02', 'B03'],
        collections=collections)
    assert len(pt_stats_list) == 2
    pt_stats_albers = pt_stats_list[0]
    assert len(pt_stats_albers.item_stats_list) == 3
    pt_stats_wgs84 = pt_stats_list[1]
    assert len(pt_stats_wgs84.item_stats_list) == 2
