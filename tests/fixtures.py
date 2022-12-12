"""pytest fixtures that are shared across tests."""

import datetime

import pytest
from osgeo import osr
from pystac_client import Client

from pixelstac import pixelstac
from pixelstac.pointstats import Point, ROI_SHP_SQUARE, ROI_SHP_CIRCLE

# We use Element84's STAC endpoint and search the sentinel-s2-l2a-cogs
# collection in many tests.

STAC_ENDPOINT = "https://earth-search.aws.element84.com/v0"
COLLECTIONS = ['sentinel-s2-l2a-cogs']
_STAC_CLIENT = None
def get_stac_client():
    """
    Get a STAC endpoint for working with.

    To minimse calls to the endpoint, use this function when you need a 
    STAC Client object to query the stac endpoint. The object is created
    once and reused across all tests.

    """
    global _STAC_CLIENT
    if not _STAC_CLIENT:
        _STAC_CLIENT = Client.open(STAC_ENDPOINT)
    return _STAC_CLIENT


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
    other_atts = {"PointID": "def456", "OwnerID": "uvw000"}
    pt = Point(
        (x, y, date), sp_ref, t_delta, 50, ROI_SHP_SQUARE)
    setattr(pt, "other_atts", other_atts)
    return pt


@pytest.fixture
def point_albers_buffer_degrees():
    """Create a point in Australian albers with a buffer distance in degrees."""
    sp_ref = create_sp_ref(3577)
    x = 0
    y = -1123600
    date, t_delta = create_date(3)
    other_atts = {"PointID": "def456", "OwnerID": "uvw000"}
    pt = Point(
        (x, y, date), sp_ref, t_delta, 0.0005, ROI_SHP_SQUARE,
        buffer_degrees=True)
    setattr(pt, "other_atts", other_atts)
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
def point_wgs84_buffer_degrees():
    """Create a point in WGS 84 with a buffer distance in degrees."""
    sp_ref = create_sp_ref(4326)
    x = 136.5
    y = -36.5
    date, t_delta = create_date(3)
    # A buffer of 0.00056 degrees is 50.20 m at this latitude.
    pt = Point(
        (x, y, date), sp_ref, t_delta, 0.00056, ROI_SHP_SQUARE,
        buffer_degrees=True)
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
def point_one_item_circle():
    """
    Create a point in WGS 84 that returns only one item from the
    earth-search stac for the sentinel-s2-l2a-cogs collection.
    It's region of interest is a circle with a 50 m radius.

    """
    sp_ref = create_sp_ref(4326)
    x = 136.5
    y = -36.5
    date, t_delta = create_date(1)
    pt = Point((x, y, date), sp_ref, t_delta, 50, ROI_SHP_CIRCLE)
    return pt


@pytest.fixture
def point_one_item_circle_small():
    """
    Create a point in WGS 84 that returns only one item from the
    earth-search stac for the sentinel-s2-l2a-cogs collection.
    It's region of interest is a circle with a radius small relative
    to the pixel size, so that it intersects fewer than 5 pixels,
    in this case it intersect 2 pixels.

    """
    sp_ref = create_sp_ref(4326)
    x = 136.5
    y = -36.5
    date, t_delta = create_date(1)
    pt = Point((x, y, date), sp_ref, t_delta, 3, ROI_SHP_CIRCLE)
    return pt


@pytest.fixture
def point_one_item_singular():
    """
    Create a point in WGS 84 that returns only one item from the
    earth-search stac for the sentinel-s2-l2a-cogs collection.
    It's region of interest is a singular point, created by setting buffer=0.

    """
    sp_ref = create_sp_ref(4326)
    x = 136.5
    y = -36.5
    date, t_delta = create_date(1)
    pt = Point((x, y, date), sp_ref, t_delta, 0, ROI_SHP_CIRCLE)
    return pt


@pytest.fixture
def point_intersects():
    """
    Create a point in WGS 84 that returns that is known to intersect
    the real_item below. It's the same as point_one_item above, but
    without the side-effect of having the real_item attached to it
    (see real_item below).

    """
    sp_ref = create_sp_ref(4326)
    x = 136.5
    y = -36.5
    date, t_delta = create_date(1)
    pt = Point((x, y, date), sp_ref, t_delta, 50, ROI_SHP_SQUARE)
    return pt


@pytest.fixture
def point_partial_nulls():
    """
    A point whose ROI contains a mix of valid and invalid pixel values
    when it intersects the real_item defined below.

    """
    sp_ref = create_sp_ref(4326)
    x = 137.3452
    y = -36.7259
    date, t_delta = create_date(1)
    pt = Point((x, y, date), sp_ref, t_delta, 50, ROI_SHP_SQUARE)
    return pt


@pytest.fixture
def point_straddle_bounds_1():
    """
    A point whose ROI straddles the bounds of the real_item defined below.

    """
    sp_ref = create_sp_ref(4326)
    # Point centred on UL corner pixel of image.
    x = 136.1115
    y = -36.1392
    date, t_delta = create_date(1)
    pt = Point((x, y, date), sp_ref, t_delta, 50, ROI_SHP_SQUARE)
    return pt


@pytest.fixture
def point_straddle_bounds_2():
    """
    A point whose ROI straddles the bounds of the real_item defined below.

    """
    sp_ref = create_sp_ref(4326)
    # Point centred on LR corner pixel of image.
    x = 137.3612
    y = -37.1107
    date, t_delta = create_date(1)
    pt = Point((x, y, date), sp_ref, t_delta, 50, ROI_SHP_SQUARE)
    return pt


@pytest.fixture()
def point_outside_bounds_1():
    """
    A point whose ROI is entirely outside the minimum x and y extents
    of the real_item defined below.

    """
    sp_ref = create_sp_ref(4326)
    # Point centred on UL corner pixel of image.
    x = 136.1107
    y = -36.1387
    date, t_delta = create_date(1)
    pt = Point((x, y, date), sp_ref, t_delta, 50, ROI_SHP_SQUARE)
    return pt


@pytest.fixture()
def point_outside_bounds_2():
    """
    A point whose ROI is entirely outside the maximum x extents
    of the real_item defined below.

    """
    sp_ref = create_sp_ref(4326)
    # Point centred on UL corner pixel of image.
    x = 137.3467
    y = -36.5957
    date, t_delta = create_date(1)
    pt = Point((x, y, date), sp_ref, t_delta, 50, ROI_SHP_SQUARE)
    return pt


@pytest.fixture()
def point_outside_bounds_3():
    """
    A point whose ROI is entirely outside the maximum LR extents
    of the real_item defined below.

    """
    sp_ref = create_sp_ref(4326)
    # Point centred on UL corner pixel of image.
    x = 137.3647
    y = -37.1175
    date, t_delta = create_date(1)
    pt = Point((x, y, date), sp_ref, t_delta, 50, ROI_SHP_SQUARE)
    return pt



@pytest.fixture
def point_all_nulls():
    """
    A point whose ROI contains a all null values when it intersects the
    real_item defined below.

    """
    sp_ref = create_sp_ref(4326)
    x = 137.3417
    y = -36.7294
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
    item.id = "Fake123"
    return item


@pytest.fixture
def real_item(point_one_item):
    """
    Return a real Item by calling pixelstac.stac_search using the
    earth-search endpoint on the sentinel-s2-l2a-cogs collection.

    Of course, this assumes that pixelstac.stac_search is functioning
    as expected - see test_pixelstac.test_stac_search.

    A side-effect of calling assign_points_to_stac_items() to find this
    real_item is that the item is attached to point_one_item,
    so point_one_item.get_item_ids() contains S2B_53HPV_20220728_0_L2A.

    """
    client = get_stac_client()
    # Retrieves the Item with id=S2B_53HPV_20220728_0_L2A
    # The URL to the B02 asset is:
    # https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/53/H/PV/2022/7/S2B_53HPV_20220728_0_L2A/B02.tif
    # Note that we return a pystac.StacItem, so the raster_assets here have
    # no effect; they're only needed by assign_points_to_stac_items.
    item_points = pixelstac.assign_points_to_stac_items(
        client, [point_one_item], COLLECTIONS)
    return item_points[0].get_item()


@pytest.fixture
def real_image_path(real_item):
    """
    Return a path to a real image that can be opened with gdal.Open.

    What's returned is the path to the real_item's SCL raster.

    """
    # /vsicurl/https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/53/H/PV/2022/7/S2B_53HPV_20220728_0_L2A/SCL.tif
    filepath = f"/vsicurl/{real_item.assets['SCL'].href}"
    return filepath
