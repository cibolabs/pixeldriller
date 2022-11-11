"""Tests for pixelstac.py"""

# TODO: add tests that handle geometry that cuts across the anti-meridian.
# See section 3.1.9 in https://www.rfc-editor.org/rfc/rfc7946#section-3.1

from pixelstac import pixelstac

from .fixtures import point_albers, point_wgs84
from .fixtures import COLLECTIONS, STAC_ENDPOINT, get_stac_client


def test_stac_search(point_wgs84):
    """Test pixelstac.stac_search."""
    # point_wgs84 intersects two items in the time range.
    items = pixelstac.stac_search(get_stac_client(), point_wgs84, COLLECTIONS)
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
    # The test is fairly simple, just see that the expected number of
    # PointStats and ItemStats instances were created. The other tests cover
    # the other functions that test_query calls.
    pixelstac.query(
        STAC_ENDPOINT, [point_albers, point_wgs84], ['B02', 'B03'],
        collections=COLLECTIONS)
    assert len(point_albers.get_stats()) == 3
    assert len(point_wgs84.get_stats()) == 2
