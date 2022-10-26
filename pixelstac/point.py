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

    These attributes are set on calling make_roi
    - roi: the point's spatial buffer (region of interest)

    """
    def __init__(self, point, sp_ref, t_delta):
        """
        Point constructor.

        Takes a (X, Y, Time) point and the osr.SpatialReference object
        defining the coordinate reference system of the point.

        Time is a datetime.datetime object.

        Also takes the datetime.timedelta object, which defines the 
        temporal buffer either side of the given Time.

        """
        self.x = point[0]
        self.y = point[1]
        self.t = point[2]
        self.x_y = (self.x, self.y)
        self.sp_ref = sp_ref
        self.wgs84_x, self.wgs84_y = self.to_wgs84()
        self.start_date = self.t - t_delta
        self.end_date = self.t + t_delta
        # Set by make_roi():
        self.roi_shape = None
        self.roi_bbox = None


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
        return Point.transform_point(self.x, self.y, self.sp_ref, dst_srs)

    
    def make_roi(self, buffer, shape, item, ref_asset):
        """
        Construct the region of interest (ROI) in the same coordinate
        reference system as the reference asset of the given pystac.item.Item.
        
        The ROI is defined by its bounding box (coordinates of
        its upper left and lower right corners) and its shape. It assumes
        that the asset's coordinate reference system defines north as up.
    
        buffer is the distance either side of the point that defines the ROI.
        It is used in combination with shape (one of the ROI_SHP_ values) to
        fully specify the ROI.

        Two attributes on this Point instance:
        - roi_shape: using the given shape
        - roi_bbox: as the coordinates of the upper left and lower right 
          corners of the bounding box in the coordinate reference
          system of the reference asset (ul_x, ul_y, lr_x, lr_y).
    
        """
        self.roi_shape = shape
        # self.x_y is the centre of the point and has a coordinate
        # reference system of self.sp_ref.
        # Example, although I think this creates a circle not a square
        # which do we want?
        #pt = ogr.CreateGeometryFromWkt(wkt)
        #poly = pt.Buffer(bufferDistance)
        #xmin, xmax, ymin, ymax = poly.GetEnvelope()
        # Find the centre of the bounding box in the asset's coordinate
        # reference system.
        asset_info = asset_reader.asset_info(item, ref_asset)
        a_sp_ref = osr.SpatialReference()
        a_sp_ref.ImportFromWkt(asset_info.projection)
        c_x, c_y = Point.transform_point(self.x, self.y, self.sp_ref, a_sp_ref)
        # Bounds. Assume north is up.
        ul_x = c_x - buffer
        ul_y = c_y + buffer
        lr_x = c_x + buffer
        lr_y = c_y - buffer
        self.roi_bbox = (ul_x, ul_y, lr_x, lr_y)


    @staticmethod
    def transform_point(x, y, src_srs, dst_srs):
        """
        Transform the (x, y) point from the source
        osr.SpatialReference to the destination osr.SpatialReference.

        Return the transformed (x, y) point.

        Under the hood, use the OAMS_TRADITIONAL_GIS_ORDER axis mapping strategies
        to guarantee x, y point ordering of the input and output points.

        """
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
