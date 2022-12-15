"""
For reading pixel data and metadata from raster assets.

"""

import math
import numpy

from osgeo import gdal
from osgeo import osr

from . import pointstats

gdal.UseExceptions()

class ImageInfo:
    """
    An object with metadata for the given image, in GDAL conventions.
    ds is an already-opened gdal.Dataset object, or the path to the image as
    a string.

    Sourced from rios:
    https://github.com/ubarsc/rios/blob/master/rios/fileinfo.py

    The omit_per_band argument on the constructor is provided in order to speed up the
    access of very large VRT stacks. The information which is normally extracted
    from each band will, in that case, trigger a gdal.Open() for each band, which
    can be quite slow. So, if none of that information is actually required, then
    setting omit_per_band=True will omit that information, but will return as quickly
    as for a normal single file.

    Attributes
    ----------
    x_min : float
        Map X coord of left edge of left-most pixel
    x_max : float
        Map X coord of right edge of right-most pixel
    y_min : float
        Map Y coord of bottom edge of bottom pixel
    y_max : float
        Map Y coord of top edge of top-most pixel
    x_res : float
        Map coord size of each pixel, in X direction
    y_res : float
        Map coord size of each pixel, in Y direction
    nrows : int
        Number of rows in image
    ncols : int
        Number of columns in image
    transform : list of floats
        Transformation params to map between pixel and map coords, in GDAL form
    projection : string
        WKT string of projection
    raster_count : int
        Number of rasters in file
    lnames : list of strings
        Names of the layers as a list.
    layer_type : string
        "thematic" or "athematic", if it is set
    data_type : int
        Data type for the first band (as a GDAL integer constant)
    data_type_name : string
        Data type for the first band (as a human-readable string)
    nodataval : list of floats
        Value used as the no-data indicator (per band)

    """
    def __init__(self, ds, omit_per_band=False):
        """
        Parameters
        ----------
        ds : gdal.Dataset or string
            If string, file will be opened
        omit_per_band : bool
            If True, won't calculate per band information
        """
        opened=False
        if not isinstance(ds, gdal.Dataset):
            ds = gdal.Open(ds, gdal.GA_ReadOnly)
            opened=True
        geotrans = ds.GetGeoTransform()
        (ncols, nrows) = (ds.RasterXSize, ds.RasterYSize)
        self.raster_count = ds.RasterCount
        self.x_min = geotrans[0]
        self.x_res = geotrans[1]
        self.y_max = geotrans[3]
        self.y_res = abs(geotrans[5])
        self.x_max = self.x_min + ncols * self.x_res
        self.y_min = self.y_max - nrows * self.y_res
        self.ncols = ncols
        self.nrows = nrows
        # Projection, etc. 
        self.transform = geotrans
        self.projection = ds.GetProjection()
        # Per-band stuff, including layer names and no data values, and stats
        self.lnames = []
        self.nodataval = []
        if not omit_per_band:
            for band in range(ds.RasterCount):
                band_obj = ds.GetRasterBand(band + 1)
                self.lnames.append(band_obj.GetDescription())
                self.nodataval.append(band_obj.GetNoDataValue())
        gdal_meta = ds.GetRasterBand(1).GetMetadata()
        if 'LAYER_TYPE' in gdal_meta:
            self.layer_type = gdal_meta['LAYER_TYPE']
        else:
            self.layer_type = None
        # Pixel datatype, stored as a GDAL enum value. 
        self.data_type = ds.GetRasterBand(1).DataType
        self.data_type_name = gdal.GetDataTypeName(self.data_type)
        if opened:
            ds = None


    def __str__(self):
        """
        Print a readable version of the object
        """
        lines = []
        for attribute in ['nrows', 'ncols', 'raster_count', 'x_min',
            'x_max', 'y_min', 'y_max', 'x_res', 'y_res', 'lnames',
            'layer_type', 'data_type', 'data_type_name', 
            'nodataval', 'transform', 'projection']:
            value = self.__dict__[attribute]
            lines.append("%-20s%s" % (attribute, value))
        result = '\n'.join(lines)
        return result


class ArrayInfo:
    """
    Contains information about the array read from the image around a point.

    Attributes
    ----------
    
    data : numpy arary
        the numpy masked array containing the pixel data
    asset_id : string
        the id of the Stac Item's asset from which the data was read
    xoff, yoff, win_xsize, win_ysize : int
        The pixel window read from the raster asset in pixel coordinates.
        xoff and yoff are the coordinates of the upper left pixel in
        the array in pixel coordinates
    ulx, uly, lrx, lry : float
        The bounding box of the array in image coordinates.
    x_res, y_res : float
        The pixel size in the same units as the image coordinate reference system

    """
    def __init__(
        self, data, asset_id, xoff, yoff, win_xsize, win_ysize,
        ulx, uly, lrx, lry, x_res, y_res):
        """Create and ArrayInfo object."""
        self.data = data
        self.asset_id = asset_id
        self.xoff = xoff
        self.yoff = yoff
        self.win_xsize = win_xsize
        self.win_ysize = win_ysize
        self.ulx = ulx
        self.uly = uly
        self.lrx = lrx
        self.lry = lry
        self.x_res = x_res
        self.y_res = y_res


    def isempty(self):
        """Return True of the ArrayInfo's data array contains no data."""
        return self.data.size == 0


    def __repr__(self):
        """
        Return a string representation of this object,
        but without the numpy masked array.

        """
        return f"ArrayInfo({self.asset_id=}, " \
            f"{self.xoff=}, " \
            f"{self.yoff=}, " \
            f"{self.win_xsize=}, " \
            f"{self.win_ysize=}, " \
            f"{self.ulx=}, " \
            f"{self.uly=}, " \
            f"{self.lrx=}, " \
            f"{self.lry=}, " \
            f"{self.x_res=}, " \
            f"{self.y_res=})" \


class AssetReaderError(Exception): pass


def get_asset_filepath(item, asset_id):
    """
    Get the filepath to the STAC item's asset.

    """
    return f"/vsicurl/{item.assets[asset_id].href}"


class AssetReader:
    """
    Encapsulates the GDAL Dataset object and metadata (an ImageInfo object) for
    a STAC asset or raster image. It also contains the algorithms
    used to read arrays of pixels around a list of points.

    Attributes
    ----------
    item : pystac.Item or ImageItem object
        Item to read from
    asset_id : string
        Asset ID. If None, then will be assumed that item is a ImageItem
    filepath : string
        The GDAL openable filepath
    dataset : GDAL dataset
        The GDAL dataset for filepath
    info : ImageInfo
        The ImageInfo for the filepath

    """
    def __init__(self, item, asset_id=None):
        """
        Construct an AssetReader object.

        item is a pystac.Item or ImageItem object. If it is a pystac.Item
        object then you must supply the asset_id. If it is a pointstats.ImageItem
        object, then its id must be the path of the file to be read.

        Parameters
        ----------
        item : pystac.Item or ImageItem object
            Item to read from
        asset_id : string
            Asset ID. If None, then will be assumed that item is a ImageItem

        """
        self.item = item
        self.asset_id = asset_id
        if self.asset_id is None:
            # item is an instance of pointstats.ImageItem
            self.filepath = item.filepath
        else:
            #self.filepath = f"/vsicurl/{item.assets[asset_id].href}"
            self.filepath = get_asset_filepath(self.item, self.asset_id)
        self.dataset = gdal.Open(self.filepath, gdal.GA_ReadOnly)
        self.info = ImageInfo(self.dataset)

    
    def read_data(self, points, ignore_val=None):
        """
        Read the data around each of the given points and add it to the point.

        The data is read using read_roi(), passing it the ignore_val.
        The data is attached to each point.

        Once read, the ItemStats object (corresponding to this asset's Item ID)
        of every Point will contain the ArrayInfo object for data read.

        Parameters
        ----------
        points : list of pointstats.Point objects
            Points to read from
        ignore_val : float
            ignore value to use, if None then the image no data is used

        """
        # Do a naive read, reading a small chunk of the image for every point.
        # The testing done to date shows that this is more efficient than
        # reading the entire image and slicing the numpy arrays for each point.
        # But, in those tests there are a small number of points that intersect
        # the images.
        # I suspect that there is a tipping point where it is more
        # efficient to read the entire image (or several large chunks) as the
        # number of points per image increases.
        for pt in points:
            arr_info = self.read_roi(pt, ignore_val=ignore_val)
            pt.add_data(self.item, arr_info)


    def read_roi(self, pt, ignore_val=None):
        """
        Extract the smallest number of pixels required to cover the region of
        interest. We use an 'all-touched' approach, whereby any pixel inside
        or touched by the ROI's boundary is returned. Any pixels outside or
        not touched by the ROI's boundary are masked using ignore_val.
        
        Return an ArrayInfo object.

        The ArrayInfo object contains a 3D numpy masked array (numpy.ma.MaskedArray)
        with the pixel data. If ignore_val=None, the no-data value set on each
        band in the asset/image is used. If ignore_val is set then the same
        value is used for every band in the asset/image.
        
        The returned ArrayInfo object also contains information about the ROI's
        location within the image.

        If the ROI straddles the image extents, the ROI is clipped to the extents
        (i.e. only that portion of the image that is within the extents is returned).

        Parameters
        ----------

        pt : pointstats.Point
            Point to use
        ignore_val : float
            ignore value to use, if None then the image no data is used

        Returns
        -------
        ArrayInfo

        """
        # ROI bounds in pixel coordinates.
        xoff, yoff, win_xsize, win_ysize = self.get_pix_window(pt)
        # ROI bounds in image coordinates:
        ulx, uly = self.pix2wld(xoff, yoff) # Coords of the upper-left pixel's upper-left corner
        lrx, lry = self.pix2wld(xoff+win_xsize, yoff+win_ysize) # Coords of the upper-left pixel's upper-left corner
        # Read the raster.
        if win_xsize > 0 and win_ysize > 0:
            band_data = []
            mask_data = []
            for band_num in range(1, self.info.raster_count + 1):
                band = self.dataset.GetRasterBand(band_num)
                b_arr = band.ReadAsArray(xoff, yoff, win_xsize, win_ysize)
                band_data.append(b_arr)
                nodata_val = ignore_val if ignore_val else self.info.nodataval[band_num-1]
                if nodata_val is None:
                    mask = numpy.zeros(b_arr.shape, dtype=bool)
                else:
                    mask = b_arr==nodata_val
                mask_data.append(mask)
            arr = numpy.array(band_data)
            mask = numpy.array(mask_data)
            m_arr = numpy.ma.masked_array(arr, mask=mask)
        else:
            m_arr = numpy.ma.masked_array([], mask=True)
        arr_info = ArrayInfo(
            m_arr, self.asset_id,
            xoff, yoff, win_xsize, win_ysize,
            ulx, uly, lrx, lry, self.info.x_res, self.info.y_res)
        # Only mask pixels outside the ROI if there are
        # sufficient pixels. The only non-square ROI supported is a circle.
        # This handles the cases where:
        # - the ROI is outside the image extents; size=0
        # - the ROI is a singular point (pt.buffer=0); size=1
        # - the pixel is much larger than the ROI and and the ROI is
        #   contained within one pixel; size=1
        # - the pixel is much larger than the ROI and the ROI crosses pixel
        #   boundaries without intersecting pixel corners; size=4
        # But the case where only 3 of the four pixels are intersected by a
        # circular ROI remains unhandled; all four pixels are returned.
        if arr_info.data.size > 4:
            self.mask_roi_shape(pt, arr_info, ignore_val=ignore_val)
        return arr_info


    def get_pix_window(self, pt):
        """
        Return the rectangular bouds of the region of interest in the image's
        pixel coordinate space as: (xoff, yoff, win_xsize, win_ysize).
        
        If a pixel touches the image's bounds it is included.
    
        xoff, yoff is the grid location of the top-left pixel of the ROI.
        win_xsize and win_ysize are the number of columns and rows to read
        from the image.
    
        An xoff, yoff of 0, 0 corresponds to the top-left pixel of the image.
        An xoff, yoff of (ncols-1, nrows-1) corresponds to the bottom-right
        pixel of the image.
        
        If the ROI is outside the image bounds, the returned window is clipped
        to the image bounds.

        If the returned win_xsize or win_ysize is 0, then the ROI is outside
        of the image's extents.

        Parameters
        ----------

        pt : pointstats.Point
            Point to use

        Returns
        -------
        tuple of floats

        """
        a_sp_ref = osr.SpatialReference()
        a_sp_ref.ImportFromWkt(self.info.projection)
        # Transform the point and buffer into same CRS as the image.
        c_x, c_y = pt.transform(a_sp_ref)
        buffer = pt.change_buffer_units(a_sp_ref)
        if buffer > 0:
            ul_geo_x = c_x - buffer
            ul_geo_y = c_y + buffer
            lr_geo_x = c_x + buffer
            lr_geo_y = c_y - buffer
            ul_px, ul_py = self.wld2pix(ul_geo_x, ul_geo_y)
            lr_px, lr_py = self.wld2pix(lr_geo_x, lr_geo_y)
            ul_px = math.floor(ul_px)
            ul_py = math.floor(ul_py)
            lr_px = math.ceil(lr_px)
            lr_py = math.ceil(lr_py)
            win_xsize = lr_px - ul_px
            win_ysize = lr_py - ul_py
            # Reduce the window size if it is straddles the image extents.
            # If the resulting window is less than or equal to 0, the ROI is outside of
            # the image's extents.
            if ul_px < 0:
                win_xsize = win_xsize + ul_px
                ul_px = 0
            elif ul_px + win_xsize > self.info.ncols:
                win_xsize = self.info.ncols - ul_px
            if ul_py < 0:
                win_ysize = win_ysize + ul_py
                ul_py = 0
            elif ul_py + win_ysize >= self.info.nrows:
                win_ysize = self.info.nrows - ul_py
        else:
            # The ROI is a singular point. Extract the pixel, but not if
            # the point is outside the image's extents.
            c_px, c_py = self.wld2pix(c_x, c_y)
            ul_px = math.floor(c_px)
            ul_py = math.floor(c_py)
            if ul_px >= 0 and ul_px <= self.info.ncols and \
               ul_py >= 0 and ul_py <= self.info.nrows:
                win_xsize = 1
                win_ysize = 1
            else:
                win_xsize = 0
                win_ysize = 0
        return (ul_px, ul_py, win_xsize, win_ysize)


    def mask_roi_shape(self, pt, arr_info, ignore_val):
        """
        Mask the pixels in the ArrayInfo.data's array that are outside
        the region of interest.

        arr_info is the ArrayInfo instance.
        pt is the Point.
        The pixels outside the shape are set to ignore_val. If ignore_val is None,
        the no-data value set on each band of the asset/image is used. If
        ignore_val is set use the same value for every band of the asset/image.

        arr_info.data is updated in place, so the function returns nothing.

        Currently only supports ROI_SHP_SQUARE and ROI_SHP_CIRCLE. No masking
        is done in the case of squares. For circles, the size of the array
        must be greater than four pixels. Raise an AssetReaderError if it is not.

        Parameters
        ----------

        pt : pointstats.Point
            Point to use
        arr_info : ArrayInfo
            The data
        ignore_val : float
            ignore value to use, if None then the image no data is used

        """
        if pt.shape==pointstats.ROI_SHP_SQUARE:
            # Do nothing. arr_info.data is already the correct shape.
            pass
        elif pt.shape==pointstats.ROI_SHP_CIRCLE:
            if arr_info.data.size < 5:
                raise AssetReaderError(
                    "There must be at least 4 pixels in the array to mask it " \
                    "using a circular ROI.")
            # Include all pixels inside the circle's boundary and those
            # that touch the circle's boundary.
            # The circle's boundary touches a pixel if at least one corner of
            # the pixel is inside the circle. A corner is outside the circle if
            # it's distance to the circle's centre is greater than the circle's
            # radius.
            a_sp_ref = osr.SpatialReference()
            a_sp_ref.ImportFromWkt(self.info.projection)
            # Circle centre and radius in the same CRS as the image.
            c_x, c_y = pt.transform(a_sp_ref)
            radius = pt.change_buffer_units(a_sp_ref)
            def outside(lower, right):
                # Return an array where True means the pixels's corner is
                # outside the circle.
                # For upper-left corners, use lower=0, right=0
                # For upper-right corners, use lower=0, right=1, and so on.
                ys, xs = numpy.mgrid[
                    lower:arr_info.win_ysize + lower,
                    right:arr_info.win_xsize + right]
                ys = arr_info.uly - ys * arr_info.y_res
                xs = arr_info.ulx + xs * arr_info.x_res
                return (ys-c_y)**2 + (xs-c_x)**2 > radius**2
            # Pixels are outside the circle where all corners are outside.
            ul_outside = outside(0, 0)
            ur_outside = outside(0, 1)
            ll_outside = outside(1, 0)
            lr_outside = outside(1, 1)
            px_outside = numpy.all(
                numpy.array([ul_outside, ur_outside, ll_outside, lr_outside]),
                axis=0)
            # Apply a mask per-band because the nodataval can vary by band.
            num_bands = arr_info.data.shape[0]
            for idx in range(num_bands):
                nodata_val = ignore_val if ignore_val else self.info.nodataval[idx]
                arr_info.data[idx][px_outside] = nodata_val
                arr_info.data.mask[idx][px_outside] = True
        else:
            raise AssetReaderError(f"Unknown ROI shape {pt.shape}")
    
    
    def wld2pix(self, geox, geoy):
        """
        converts a set of map coords to pixel coords

        Parameters
        ----------
        geox, geoy : float
            The input coordinates

        Returns
        -------
        tuple of (x, y)

        """
        inv_transform = gdal.InvGeoTransform(self.info.transform)
        x, y = gdal.ApplyGeoTransform(inv_transform, geox, geoy)
        return (x, y)

    
    def pix2wld(self, x, y):
        """
        converts a set of pixel coords to map coords

        Parameters
        ----------
        x, y : int
            The input coordinates

        Returns
        -------
        tuple of (geox, geoy)
        """
        geo_x, geo_y = gdal.ApplyGeoTransform(self.info.transform, x, y)
        return (geo_x, geo_y)
