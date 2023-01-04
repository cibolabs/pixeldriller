"""
Contains the Point and ItemPoints classes which are used to create and hold
the points for an Item.

"""

import traceback
import math
import logging

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

class PointError(Exception): pass

class Point:
    """
    A structure for an X-Y-Time point with a corresponding 
    osr.SpatialReference system. A point is characterised by:
    
    - a location in space and time
    - a spatial buffer
    - a temporal window
    
    Attributes
    ----------
    x : float
        The point's x-coordinate.
    y : float
        The point's y-coordinate.
    t : datetime.datetime
        The point's datetime.datetime time.
    x_y : tuple of float
        The point's (x, y) location.
    sp_ref : osr.SpatialReference
        The osr.SpatialReference of (x, y).
    wgs84_x : float
        The point's x location in WGS84 coordinates.
    wgs84_y : float
        The point's y location in WGS84 coordinates.
    start_date : datetime.datetime
        The datetime.datetime start date of the temporal buffer.
    end_date : datetime.datetime
        The datetime.datetime end date of the temporal buffer.
    buffer : float
        The distance from the point that defines the region of interest.
    shape : int
        ROI_SHP_SQUARE or ROI_SHP_CIRCLE
    buffer_degrees : bool
        True if the buffer distance is in degrees or False if it is in metres.
    stats : drillstats.PointStats
        Holds the drilled data and statistics.
    items : dictionary
        The items associated with this point, keyed by the Item ID.
        See get_item_ids().

    """
    def __init__(
        self, point, sp_ref, t_delta, buffer, shape, buffer_degrees=False):
        """
        Point constructor.

        point is a (X, Y, Time) tuple. X and Y are the spatial coordinates and
        Time is a datetime.datetime object.

        Time may be may be timezone aware or unaware.
        They are handled as per the pystac_client.Client.search interface.
        See: https://pystac-client.readthedocs.io/en/stable/api.html
        
        sp_ref is the osr.SpatialReference object
        defining the coordinate reference system of the point.

        t_delta is a datetime.timedelta object, which defines the
        temporal window either side of the given Time.

        buffer defines the region of interest about the point.
        If buffer_degrees is True, then the units for the point's buffer are
        assumed to be in degrees, otherwise they are assumed to be in metres.
        The default is metres.

        shape defines the shape of the region of interest. If shape is
        ROI_SHP_SQUARE, then buffer is half the length of the square's side.
        If shape is ROI_SHP_CIRCLE, then buffer is the circle's radius.

        """
        self.x = point[0]
        self.y = point[1]
        self.t = point[2]
        self.x_y = (self.x, self.y)
        self.sp_ref = sp_ref
        self.wgs84_x, self.wgs84_y = self.to_wgs84()
        self.wgs84_x = -180 if math.isclose(self.wgs84_x, 180) else self.wgs84_x
        self.start_date = self.t - t_delta
        self.end_date = self.t + t_delta
        self.buffer = buffer
        self.shape = shape
        self.buffer_degrees = buffer_degrees
        self.items = {}
        self.stats = drillstats.PointStats(self)


    def add_items(self, items):
        """
        A point might intersect multiple STAC items. Use this function
        to link the point with the items it intersects.

        See also get_item_ids().

        Parameters
        ----------
        items : a sequence of pystac.Item or drill.ImageItem objects

        """
        for item in items:
            if item.id not in self.items:
                self.items[item.id] = item

    
    def intersects(self, ds):
        """
        Return True if the point intersects the GDAL dataset. ds can be a
        open gdal.Dataset or a filepath as a string.

        The comparison is made using the image's coordinate reference system.

        Parameters
        ----------
        ds : GDAL dataset object or filepath as a string
            The file to check intersection with

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

 
    def get_item_ids(self):
        """
        Return a list of the IDs of the pystac.Item items associated with this point.

        Returns
        -------
        list of ids

        """
        return list(self.items.keys())


    def transform(self, dst_srs, src_srs=None, x=None, y=None):
        """
        Transform the point's x, y location to the destination
        osr.SpatialReference coordinate reference system.

        Return the transformed (x, y) point.

        You may supply an alternative src_srs for the (x, y) Point. If not
        supplied the points sp_ref is used.

        You may supply alternative x, y coordinates. If not supplied the 
        point's x, y coordinates are used.

        Under the hood, use the OAMS_TRADITIONAL_GIS_ORDER axis mapping strategies
        to guarantee x, y point ordering of the input and output points.

        Parameters
        ----------

        dst_srs : osr.SpatialReference
            The optional destination SRS
        src_srs : osr.SpatialReference
            The optional source SRS
        x : float
            The optional x coord
        y : float
            The optional y coord

        Returns
        -------
        tuple with the new coords

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
        the point's buffer units and estimate a new distance in the dst_srs.
        
        Handles two cases:

        1. convert the point's buffer distance to metres if it is in degrees
           and the dst_srs is a projected reference system.
        2. convert the point's buffer distance to degrees if it is in metres
           and the dst_srs is a geographic reference system.

        Return the buffer distance in the new units.

        Do nothing, returning self.buffer, if the buffer distance and dst_srs
        are compatible; that is:
        
        1. the buffer distance is metres and dst_srs is a
           projected reference system
        2. the buffer distance is in degrees and dst_srs is a
           geographic reference system

        Parameters
        ----------

        dst_srs : osr.SpatialReference
            The new SRS

        Returns
        -------
        float


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
                    epsg = 32600 + int(self.wgs84_x/6.0) + 31
                else:
                    epsg = 32700 + int(self.wgs84_x/6.0) + 31
                p_sp_ref = osr.SpatialReference()
                p_sp_ref.ImportFromEPSG(epsg)
                px, py = self.transform(p_sp_ref)
                buffer = self._transformed_buffer(
                    px, py, self.buffer, p_sp_ref, dst_srs)
            else:
                # Dunno! Is self.sp_ref.IsLocal() ??
                raise PointError("ERROR: unknown Spatial Reference type for sp_ref.")
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
                raise PointError("ERROR: unknown Spatial Reference type for sp_ref.")
        elif not (dst_srs.IsProjected() or dst_srs.IsGeographic()):
            # Dunno! What is dst_srs ??
            raise PointError("ERROR: unknown Spatial Reference type for dst_srs.")
        else:
            # The buffer units and destination spatial reference system are compatible.
            buffer = self.buffer
        return buffer


    def _transformed_buffer(self, x, y, buffer, src_srs, dst_srs):
        """
        Add buffer to x to create a new point.
        Project both points to dst_srs and calculate a new buffer distance
        in the dst_srs.

        Assumptions:
            - x, y is in src_srs
            - buffer's units are the same as the src_srs

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


        """
        xn = buffer + x
        t_x, t_y = self.transform(dst_srs, src_srs=src_srs, x=x, y=y)
        t_xn, t_y = self.transform(dst_srs, src_srs=src_srs, x=xn, y=y)
        new_buff = t_xn - t_x
        return new_buff


class ItemPointsError(Exception): pass

class ItemPoints:
    """
    A collection of points that Intersect a pystac.Item or a drill.ImageItem.

    The read_data() function is used to read the pixels from the associated
    rasters.

    Attributes
    ----------
    item : pystac.Item object or a drill.ImageItem
        These points intersect this item
    asset_ids : sequence of strings
        the IDs of the pystac.Item's raster assets to read
    points : list of Point objects

    """
    def __init__(self, item, asset_ids=None):
        """
        Construct an ItemPoints object, setting the following attributes:
        - item: the pystac.Item object or a drill.ImageItem
        - asset_ids: the IDs of the pystac.Item's raster assets to read; leave
          this as None if item is an instance of drill.ImageItem or you want
          to set the assets later using set_asset_ids().
        - points: to an empty list

        """
        if isinstance(item, drill.ImageItem) and asset_ids is not None:
            errmsg = "ERROR: do not set asset_ids when item is an ImageItem."
            raise ItemPointsError(errmsg)
        self.item = item
        self.asset_ids = asset_ids
        self.points = []

    
    def set_asset_ids(self, asset_ids):
        """
        Set which asset IDs to read data from on the next call to read_data().
        This function is not relevant when self.item is a drill.ImageItem.
        But if self.item is a pystac.Item, then you must set the asset_ids
        using this function or in the constructor.

        Using this function probably only makes sense in the contexts of
        setting the asset IDs for the first time or
        reusing the pystac.Item objects to calculate statistics for an
        entirely new set of raster assets. In the latter case,
        you would call this function after calling reset_stats() and before
        calling read_data() and calc_stats().

        You may experience strange side effects if you don't call reset_stats()
        on an ItemPoints object that previously had assets assigned.
        The underlying behaviour is that arrays for the new set of asset_ids
        will be appended to the existing arrays for each point's PointStats objects.
        Then, on the next calc_stats() call, the stats for all previously read
        data will be recalculated in addition to the new stats for the new assets.

        Parameters
        ----------

        asset_ids : list of ids

        """
        if isinstance(self.item, drill.ImageItem):
            errmsg = "ERROR: do not set asset_ids when item is an ImageItem."
            raise ItemPointsError(errmsg)
        elif not asset_ids:
            errmsg = "ERROR: must set asset_ids."
            raise ItemPointsError(errmsg)
        else:
            self.asset_ids = asset_ids


    def add_point(self, pt):
        """
        Append the Point to this object's points list.

        Parameters
        ----------
        pt : Point object

        """
        self.points.append(pt)

 
    def read_data(self, ignore_val=None):
        """
        Read the pixels around every point for the given raster assets.

        ignore_val specifies the no data values of the rasters being read.
        
        When reading from the assets of a STAC Item, ignore_val can be
        a single value, a list of values, or None.
        A list of values is the null value per asset. It assumes all
        bands in an asset use the same null value.
        A single value is used for all bands of all assets.
        None means to use the no data value set on each asset.
        
        When reading from a plain image, ignore_val can be a single value
        or None.
        A single value is used for all bands in the image.
        None means to use the image band's no data value.

        The reading is done by image_reader.ImageReader.read_data().

        Parameters
        ----------
        ignore_val : number or None
            Use the given number as the ignore value or all bands. If none,
            use the image's nodata value.

        Returns
        -------
        True if data is read or False if there's an error reading the data.

        """
        read_ok = True
        if isinstance(self.item, drill.ImageItem):
            # Read bands from an image
            reader = image_reader.ImageReader(self.item)
            if ignore_val is not None:
                if isinstance(ignore_val, list):
                    errmsg = "Passing a list of ignore_vals when reading from " \
                             "an image is unsupported"
                    raise ItemPointsError(errmsg)
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
                          "are set in the ItemPoints constructor or by " +
                          "calling ItemPoints.set_asset_ids()")
                raise ItemPointsError(errmsg)
            if isinstance(ignore_val, list):
                errmsg = "The ignore_val list must be the same length as asset_ids."
                assert len(ignore_val) == len(self.asset_ids), errmsg
            else:
                ignore_val = [ignore_val] * len(self.asset_ids)
            # GDAL will raise a RuntimeError if it can't open files,
            # in which case we write to the error log and roll back
            # all data read for the item because we can't guarantee a clean read.
            try:
                for asset_id, i_v in zip(self.asset_ids, ignore_val):
                    reader = image_reader.ImageReader(self.item, asset_id=asset_id)
                    reader.read_data(self.points, ignore_val=i_v)
            except RuntimeError:
                fp = image_reader.get_asset_filepath(self.item, asset_id)
                err_msg = f"Failed to read data for item {self.item.id} from {fp}. "
                err_msg += "The stack trace is:\n"
                err_msg += traceback.format_exc()
                logging.error(err_msg)
                self.reset_stats()
                read_ok = False
        return read_ok

    
    def get_points(self):
        """
        Get the list of pointstats.Point objects in this collection.

        Returns
        -------
        list of Point objects

        """
        return self.points

    
    def calc_stats(self, std_stats=None, user_stats=None):
        """
        Calculate the statistics for every Point.

        Call this after calling read_data().

        std_stats is a list of standard stats to calculate for each point's
        region of interest.
        They are a list of STATS symbols defined in this module.

        user_stats is a list of tuples. Each tuple defines:
        
        - the name (a string) for the statistic
        - and the function that is called to calculate it

        Parameters
        ----------
        std_stats : int
            One of the STATS* constants
        user_stats : list of (name, func) tuples
            where func is the user functional to calculate a statistic

        """
        for pt in self.points:
            pt.stats.calc_stats(
                self.item.id, std_stats=std_stats, user_stats=user_stats)


    def get_item(self):
        """
        Return the pystac.Item or drill.ImageItem.

        Returns
        -------
        pystac.Item or drill.ImageItem

        """
        return self.item


    def reset_stats(self):
        """
        Reset the stats for this item for all points.
        
        """
        for pt in self.points:
            pt.stats.reset(item=self.item)
