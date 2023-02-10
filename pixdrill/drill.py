"""
:func:`drill` is the main interface. Most interaction with this package
should be through this interface.

"""

# This file is part of Pixel Driller - for extracting pixels from
# imagery that correspond to survey field sites.
# Copyright (C) 2023 Cibolabs.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
from concurrent import futures
import datetime
from datetime import timezone
import functools

from osgeo import gdal
from pystac_client import Client

from . import drillpoints


def drill(points, images=None,
        stac_endpoint=None, raster_assets=None, collections=None,
        item_properties=None, nearest_n=0, std_stats=None, user_stats=None,
        ignore_val=None, concurrent=False):
    """
    Given a list of :class:`~pixdrill.drillpoints.Point` objects, compute the
    zonal statistics around each point for the specified images.

    Parameters
    ----------
    points : list of :class:`~pixdrill.drillpoints.Point` objects
        Points to drill the specified STAC endpoint or images for.
    images : list of strings
        GDAL-readable list of filenames to drill.
    stac_endpoint : string
        The STAC catalogue's URL.
    raster_assets : sequence of strings
        The raster assets to read from each Item in the STAC catalogue.
    collections : list of strings
        The STAC catalogue's collections to query. You would normally only
        specify one catalogue.
    item_properties : a list of objects
        These are for filtering the results of a STAC search. The list is
        passed to the :class:`pystacclient:pystac_client.Client` ``search``
        function using the ``query`` parameter.
    nearest_n : integer
        Only use up to n STAC Items that are nearest-in-time to the
        :class:`~pixdrill.drillpoints.Point`.
        A value of 0 means use all items found.
    std_stats : sequence of integers
        Constants from the :mod:`~pixdrill.drillstats` module
        (STATS_MEAN, STATS_STDEV etc) defining which 'standard'
        statistics to extract.
    user_stats : a list of tuples
        A user defined list of statistic names and functions. See the
        notes section below for a description of the function signatures.
    ignore_val : float or list of floats
        A value to use for the ignore value for rasters. Should only be
        used to override the image's no data values. See the notes below.
    concurrent : bool
        If True, will call :func:`~pixdrill.drill.calc_stats` for each Item
        to be drilled concurrently in a
        :class:`python:concurrent.futures.ThreadPoolExecutor`.

    Returns
    -------
    None
        Instead, the Points' :class:`pixdrill.drillstats.PointStats` objects
        are updated.

    Notes
    -----
    Images are specified in one of two ways. You may use either or both.
    The first method is to use ``images``
    parameter to supply a list of paths to rasters. A path is
    any string understood by GDAL. All bands in each image are read.
    
    The second method is to search a STAC endpoint for the raster.
    In this case, you must supply:
    
    - a list of ``raster_assets``
    - preferably, a name of one collection in the STAC catalogue
    - optionally, a list of item properties to filter the search by
    
    :func:`~pixdrill.drill.create_stac_drillers` is called to find all STAC
    items that intersect the survey points within their time-window;
    only up to the n nearest-in-time Items are used.

    For each raster, the pixels are drilled and zonal statistics calculated
    using the list of standard stats and user stats.   

    ``std_stats`` is a list of standard stats, as defined in the
    :mod:`pixdrill.drillstats` module with the ``STATS_*`` attributes.
    To use the standard statistics, every image must only contain one band.
 
    ``user_stats`` is a list of ``(name, function)`` pairs. The function is
    used to calculate a user-specified statistic.
    The signature of a user-supplied function must be::

        def user_func(array_info, item, pt):

    where:
    
    - array_info is a list of :class:`~pixdrill.image_reader.ArrayInfo`
      objects, one element for each image/asset read
    - item is the :class:`pystac:pystac.Item` object (for STAC rasters) or
      :class:`~pixdrill.drill.ImageItem` for an image.
    - pt is the :class:`~pixdrill.drillpoints.Point` object from around which
      the pixels were extracted

    Each :class:`~pixdrill.image_reader.ArrayInfo` instance has a ``data``
    attribute that contains a 3D numpy masked array with the pixel data for
    the asset defined by the instance's ``asset_id`` attribute.
    Note that each element in ``array_info`` corresponds to the
    ``raster_assets`` passed to :func:`~pixdrill.drill.drill`.

    The user function must return a value. It can be any data type.
    
    The value(s) returned from the stats functions are stored with the
    Point's :class:`~pixdrill.drillstats.PointStats` object. See the examples
    section below for how to retrieve them.

    ``item_properties`` allows you to filter your STAC search results if the
    STAC endpoint supports the
    `Query extension <https://github.com/stac-api-extensions/query>`__. An
    ``Item's`` properties are specific to the STAC collection. So you need to
    inspect the properties of a ``STAC Item`` in the collection to determine
    sensible values for this parameter.
    For example, the ``sentinel2-s2-l2a-cogs`` collection in the STAC
    Catalogue at endpoint https://earth-search.aws.element84.com/v0, has
    Sentinel2-specific properties that allow you to filter by the tile ID::

        tile = '54JVR'
        zone = tile[:2]
        lat_band = tile[2]
        grid_sq = tile[3:]
        item_properties = [
            f'sentinel:utm_zone={zone}',
            f'sentinel:latitude_band={lat_band}',
            f'sentinel:grid_square={grid_sq}']

    The ``ignore_val`` parameter allows you to set or override the pixel values
    to be ignored when calculating statistics.
    Whereever possible though, you should use the image's no data values.
    ``ignore_val`` is treated differently depending on whether the assets of
    a :class:`pystac:pystac.Item` are being read or a
    :class:`~pixdrill.drill.ImageItem` is being read.
    
    When reading from the assets of a :class:`pystac:pystac.Item`,
    ``ignore_val`` can be a list of values, a single values, or ``None``.
    A list of values is the null value per asset. It assumes all
    bands in an asset use the same null value.
    A single value is used for all bands of all assets.
    ``None`` means to use the no data value set on each the assets' bands.
    
    When reading the image of a :class:`pixdrill.drill.ImageItem`,
    ``ignore_val`` can be a single value or ``None``. A single value is used
    for all bands in the image. ``None`` means to use the each band's
    no data value.

    ``ignore_val`` is used for:
    
    - the mask value when 'removing' pixels from the raw arrays that
      are outside the region of interest, e.g. if the Point's footprint
      is a circle then we remove pixels from the raw rectangular arrays
    - excluding pixels from the stats calculations,
      those both within and outside the Point's footprint

    See Also
    --------

    pixdrill.example: a script that shows two usage patterns

    Examples
    --------

    With the statistics calculated, you retrieve them point-by-point.
    Use the Point's ``stats`` attribute. It is an instance of
    :class:`~pixdrill.drillstats.PointStats`. Use its
    :func:`~pixdrill.drillstats.PointStats.get_stats` function, which
    returns a dictionary, keyed by the Item's ID. So, the dictionary's
    length matches the number of Items that the Point intersects.
    For example::

        point_stats = pt.stats.get_stats()
        for item_id, item_stats in point_stats.items():
            print(f"    Item ID={item_id}")
            print(f"        Raw arrays : {item_stats[drillstats.STATS_RAW]}")
            print(f"        Mean values: {item_stats[drillstats.STATS_MEAN]}")
            print(f"        Counts     : {item_stats[drillstats.STATS_COUNT]}")
            print(f"        My Stat    : {item_stats["MY_STAT"]})
    
    A few things to note in this example:
    
    - the std_stats argument passed to :func:`~pixdrill.drill` would have been
      ``[drillstats.STATS_MEAN, drillstats.STATS_COUNT]``
    - the user_stats argument defines the ``MY_STAT`` statistic and its
      corresponding function name: ``[('MY_STAT', my_stat_function)]``
    - retrieve the numpy masked arrays using the key
      :attr:`pixdrill.drillstats.STATS_RAW`; these are always supplied
    - likewise, retrieve the ArrayInfo object using
      :attr:`pixdrill.drillstats.STATS_ARRAYINFO` (not shown)
        
    """
    logging.info(f"Searching {stac_endpoint} for {len(points)} points")
    drillers = []
    if stac_endpoint:
        client = Client.open(stac_endpoint)
        stac_drillers = create_stac_drillers(
            client, points, collections, raster_assets=raster_assets,
            item_properties=item_properties, nearest_n=nearest_n)
        drillers.extend(stac_drillers)
    if images:
        image_drillers = create_image_drillers(points, images)
        drillers.extend(image_drillers)
    # Read the pixel data from the rasters and calculate the stats.
    # On completion, each point will contain PointStats objects, with stats
    # stats for each item.
    logging.info(f"The {len(points)} points intersect {len(drillers)} items")
    if concurrent:
        logging.info("Running extract concurrently.")
        with futures.ThreadPoolExecutor() as executor:
            for dr in drillers:
                executor.submit(
                    calc_stats(
                        dr, std_stats=std_stats, user_stats=user_stats,
                        ignore_val=ignore_val))
    else:
        logging.info("Running extract sequentially.")
        for dr in drillers:
            calc_stats(
                dr, std_stats=std_stats, user_stats=user_stats,
                ignore_val=ignore_val)


def create_image_drillers(points, images, image_ids=None):
    """
    Return a list of :class:`~pixdrill.drillpoints.ItemDriller` objects,
    one for each image in the images list.

    Parameters
    ----------
    points : sequence of :class:`~pixdrill.drillpoints.Point` objects
        Points to drill the image for.
    images : sequence of strings
        GDAL-readable filenames to drill.
    image_ids : sequence of strings
        ID to use for each image. If not specified the image filename is used.

    Returns
    -------
    drillers : list of :class:`~pixdrill.drillpoints.ItemDriller` objects
        The ItemDriller for each image.

    """
    drillers = []
    if image_ids is None:
        image_ids = [None] * len(images)
    elif len(images) != len(set(image_ids)):
        errmsg = ("ERROR: the number of image IDs must be the same as the " +
                  "number of images and each ID must be unique")
        raise PixelStacError(errmsg)
    for image, image_id in zip(images, image_ids):
        image_item = ImageItem(image, id=image_id)
        driller = drillpoints.ItemDriller(image_item)
        drillers.append(driller)
        ds = gdal.Open(image, gdal.GA_ReadOnly)
        for pt in points:
            if pt.intersects(ds):
                driller.add_point(pt)
    return drillers


def create_stac_drillers(stac_client, points, collections, raster_assets=None,
        item_properties=None, nearest_n=0):
    """
    Search the list of collections in a STAC endpoint for items that
    intersect the x, y coordinate of the list of points and are within the
    Points' image-acquisition windows.

    Parameters
    ----------
    
    stac_client : str or pystac.Client object
        The endpoint URL to the STAC catalogue (str) or the
        :class:`pystacclient:pystac_client.Client` object returned from
        calling its ``open()`` function.
    points : list of :class:`~pixdrill.drillpoints.Point` objects
        Points to drill the endpoint for.
    collections : list of strings
        The names of the collections to query, normally only collection
        is given.
    raster_assets : list of strings, required
        Raster assets to use from the STAC endpoint.
    item_properties : a list of objects, optional
        These are passed to the :class:`pystacclient:pystac_client.Client`
        ``search()`` function using its ``query`` parameter.
    nearest_n : integer
        Only use up to n STAC Items that are nearest-in-time to the
        :class:`~pixdrill.drillpoints.Point`.
        A value of 0 means use all items found.

    Returns
    -------
    drillers : list of :class:`~pixdrill.drillpoints.ItemDriller` objects
        Each driller is the ItemDriller for a STAC Item.

    """
    if isinstance(stac_client, str):
        client = Client.open(stac_client)
    else:
        client = stac_client

    drillers = {}
    for pt in points:
        pt_json = {
            "type": "Point",
            "coordinates": [pt.wgs84_x, pt.wgs84_y]}
        # TODO: Do bounding boxes that cross the anti-meridian need to be
        # split in 2, or does the stac-client handle this case?
        # See: https://www.rfc-editor.org/rfc/rfc7946#section-3.1.9
        search = client.search(
            collections=collections,
            max_items=None,  # no limit on number of items to return
            intersects=pt_json,
            limit=500,  # results per page
            datetime=[pt.start_date, pt.end_date],
            query=item_properties)
        items = list(search.items())
        # Choose the nearest_n Items for the point
        if nearest_n > 0:
            sort_func = functools.partial(_time_diff, pt=pt)
            items = sorted(items, key=sort_func)[:nearest_n]
        # Group all points for each item together in an ItemDriller.
        for item in items:
            if item.id not in drillers:
                drillers[item.id] = drillpoints.ItemDriller(
                    item, asset_ids=raster_assets)
            drillers[item.id].add_point(pt)
    return list(drillers.values())


def _time_diff(item, pt):
    """
    Calculate the time difference, in seconds, between the STAC Item's
    acquisition time and the time of the survey. Use this function to sort the
    returned STAC Items so that the n_nearest can be selected.

    Parameters
    ----------
    item : :class:`pystac:pystac.Item`
        The Item containing information about the image acquisition time.
    pt : :class:`~pixdrill.drillpoints.Point`
        The survey point.

    Returns
    -------
        The number of seconds difference. This is a positive value, so this
        function cannot be used to determine if the image was acquired
        before or after the survey.

    Notes
    -----
    Assumes the datetime property of the STAC Item is formatted as
    'YYYY-MM-DDTHH:MM:SSZ', as per the date+time formatting rules in the
    `STAC Item Spec <https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md>`_.
    For example '2022-07-28T00:57:20Z'. A time zone offset is not expected
    because the spec specifies UTC.

    """
    acq_time = item.properties['datetime'].upper()
    acq_time = datetime.datetime.strptime(acq_time, "%Y-%m-%dT%H:%M:%SZ")
    acq_time = acq_time.replace(tzinfo=timezone.utc)
    diff = abs(acq_time - pt.t).total_seconds()
    return diff


def calc_stats(driller, std_stats=None, user_stats=None, ignore_val=None):
    """
    Calculate the statistics for all points in the ItemDriller objects.
    It reads the rasters and calculates the stats.

    Parameters
    ----------

    driller : a :class:`~pixdrill.drillpoints.ItemDriller`.
        The driller for the Item to be drilled.
    std_stats : sequence of integers
        Constants from the :mod:`~pixdrill.drillpoints` module
        ```(STATS_MEAN, STATS_STDEV etc)``
        defining which 'standard' statistics to extract.
    user_stats : function
        A list of (stat_name, stat_function) tuples containing the user defined
        function as specified by :func:`~pixdrill.drill.drill`.

    """
    msg = "Calculating stats for %i points in item %s."
    logging.info(msg, len(driller.points), driller.item.id)
    driller.read_data(ignore_val=ignore_val)
    driller.calc_stats(std_stats=std_stats, user_stats=user_stats)


class ImageItem:
    """
    Analogous to a :class:`pystac:pystac.Item` object, use an
    ``ImageItem`` object when constructing
    :class:`~pixdrill.drillpoints.ItemDriller` objects for an image file.

    Parameters
    ----------
    filepath: str
        Path to the GDAL-readable file.
    id:
        An optional ID for the ImageItem. If not given, filepath is used.

    Attributes
    ----------
    filepath : string
        Path to the GDAL file
    id : String
        ID to use for this item. Is the same as filepath unless overridden.

    """
    def __init__(self, filepath, id=None):
        """
        Construct the ImageItem. If id is None, then set the id attribute
        to filepath.

        """
        self.filepath = filepath
        if id:
            self.id = id
        else:
            self.id = filepath


class PixelStacError(Exception):
    pass
