"""
Contains the :class:`~pixdrill.drillpoints.Point` and
:class:`~pixdrill.drillpoints.ItemDriller` classes which define the
survey point's properties and are used to drill an ``Item's`` pixels.

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

import traceback
import math
import logging
from datetime import timezone

from osgeo import osr

from . import drill
from . import drillstats
from . import image_reader


# For defining the shape of a Point's region of interest.
ROI_SHP_SQUARE = 'square'
"""
Define a square region of interest
"""
ROI_SHP_CIRCLE = 'circle'
"""
Define a circle region of interest
"""


class PointError(Exception):
    pass


class Point:
    """
    A structure for an X-Y-Time point with a coordinate reference system,
    spatial shape, and image-acquisition window.

    The statistics for a Point are retrievable using its ``stats`` attribute,
    which is an instance of :class:`~pixdrill.drillstats.PointStats`.
    
    Parameters
    ----------
    x : float
        The x-coordinate of the survey's centre (e.g. longitude or easting).
    y : float
        The y-coordinate of the survey's centre (e.g. latitude or northing).
    t : datetime.datetime
        The point's survey date and time. If `t` is time zone unaware, then
        UTC is assumed.
    sp_ref : int or osr.SpatialReference
        The coordinate reference system of the point's `x`, `y` location.
        Integer's are interpreted as `EPSG codes <https://epsg.org/>`__
        and used to create a GDAL osr.SpatialReference object.
    t_delta : :class:`python:datetime.timedelta` object
        For searching STAC catalogues. An Item acquired within this time
        window either side of the point's time will be drilled, provided
        it is one of the ``nearest_n`` Items
        (see :func:`pixdrill.drill.drill`).
    buffer : int or float
        Together with the ``shape`` parameter, buffer defines the region of
        interest about the point.
    shape : {ROI_SHP_SQUARE, ROI_SHP_CIRCLE}
        The shape of the region of interest. If shape is
        :attr:`~pixdrill.drillpoints.ROI_SHP_SQUARE`, then buffer is half the
        length of the square's side.
        If shape is :attr:`~pixdrill.drillpoints.ROI_SHP_CIRCLE`, then buffer
        is the circle's radius.        
    buffer_degrees : bool
        If True, then the units for the point's buffer are
        assumed to be in degrees, otherwise they are assumed to be in metres.
        The default is False (metres).
    
    Attributes
    ----------
    x : float
        The survey point's x-coordinate.
    y : float
        The survey point's y-coordinate.
    t : datetime.datetime
        The survey point's date and time.
    x_y : tuple of float
        The point's (x, y) location.
    sp_ref : osr.SpatialReference
        The osr.SpatialReference of (x, y).
    wgs84_x : float
        The point's x location in WGS84 coordinates.
    wgs84_y : float
        The point's y location in WGS84 coordinates.
    start_date : datetime.datetime
        The start date of the image-acquistion window.
    end_date : datetime.datetime
        The end date of the image-acquisition window.
    buffer : float
        The distance from the point that defines the region of interest.
    shape : int
        :attr:`~pixdrill.drillpoints.ROI_SHP_SQUARE` or
        :attr:`~pixdrill.drillpoints.ROI_SHP_CIRCLE`.
    buffer_degrees : bool
        True if the buffer distance is in degrees or False if it is in metres.
    stats : drillstats.PointStats
        Holds the drilled data and statistics.
    items : dictionary
        The items associated with this point, keyed by the Item ID.

    """
    def __init__(self, x, y, t, sp_ref, t_delta, buffer, shape,
            buffer_degrees=False):
        """Point constructor."""
        self.x = x
        self.y = y
        self.t = t
        if self.t.tzinfo is None:
            self.t = self.t.replace(tzinfo=timezone.utc)
        self.x_y = (self.x, self.y)
        if not isinstance(sp_ref, osr.SpatialReference):
            sp_ref_osr = osr.SpatialReference()
            sp_ref_osr.ImportFromEPSG(sp_ref)
            self.sp_ref = sp_ref_osr
        else:
            self.sp_ref = sp_ref
        self.wgs84_x, self.wgs84_y = self.to_wgs84()
        self.wgs84_x = -180 if math.isclose(self.wgs84_x, 180) else \
            self.wgs84_x
        self.start_date = self.t - t_delta
        self.end_date = self.t + t_delta
        self.buffer = buffer
        self.shape = shape
        self.buffer_degrees = buffer_degrees
        self.items = {}
        self.stats = drillstats.PointStats(self)

    def intersects(self, ds):
        """
        Return True if the point intersects the GDAL dataset.
        The comparison is made using the image's coordinate reference system.

        Parameters
        ----------
        ds : An ``osgeo.gdal.Dataset`` object or ``str``
            The file to check intersection with, it can be an open
            GDAL Dataset or a filepath.

        Returns
        -------
        bool

        """
        iinfo = image_reader.ImageInfo(ds)
        img_srs = osr.SpatialReference()
        img_srs.ImportFromWkt(iinfo.projection)
        pt_x, pt_y = self.transform(img_srs)
        in_bounds = (pt_x >= iinfo.x_min and pt_x <= iinfo.x_max and
                     pt_y >= iinfo.y_min and pt_y <= iinfo.y_max)
        return in_bounds

    def transform(self, dst_srs, src_srs=None, x=None, y=None):
        """
        Transform the point's x, y location to the destination
        osr.SpatialReference coordinate reference system.

        Parameters
        ----------

        dst_srs : osr.SpatialReference
            The destination SRS
        src_srs : osr.SpatialReference, optional
            The source SRS
        x : float, optional
            The x coord to be transformed.
        y : float, optional
            The y coord to be transformed.

        Returns
        -------
        tuple with the transformed (x, y) coords

        Notes
        -----

        You may supply an alternative `src_srs` for the (x, y) Point. If not
        supplied this Point's sp_ref is used.

        You may supply alternative `x`, `y` coordinates. If not supplied the 
        Point's `x`, `y` coordinates are used.

        Under the hood, use GDAL's OAMS_TRADITIONAL_GIS_ORDER axis mapping
        strategies to guarantee x, y point ordering of the input and
        output points.

        """
        x = self.x if x is None else x
        y = self.y if y is None else y
        src_srs = self.sp_ref if src_srs is None else src_srs
        src_map_strat = src_srs.GetAxisMappingStrategy()
        dst_map_strat = dst_srs.GetAxisMappingStrategy()
        src_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        dst_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        # TODO: handle problems that may arise. See:
        # https://gdal.org/tutorials/osr_api_tut.html#coordinate-transformation
        ct = osr.CoordinateTransformation(src_srs, dst_srs)
        tr = ct.TransformPoint(x, y)
        src_srs.SetAxisMappingStrategy(src_map_strat)
        dst_srs.SetAxisMappingStrategy(dst_map_strat)
        return (tr[0], tr[1])

    def to_wgs84(self):
        """
        Return the x, y coordinates of this Point in the WGS84 coordinate
        reference system, EPSG:4326.

        Returns
        -------
        tuple of the new coords

        """
        dst_srs = osr.SpatialReference()
        dst_srs.ImportFromEPSG(4326)
        return self.transform(dst_srs)

    def change_buffer_units(self, dst_srs):
        """
        Given the destination (target) spatial reference system, change
        the buffer's units and estimate a new distance in the dst_srs.
        
        Parameters
        ----------

        dst_srs : osr.SpatialReference
            The target SRS.

        Returns
        -------
        float
            The buffer distance.

        Notes
        -----

        Handles two cases:

        1. convert the point's buffer distance to metres if it is in degrees
           and the dst_srs is a projected reference system.
        2. convert the point's buffer distance to degrees if it is in metres
           and the dst_srs is a geographic reference system.

        If the buffer's units and `dst_srs` are compatible; then do nothing,
        returning self.buffer as is.

        """
        if not self.buffer_degrees and dst_srs.IsGeographic():
            # Convert buffer units from metres to degrees
            if self.sp_ref.IsProjected():
                buffer = self._transformed_buffer(
                    self.x, self.y, self.buffer, self.sp_ref, dst_srs)
            elif self.sp_ref.IsGeographic():
                # Which CRS is the buffer distance defined in? We don't know.
                # So convert x, y to the following projected CRS:
                # - EPSG 32601 - 32660 for the northern hemisphere, and
                # - EPSG 32701 = 32770 for the southern hemisphere
                if self.wgs84_y >= 0:
                    epsg = 32600 + int(self.wgs84_x / 6.0) + 31
                else:
                    epsg = 32700 + int(self.wgs84_x / 6.0) + 31
                p_sp_ref = osr.SpatialReference()
                p_sp_ref.ImportFromEPSG(epsg)
                px, py = self.transform(p_sp_ref)
                buffer = self._transformed_buffer(
                    px, py, self.buffer, p_sp_ref, dst_srs)
            else:
                # Dunno! Is self.sp_ref.IsLocal() ??
                raise PointError(
                    "ERROR: unknown Spatial Reference type for sp_ref.")
        elif self.buffer_degrees and dst_srs.IsProjected():
            # Convert buffer units from degrees to metres
            if self.sp_ref.IsProjected():
                # Which CRS is the buffer distance defined in? We don't know.
                # So, assume EPSG 4326.
                g_sp_ref = osr.SpatialReference()
                g_sp_ref.ImportFromEPSG(4326)
                buffer = self._transformed_buffer(
                    self.wgs84_x, self.wgs84_y, self.buffer, g_sp_ref, dst_srs)
            elif self.sp_ref.IsGeographic():
                buffer = self._transformed_buffer(
                    self.x, self.y, self.buffer, self.sp_ref, dst_srs)
            else:
                # Dunno! Is self.sp_ref.IsLocal() ??
                raise PointError(
                    "ERROR: unknown Spatial Reference type for sp_ref.")
        elif not (dst_srs.IsProjected() or dst_srs.IsGeographic()):
            # Dunno! What is dst_srs ??
            raise PointError(
                "ERROR: unknown Spatial Reference type for dst_srs.")
        else:
            # The buffer units and destination spatial reference system
            # are compatible.
            buffer = self.buffer
        return buffer

    def _transformed_buffer(self, x, y, buffer, src_srs, dst_srs):
        """
        Add the `buffer` distance to `x` to create a new point and calculate
        the distance between the two points in the `dst_srs`, which is
        the transformed buffer distance.

        Parameters
        ----------
        x : float
        y : float
        buffer : float
        src_srs : osr.SpatialReference
        dst_srs : osr.SpatialReference

        Returns
        -------
        float
            The transformed buffer distance.

        """
        xn = buffer + x
        t_x, t_y = self.transform(dst_srs, src_srs=src_srs, x=x, y=y)
        t_xn, t_y = self.transform(dst_srs, src_srs=src_srs, x=xn, y=y)
        new_buff = t_xn - t_x
        return new_buff


class ItemDrillerError(Exception):
    pass


class ItemDriller:
    """
    Drills an Item, extracting pixels for a list of Points.

    Parameters
    ----------

    item : a pystac.Item object or a drill.ImageItem object
        The Item to be drilled.
    asset_ids : a list of strings
        The IDs of the pystac.Item's raster assets to read; leave
        this as None (the default) if item is an instance of
        :class:`~pixdrill.drill.ImageItem` or you want to set the assets
        later using :func:`~pixdrill.drillpoints.ItemDriller.set_asset_ids`.


    Attributes
    ----------
    item : :class:`pystac:pystac.Item` or :class:`~pixdrill.drill.ImageItem`
        The Item to be drilled.
    points : list of :class:`~pixdrill.drillpoints.Point` objects
    asset_ids : list of strings
        the IDs of the :class:`pystac:pystac.Item`'s raster assets to read.

    """
    def __init__(self, item, asset_ids=None):
        """Constructor"""
        if isinstance(item, drill.ImageItem) and asset_ids is not None:
            errmsg = "ERROR: do not set asset_ids when item is an ImageItem."
            raise ItemDrillerError(errmsg)
        self.item = item
        self.asset_ids = asset_ids
        self.points = []

    def set_asset_ids(self, asset_ids):
        """
        Set which asset IDs to read data from on the next call to
        :func:`~pixdrill.drillpoints.ItemDriller.read_data`.

        Parameters
        ----------
        asset_ids : list of ids

        Notes
        -----
        This function is irrelevant when ``self.item`` is an instance
        of :class:`~pixdrill.drill.ImageItem`.
        If ``self.item`` is a :class:`pystac:pystac.Item`, then you must set
        the asset_ids using this function or the constructor.

        Using this function probably only makes sense in the context of
        setting the asset IDs for the first time or
        reusing the :class:`pystac:pystac.Item` to calculate statistics for an
        entirely new set of raster assets. In the latter case,
        you would call this function after calling
        :func:`~pixdrill.drillpoints.ItemDriller.reset_stats` and before
        calling :func:`~pixdrill.drillpoints.ItemDriller.read_data` and
        :func:`~pixdrill.drillpoints.ItemDriller.calc_stats`.

        You may experience strange side effects if you don't call
        :func:`~pixdrill.drillpoints.ItemDriller.reset_stats`
        when the ItemDriller previously had assets assigned.
        The underlying behaviour is that arrays for the new set of asset_ids
        will be appended to the existing arrays for each point's
        :class:`~pixdrill.drillpoints.PointStats` object. Then, on the next
        :func:`~pixdrill.drillpoints.ItemDriller.calc_stats()` call, the stats
        for all previously read data will be recalculated in addition to
        the new stats for the new assets.

        """
        if isinstance(self.item, drill.ImageItem):
            errmsg = "ERROR: do not set asset_ids when item is an ImageItem."
            raise ItemDrillerError(errmsg)
        elif not asset_ids:
            errmsg = "ERROR: must set asset_ids."
            raise ItemDrillerError(errmsg)
        else:
            self.asset_ids = asset_ids

    def add_point(self, pt):
        """
        Append the Point to this object's points list.

        Parameters
        ----------
        pt : :class:`~pixdrill.drillpoints.Point` object

        """
        self.points.append(pt)

    def read_data(self, ignore_val=None):
        """
        Read the pixels around every point for the given raster assets.
        On completion, each Point's stats object will have a
        :ref:`masked array <numpy:maskedarray>` for the ``Item``.

        Parameters
        ----------
        ignore_val : number or ``None``, optional
            Use the given number to define the pixels to be masked when
            creating the numpy masked arrays. See the notes below.

        Returns
        -------
        bool
            True if data is read or False if there's an error reading the data.

        Notes
        -----

        When reading from the assets of a :class:`pystac:pystac.Item`,
        ``ignore_val`` can be a list of values, a single values, or ``None``.
        A list of values is the null value per asset. It assumes all
        bands in an asset use the same null value.
        A single value is used for all bands of all assets.
        None means to use the no data value set on each the assets' bands.
        
        When reading the image of a :class:`~pixdrill.drill.ImageItem`,
        ``ignore_val`` can be a single value or ``None``.
        A single value is used for all bands in the image.
        None means to use the each band's no data value.

        The reading is delegated to
        :func:`pixdrill.image_reader.ImageReader.read_data`.

        """
        read_ok = True
        if isinstance(self.item, drill.ImageItem):
            # Read bands from an image
            reader = image_reader.ImageReader(self.item)
            if ignore_val is not None:
                if isinstance(ignore_val, list):
                    errmsg = "Passing a list of ignore_vals when reading " \
                             "from an image is unsupported"
                    raise ItemDrillerError(errmsg)
            try:
                reader.read_data(self.points, ignore_val=ignore_val)
            except RuntimeError:
                err_msg = f"Failed to read data from {self.item.filepath}. "
                err_msg += "The stack trace is:\n"
                err_msg += traceback.format_exc()
                logging.error(err_msg)
                self.reset_stats()
                read_ok = False
        else:
            # Read assets from a Stac Item.
            if self.asset_ids is None:
                errmsg = ("ERROR: Cannot read data from pystac.Item objects " +
                          "without first setting the asset IDs. Asset IDs " +
                          "are set in the ItemDriller constructor or by " +
                          "calling ItemDriller.set_asset_ids()")
                raise ItemDrillerError(errmsg)
            if isinstance(ignore_val, list):
                if len(ignore_val) != len(self.asset_ids):
                    errmsg = "The ignore_val list must be the same length " \
                             "as asset_ids."
                    raise ItemDrillerError(errmsg)
            else:
                ignore_val = [ignore_val] * len(self.asset_ids)
            # GDAL will raise a RuntimeError if it can't open files,
            # in which case we write to the error log and roll back
            # all data read for the item because we can't guarantee a
            # clean read.
            try:
                for asset_id, i_v in zip(self.asset_ids, ignore_val):
                    reader = image_reader.ImageReader(
                        self.item, asset_id=asset_id)
                    reader.read_data(self.points, ignore_val=i_v)
            except RuntimeError:
                fp = image_reader.get_asset_filepath(self.item, asset_id)
                err_msg = f"Failed to read data for item {self.item.id} from "
                err_msg += f"{fp}. The stack trace is:\n"
                err_msg += traceback.format_exc()
                logging.error(err_msg)
                self.reset_stats()
                read_ok = False
        return read_ok
    
    def get_points(self):
        """
        Get the list of :class:`~pixdrill.drillpoints.Point` objects in
        this collection.

        Returns
        -------
        list of :class:`~pixdrill.drillpoints.Point` objects

        """
        return self.points

    def calc_stats(self, std_stats=None, user_stats=None):
        """
        Calculate the statistics for every Point. Call this after
        calling :func:`~pixdrill.drillpoints.ItemDriller.read_data`.

        On completion, each Point's stats object will be populated with
        the statistics.

        Parameters
        ----------
        std_stats : list of int, optional
            The list of standard statistics to calculate. Each element must be
            one of the ``STATS_*`` constants defined in
            :mod:`pixdrill.drillstats`.
        user_stats : list of (name, func) tuples
            ``name`` is a string and is the name of the statistic.
            ``func`` is the name of the function used to calculate
            the statistic.

        See also
        --------
        :func:`pixdrill.drill.drill` : for the signature of a user-supplied
            statistics function and how to retrieve the statistics from a
            :class:`~pixdrill.drillpoints.Point`.

        """
        for pt in self.points:
            pt.stats.calc_stats(
                self.item.id, std_stats=std_stats, user_stats=user_stats)

    def get_item(self):
        """
        Return this object's ``Item``.

        Returns
        -------
        :class:`pystac:pystac.Item` or :class:`~pixdrill.drill.ImageItem`

        """
        return self.item

    def reset_stats(self):
        """
        Reset the stats for this item for all points.
        
        """
        for pt in self.points:
            pt.stats.reset(item=self.item)
