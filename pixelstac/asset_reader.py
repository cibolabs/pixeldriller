"""
For reading raster assets.

"""

import math
import numpy

from osgeo import gdal
from osgeo import osr

class ImageInfo:
    """
    An object with metadata for the given image, in GDAL conventions. 

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
    def __init__(self, filename, omit_per_band=False):
        ds = gdal.Open(str(filename), gdal.GA_ReadOnly)
        if ds is None:
            raise AssetReaderError(f"Unable to open file {filename}")
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
        self.data_type_name = gdal.GetDataTypeName(self.data_type) #GDAL_DATA_TYPE_NAMES[self.data_type]
        del ds


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


def asset_filepath(item, asset):
    """
    Get the file path to the item's asset, in a form readable by GDAL.

    """
    return f"/vsicurl/{item.assets[asset].href}"


def asset_info(item, asset):
    """
    Return an asset_info.ImageInfo object with information about the
    raster asset in the pystac.item.Item.

    """
    filename = asset_filepath(item, asset)
    return ImageInfo(filename)


def read_roi(item, asset, pt, ignore_val=None):
    """
    Extract the smallest number of pixels required to cover the region of
    interest. By doing so, the area covered by the returned pixels is slightly
    larger than the region of interest defined by the point's location
    and buffer.

    Return a 3D numpy masked array (of type numpy.ma) by using the ignore_val
    to create a mask. If ignore_val=None, the no-data values set on each
    band of the asset are used.

    Assume that the roi is within the image extents.
    A future version will return None if the extent of the pixels to be
    extracted is beyond the image extents.
    
    """
    # convert centre of point to same coord reference system as filename
    a_info = asset_info(item, asset)
    xoff, yoff, win_xsize, win_ysize = get_pix_window(pt, a_info)
    # TODO: check the ROI is within the image's bounds
    # And that the ROI is at least 1 pixel in size; i.e.:
    # 0 <= ul_px < lr_px < ncols
    # 0 <= ul_py < lr_py < nrows
    ds = gdal.Open(asset_filepath(item, asset), gdal.GA_ReadOnly)
    band_data = []
    mask_data = []
    for band_num in range(1, a_info.raster_count + 1):
        band = ds.GetRasterBand(band_num)
        b_arr = band.ReadAsArray(xoff, yoff, win_xsize, win_ysize)
        band_data.append(b_arr)
        nodata_val = a_info.nodataval[band_num-1]
        if nodata_val is None:
            mask = numpy.zeros(b_arr.shape, dtype=bool)
        else:
            mask = b_arr==nodata_val
        mask_data.append(mask)
    del ds
    arr = numpy.array(band_data)
    mask = numpy.array(mask_data)
    m_arr = numpy.ma.masked_array(arr, mask=mask)
    return m_arr


def get_pix_window(pt, a_info):
    """
    Return the region of interest for the point in the image's pixel
    coordinate space as: (xoff, yoff, win_xsize, win_ysize).

    a_info is an ImageInfo object for the raster asset.

    c_x, c_y is the geo-coordinate of the centre of the ROI.
    buffer is the distance of the edge of the ROI from its centre.

    xoff, yoff is the grid location of the top-left pixel of the ROI.

    An xoff, yoff of 0, 0 corresponds to the top-left pixel of the image.
    An xoff, yoff of (ncols-1, nrows-1) corresponds to the bottom-right 
    pixel of the image. The caller should check to see that the ROI is
    within the image bounds.

    win_xsize, win_ysize is the size of the window, in pixels, to extract.

    The ROI in geo-coordinates (c_x, c_y, buffer) is unlikely to align with
    the pixel grid. This function increases the size of the ROI so it returns
    the smallest possible area that encloses the requested ROI.

    """
    a_sp_ref = osr.SpatialReference()
    a_sp_ref.ImportFromWkt(a_info.projection)
    c_x, c_y = pt.transform(a_sp_ref)
    ul_geo_x = c_x - pt.buffer
    ul_geo_y = c_y + pt.buffer
    lr_geo_x = c_x + pt.buffer
    lr_geo_y = c_y - pt.buffer
    ul_px, ul_py = wld2pix(a_info.transform, ul_geo_x, ul_geo_y)
    lr_px, lr_py = wld2pix(a_info.transform, lr_geo_x, lr_geo_y)
    ul_px = math.floor(ul_px)
    ul_py = math.floor(ul_py)
    lr_px = math.ceil(lr_px)
    lr_py = math.ceil(lr_py)
    win_xsize = lr_px - ul_px
    win_ysize = lr_py - ul_py
    return (ul_px, ul_py, win_xsize, win_ysize)


def wld2pix(transform, geox, geoy):
    """converts a set of map coords to pixel coords"""
    inv_transform = gdal.InvGeoTransform(transform)
    x, y = gdal.ApplyGeoTransform(inv_transform, geox, geoy)
    return (x, y)


class AssetReaderError(Exception):
    """For exceptions raised in this module."""
