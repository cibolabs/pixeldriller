"""Tests for pixelstac.py"""

# TODO: add tests that handle geometry that cuts across the anti-meridian.
# See section 3.1.9 in https://www.rfc-editor.org/rfc/rfc7946#section-3.1

from pixelstac import pixelstac
from pixelstac import point

from .fixtures import point_albers, point_wgs84


#def test_query():
#    """
#    pixelstac.query is the interface to the pixelstac module. So this function
#    tests the query algorithm.
#
#    TODO: Complete implementing this test, at the bottom of this test file.
#
#    """
#    # curl -s https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2B_53HPV_20220728_0_L2A | jq | less
#    endpoint = "https://earth-search.aws.element84.com/v0"
#    # The first two of these return no results, the third one returns one result.
#    # First one fails because the timezone is not specified, the second fails
#    # because we only use a single time to find results and it must match
#    # the file date-time, which is a big ask.
#    # The pystac_client docs state that
#    # timezone unaware datetime objects are assumed to be utc, but that doesn't 
#    # see to be the case in practice. So it's best to specify the timezone.
#    # If non-utc timezone is given pystac-client converts it to utc.
#    # date = datetime.datetime(2022, 7, 28, 0, 57, 20) # TODO: allow time?
#    # date = datetime.datetime(2022, 7, 28, tzinfo=datetime.timezone.utc) # TODO: allow time?
#    date = datetime.datetime(2022, 7, 28, 0, 57, 20, tzinfo=datetime.timezone.utc) # TODO: allow time?
#    #date = datetime.datetime(2022, 7, 28) # TODO: allow time?
#    date = datetime.datetime(2022, 7, 28, tzinfo=datetime.timezone.utc) # TODO: allow time?
#    date = datetime.datetime(2022, 7, 28, tzinfo=datetime.timezone(datetime.timedelta(hours=10))) # TODO: allow time?
#    print(date.isoformat())
#    point = (136.5, -36.5, date)
#    t_delta = datetime.timedelta(days=1)
#    # The following point/t_delta matches two files.
##    point = (140, -36.5, date)
##    t_delta = datetime.timedelta(days=3)
#    assets = ["B02"]
#    pixelstac.query(endpoint, [point], None, None, assets, t_delta=t_delta)
##    tile = '54JVR'
##    zone = tile[:2]
##    lat_band = tile[2]
##    grid_sq = tile[3:]
##    properties = [
##        f'sentinel:utm_zone={zone}',
##        f'sentinel:latitude_band={lat_band}',
##        f'sentinel:grid_square={grid_sq}']
##    results = api.search(
##        collections =[collection.name],
##        max_items=100,
##        bbox=AUS_BBOX,
##        limit=500,
##        datetime=[earliest_date.isoformat(), latest_date.isoformat()],
##        query=properties)


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
    endpoint = "https://earth-search.aws.element84.com/v0"
    collections = ['sentinel-s2-l2a-cogs']
    items = pixelstac.query(
        endpoint, [point_albers, point_wgs84],
        100, point.ROI_SHP_SQUARE, ['B02', 'B03'],
        collections=collections)
    print(len(items))
