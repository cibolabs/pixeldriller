"""pytest fixtures that are shared across tests."""

import datetime

import pytest
from osgeo import osr

from pixelstac.point import Point, ROI_SHP_SQUARE
from pixelstac import pixelstac

def create_sp_ref(epsg_code):
    """
    Return an osr.SpatialReference instance with a coordinate reference
    system determined from the epsg code.

    """
    sp_ref = osr.SpatialReference()
    sp_ref.ImportFromEPSG(epsg_code)
    return sp_ref


def create_date(d_days):
    """
    Create a datetime.datetime instance for 28 July 2022 in UTC=10 hours
    and a datetime.timedelta object of d_days.

    """
    # The pystac_client docs state that
    # timezone unaware datetime objects are assumed to be utc. But initial
    # testing showed that wasn't the case (need to revisit to confirm).
    # It's best to specify the timezone.
    # If a non-utc timezone is given pystac-client converts it to utc.
    time_zone = datetime.timezone(datetime.timedelta(hours=10))
    date = datetime.datetime(2022, 7, 28, tzinfo=time_zone)
    t_delta = datetime.timedelta(days=d_days)
    return date, t_delta


@pytest.fixture
def point_albers():
    """Create a point in Australian albers."""
    sp_ref = create_sp_ref(3577)
    x = 0
    y = -1123600
    date, t_delta = create_date(3)
    pt = Point((x, y, date), sp_ref, t_delta, 50, ROI_SHP_SQUARE)
    return pt


@pytest.fixture
def point_wgs84():
    """Create a point in WGS 84."""
    sp_ref = create_sp_ref(4326)
    x = 140
    y = -36.5
    date, t_delta = create_date(3)
    pt = Point((x, y, date), sp_ref, t_delta, 50, ROI_SHP_SQUARE)
    return pt


@pytest.fixture
def point_one_item():
    """
    Create a point in WGS 84 that returns only one item from the
    earth-search stac for the sentinel-s2-l2a-cogs collection.

    """
    sp_ref = create_sp_ref(4326)
    x = 136.5
    y = -36.5
    date, t_delta = create_date(1)
    pt = Point((x, y, date), sp_ref, t_delta, 50, ROI_SHP_SQUARE)
    return pt


@pytest.fixture
def fake_item():
    """Return a dummy pystac Item with attributes needed for the tests."""
    # curl -s https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2B_53HPV_20220728_0_L2A | jq | less
    class Item: pass
    class Asset: pass
    item = Item()
    item.assets = {"B02":Asset()}
    item.assets["B02"].href = \
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/" \
        "sentinel-s2-l2a-cogs/53/H/PV/2022/7/S2B_53HPV_20220728_0_L2A/B02.tif"
    return item


@pytest.fixture
def real_item(point_one_item):
    """
    Return a real Item by calling pixelstac.stac_search using the
    earth-search endpoint on the sentinel-s2-l2a-cogs collection.

    Of course, this assumes that pixelstac.stac_search is functioning
    as expected - see test_pixelstac.test_stac_search.

    """
    endpoint = "https://earth-search.aws.element84.com/v0"
    collections = ['sentinel-s2-l2a-cogs']
    # Retrieves the Item with id=S2B_53HPV_20220728_0_L2A
    # The URL to the B02 asset is:
    # https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/53/H/PV/2022/7/S2B_53HPV_20220728_0_L2A/B02.tif
    items = pixelstac.stac_search(endpoint, point_one_item, collections)
    return items[0]