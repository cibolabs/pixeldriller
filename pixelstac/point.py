"""
Defines the Point class and additional functions for operating on points.

"""

from osgeo import osr

from . import asset_reader

# For defining the shape of a Point's region of interest.
ROI_SHP_SQUARE = 'square'
#ROI_SHP_CIRCLE = 'circle'

class Point:
    """
    A structure for an X-Y-Time point with a corresponding 
    osr.SpatialReference system. A point is characterised by:
    - a location in space and time
    - a spatial buffer
    - a temporal buffer
    
    These attributes are set at construction time:
    - x: the point's x-coordinate
    - y: the point's y-coordinate
    - t: the point's datetime.datetime time
    - x_y: the point's (x, y) location
    - sp_ref: the osr.SpatialReference of (x, y)
    - wgs84_x: the point's x location in WGS84 coordinates
    - wgs84_y: the point's y location in WGS84 coordinates
    - start_date: the datetime.datetime start date of the temporal buffer
    - end_date: the datetime.datetime end date of the temporal buffer
    - buffer: the distance from the point that defines the region of interest
    - shape: the shape of the region of interest
    - other_attributes: other attributes, of any type, as required by the caller

    """
    def __init__(
        self, point, sp_ref, t_delta, buffer, shape, other_attributes=None):
        """
        Point constructor.

        Takes a (X, Y, Time) point and the osr.SpatialReference object
        defining the coordinate reference system of the point.

        Time is a datetime.datetime object.

        Also takes the datetime.timedelta object, which defines the 
        temporal buffer either side of the given Time.

        The region of interest about the point is defined by the buffer
        and the shape. buffer is assumed to be in the same coordinate
        reference system as the raster assets being queried. shape is one of
        the ROI_SHP_ symbols defined in this module.

        other_attributes are any other attributes that the caller wants to
        attach to this point for later convenience. They have no effect when
        querying the pixelstac. However, the Point and its other_attributes
        are accessible from each PointStats object returned from
        pixelstac.query(). other_attributes can be any data type.

        """
        self.x = point[0]
        self.y = point[1]
        self.t = point[2]
        self.x_y = (self.x, self.y)
        self.sp_ref = sp_ref
        self.wgs84_x, self.wgs84_y = self.to_wgs84()
        self.start_date = self.t - t_delta
        self.end_date = self.t + t_delta
        self.buffer = buffer
        self.shape = shape
        self.other_attributes = other_attributes


    def transform(self, dst_srs):
        """
        Transform the point's x, y location to the destination
        osr.SpatialReference coordinate reference system.

        Return the transformed (x, y) point.

        Under the hood, use the OAMS_TRADITIONAL_GIS_ORDER axis mapping strategies
        to guarantee x, y point ordering of the input and output points.

        """
        src_map_strat = self.sp_ref.GetAxisMappingStrategy()
        dst_map_strat = dst_srs.GetAxisMappingStrategy()
        self.sp_ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        dst_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        # TODO: handle problems that may arise. See:
        # https://gdal.org/tutorials/osr_api_tut.html#coordinate-transformation
        ct = osr.CoordinateTransformation(self.sp_ref, dst_srs)
        tr = ct.TransformPoint(self.x, self.y)
        self.sp_ref.SetAxisMappingStrategy(src_map_strat)
        dst_srs.SetAxisMappingStrategy(dst_map_strat)
        return (tr[0], tr[1])
    

    def to_wgs84(self):
        """
        Return the x, y coordinates of this Point in the WGS84 coordinate
        reference system.
        Convert the given points (list of x, y tuples) from the source
        spatial reference system to WGS84 (EPSG:4326).

        Return a list of x, y (longitude, latitude) tuples.

        Use transform_points to do the transformation.

        """
        dst_srs = osr.SpatialReference()
        dst_srs.ImportFromEPSG(4326)
        return self.transform(dst_srs)
