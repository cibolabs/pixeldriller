"""
For reading raster assets.

"""

from osgeo import gdal

# List of datatype names corresponding to GDAL datatype numbers. 
# The index of this list corresponds to the gdal datatype number. Not sure if this 
# is a bit obscure and cryptic.....
GDAL_DATA_TYPE_NAMES = ['Unknown', 'UnsignedByte', 'UnsignedInt16', 'SignedInt16',
    'UnsignedInt32', 'SignedInt32', 'Float32', 'Float64', 'ComplexInt16',
    'ComplexInt32','ComplexFloat32', 'ComplexFloat64']

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
        self.data_type_name = GDAL_DATA_TYPE_NAMES[self.data_type]
        
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


def asset_info(item, ref_asset):
    """
    Return an asset_info.ImageInfo object with information about the
    raster asset in the pystac.item.Item.

    """
    filename = f"/vsicurl/{item.assets[ref_asset].href}"
    return ImageInfo(filename)


class AssetReaderError(Exception):
    """For exceptions raised in this module."""
