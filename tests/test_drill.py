"""Tests for drill.py"""

# TODO: add tests that handle geometry that cuts across the anti-meridian.
# See section 3.1.9 in https://www.rfc-editor.org/rfc/rfc7946#section-3.1

from pixdrill import drill
from pixdrill import drillpoints

from .fixtures import point_albers, point_wgs84
from .fixtures import point_one_item, point_outside_bounds_1
from .fixtures import point_intersects, real_item, real_image_path
from .fixtures import COLLECTIONS, STAC_ENDPOINT, get_stac_client


def test_assign_points_to_stac_items(point_wgs84):
    """Test drill.assign_points_to_stac_items."""
    # point_wgs84 intersects two items in the time range.
    item_points_list = drill.assign_points_to_stac_items(
        get_stac_client(), [point_wgs84], COLLECTIONS)
    # curl -s https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2A_54HVE_20220730_0_L2A | jq | less
    assert len(item_points_list) == 2
    assert item_points_list[0].get_item().assets['B02'].href == \
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/" \
        "sentinel-s2-l2a-cogs/54/H/VE/2022/7/S2A_54HVE_20220730_0_L2A/B02.tif"
    assert item_points_list[1].get_item().assets['B02'].href == \
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/" \
        "sentinel-s2-l2a-cogs/54/H/VE/2022/7/S2B_54HVE_20220725_0_L2A/B02.tif"


def test_drill(point_albers, point_wgs84, point_intersects, real_image_path):
    """Test drill.drill."""
    # The test is fairly simple, just see that the expected number of
    # PointStats and ItemStats instances were created. The other tests cover
    # the other functions that test_query calls.
    std_stats = [
        drillpoints.STATS_MEAN,
        drillpoints.STATS_COUNT, drillpoints.STATS_COUNTNULL]
    def user_range(array_info, item, pt):
        return [a_info.data.max() - a_info.data.min() for a_info in array_info]
    user_stats = [("USER_RANGE", user_range)]
    drill.drill(
        [point_albers, point_wgs84, point_intersects], images=[real_image_path],
        stac_endpoint=STAC_ENDPOINT, raster_assets=['B02', 'B03'],
        collections=COLLECTIONS, std_stats=std_stats, user_stats=user_stats)
    # Check that there are the same number of stats as there are Items that
    # the point intersects.
    # These points do not intersect the image given by real_image_path. They
    # only Intersect Items in the STAC Catalogue.
    assert len(point_albers.get_stats()) == 3
    assert len(point_wgs84.get_stats()) == 2
    # Check that the mean and range stats have been set for the first
    # ItemStats object attached to point_albers.
    item_stats_dict = point_albers.get_stats()
    item_stats_obj = list(item_stats_dict.values())[0]
    assert len(item_stats_obj.get_stats(drillpoints.STATS_MEAN)) == 2
    assert len(item_stats_obj.get_stats("USER_RANGE")) == 2
    
    # point_intersects intersects one item in the STAC catalogue and the
    # image given by real_image_path.
    assert len(point_intersects.get_stats()) == 2
    stac_id = 'S2B_53HPV_20220728_0_L2A'
    item_ids = point_intersects.get_item_ids()
    assert stac_id in item_ids
    assert real_image_path in item_ids
    # Check that the mean and range stats have been set for the stac Item
    # and that the length is 2, one for each of B02 and B03.
    item_stats_obj = point_intersects.get_item_stats(stac_id)
    assert len(item_stats_obj.get_stats(drillpoints.STATS_MEAN)) == 2
    assert len(item_stats_obj.get_stats("USER_RANGE")) == 2
    # Check that the mean and range stats have been set for the ImageItem
    # and that the length is 1, because the Image is a single-band raster.
    item_stats_obj = point_intersects.get_item_stats(real_image_path)
    assert len(item_stats_obj.get_stats(drillpoints.STATS_MEAN)) == 1
    assert len(item_stats_obj.get_stats("USER_RANGE")) == 1


def test_assign_points_to_images(
    point_intersects, point_outside_bounds_1, real_image_path):
    """Test drill.assign_points_to_images."""
    item_points = drill.assign_points_to_images(
        [point_intersects, point_outside_bounds_1], [real_image_path])
    assert len(item_points) == 1
    ip = item_points[0]
    assigned_points = ip.get_points()
    assert len(assigned_points) == 1
    ap = assigned_points[0]
    assert ap == point_intersects
    i_ids = ap.get_item_ids()
    assert len(i_ids) == 1
    assert i_ids[0] == real_image_path
    # The same test, but this time explicitly set the image IDs.
    # Remove the previous items from the point first.
    ap.item_stats = {}
    item_points = drill.assign_points_to_images(
        [point_intersects, point_outside_bounds_1], [real_image_path],
        image_ids=['real_image'])
    assert len(item_points) == 1
    ip = item_points[0]
    assigned_points = ip.get_points()
    assert len(assigned_points) == 1
    ap = assigned_points[0]
    assert ap == point_intersects
    i_ids = ap.get_item_ids()
    assert len(i_ids) == 1
    assert i_ids[0] == 'real_image'
