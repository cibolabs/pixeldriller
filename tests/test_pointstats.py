"""Tests for pointstats.py"""

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
#    print(dir(real_item))
#    print(real_item.id)
#    print(real_item.assets['B02'].href)


def test_itemstats(point_one_item, real_item):
    """Test construction of the ItemStats object."""
    # PointStats creates a list of ItemStats objects.
    pt_stats = pointstats.PointStats(
        point_one_item, [real_item], ['B02', 'B03'])
    it_stats = pt_stats.item_stats_list[0]
    assert it_stats.item.id == "S2B_53HPV_20220728_0_L2A"
    assert it_stats.point_stats.pt.x == 136.5
    