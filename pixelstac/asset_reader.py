"""
For reading pixel data and metadata from raster assets.

"""

import math
import numpy

from osgeo import gdal
from osgeo import osr

class ImageInfo:
    """
    An object with metadata for the given image, in GDAL conventions.
    Pass an already-opened gdal.Dataset object to the constructor.

    Sourced from rios:
    https://github.com/ubarsc/rios/blob/master/rios/fileinfo.py
    
    Object contains the following fields
        * **x_min**            Map X coord of left edge of left-most pixel
        * **x_max**            Map X coord of right edge of right-most pixel
        * **y_min**            Map Y coord of bottom edge of bottom pixel
        * **y_max**            Map Y coord of top edge of top-most pixel
        * **x_res**            Map coord size of each pixel, in X direction
        * **y_res**            Map coord size of each pixel, in Y direction
        * **nrows**            Number of rows in image
        * **ncols**            Number of columns in image
        * **transform**        Transformation params to map between pixel and map coords, in GDAL form
        * **projection**       WKT string of projection
        * **raster_count**     Number of rasters in file
        * **lnames**           Names of the layers as a list.
        * **layer_type**       "thematic" or "athematic", if it is set
        * **data_type**        Data type for the first band (as a GDAL integer constant)
        * **data_type_name**   Data type for the first band (as a human-readable string)
        * **nodataval**        Value used as the no-data indicator (per band)
    
    The omit_per_band argument on the constructor is provided in order to speed up the
    access of very large VRT stacks. The information which is normally extracted
    from each band will, in that case, trigger a gdal.Open() for each band, which
    can be quite slow. So, if none of that information is actually required, then
    setting omit_per_band=True will omit that information, but will return as quickly
    as for a normal single file.

    """
    def __init__(self, ds, omit_per_band=False):
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

    The attributes are:
    - data: the numpy masked array containing the pixel data
    - asset_id: the id of the Stac Item's asset from which the data was read
    - The pixel window read from the raster asset in pixel coordinates:
        - xoff, yoff, win_xsize, win_ysize
        - where xoff and yoff are the coordinates of the upper left pixel in
          the array in pixel coordinates
    - The bounding box of the array in image coordinates, defined using
      two points:
      - upper left (ulx, uly)
      - lower right (lrx, lry)
    - The pixel size in the same units as the image coordinate reference system:
        - x_res, y_res

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


class AssetReader:
    """
    Encapsulates the GDAL Dataset object, metadata about a
    STAC asset (an ImageInfo object) and algorithms
    used to read arrays of pixels around a list of points.

    """
    def __init__(self, item, asset_id):
        self.item = item
        self.asset_id = asset_id
        self.filepath = f"/vsicurl/{item.assets[asset_id].href}"
        self.dataset = gdal.Open(self.filepath, gdal.GA_ReadOnly)
        self.info = ImageInfo(self.dataset)


    def read_data(self, points, ignore_val=None):
        """
        Read the data around each of the given points and add it to the point.

        The data is read using read_roi(), passing it the ignore_val.
        The data is attached to each point.

        Once read, the ItemStats object (corresponding to this asset's Item)
        of every Point will contain the pixel
        data (numpy masked array) and ArrayInfo object for the asset.

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
            # TODO: update test for read_data().
            arr_info = self.read_roi(pt, ignore_val=ignore_val)
            pt.add_data(self.item, arr_info)


    def read_roi(self, pt, ignore_val=None):
        """
        Extract the smallest number of pixels required to cover the region of
        interest. By doing so, the area covered by the returned pixels is slightly
        larger than the region of interest defined by the point's location
        and buffer.
        
        Return an ArrayInfo object.

        The ArrayInfo object contains a 3D numpy masked array (numpy.ma.MaskedArray)
        with the pixel data. If ignore_val=None, the no-data value set on the
        asset is used.
        
        The returned ArrayInfo object also contains information about the ROI's
        location within the image.

        If the ROI straddles the image extents, the ROI is clipped to the extents
        (i.e. only that portion of the image that is within the extents is returned).

        """
        xoff, yoff, win_xsize, win_ysize = self.get_pix_window(pt)
        # Reduce the window size if it is straddles the image extents.
        # If the resulting window is less than or equal to 0, the ROI is outside of
        # the image's extents.
        if xoff < 0:
            win_xsize = win_xsize + xoff
            xoff = 0
        elif xoff + win_xsize > self.info.ncols:
            win_xsize = self.info.ncols - xoff
        if yoff < 0:
            win_ysize = win_ysize + yoff
            yoff = 0
        elif yoff + win_ysize >= self.info.nrows:
            win_ysize = self.info.nrows - yoff
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
        # ROI bounds in image coordinates:
        ulx, uly = self.pix2wld(xoff, yoff) # Coords of the upper-left pixel's upper-left corner
        lrx, lry = self.pix2wld(xoff+win_xsize, yoff+win_ysize) # Coords of the upper-left pixel's upper-left corner
        arr_info = ArrayInfo(
            m_arr, self.asset_id,
            xoff, yoff, win_xsize, win_ysize,
            ulx, uly, lrx, lry, self.info.x_res, self.info.y_res)
        return arr_info


    def get_pix_window(self, pt):
        """
        Return the region of interest for the point in the image's pixel
        coordinate space as: (xoff, yoff, win_xsize, win_ysize).
    
        xoff, yoff is the grid location of the top-left pixel of the ROI.
        win_xsize and win_ysize are the number of columns and rows to read
        from the image.
    
        An xoff, yoff of 0, 0 corresponds to the top-left pixel of the image.
        An xoff, yoff of (ncols-1, nrows-1) corresponds to the bottom-right 
        pixel of the image. The caller should check to see that the ROI is
        within the image bounds.
    
        The region of interest about the point in geo-coordinates
        is unlikely to align with the pixel grid. This function increases the
        size of the window to the smallest possible area that encloses the
        region of interest.
    
        """
        a_sp_ref = osr.SpatialReference()
        a_sp_ref.ImportFromWkt(self.info.projection)
        c_x, c_y = pt.transform(a_sp_ref)
        ul_geo_x = c_x - pt.buffer
        ul_geo_y = c_y + pt.buffer
        lr_geo_x = c_x + pt.buffer
        lr_geo_y = c_y - pt.buffer
        ul_px, ul_py = self.wld2pix(ul_geo_x, ul_geo_y)
        lr_px, lr_py = self.wld2pix(lr_geo_x, lr_geo_y)
        ul_px = math.floor(ul_px)
        ul_py = math.floor(ul_py)
        lr_px = math.ceil(lr_px)
        lr_py = math.ceil(lr_py)
        win_xsize = lr_px - ul_px
        win_ysize = lr_py - ul_py
        return (ul_px, ul_py, win_xsize, win_ysize)


    def wld2pix(self, geox, geoy):
        """converts a set of map coords to pixel coords"""
        inv_transform = gdal.InvGeoTransform(self.info.transform)
        x, y = gdal.ApplyGeoTransform(inv_transform, geox, geoy)
        return (x, y)

    
    def pix2wld(self, x, y):
        """converts a set of pixel coords to map coords"""
        geo_x, geo_y = gdal.ApplyGeoTransform(self.info.transform, x, y)
        return (geo_x, geo_y)


class AssetReaderError(Exception):
    """For exceptions raised in this module."""
