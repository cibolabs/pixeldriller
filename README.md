# pixelstac

pixelstac is for the following use case:

Given a STAC endpoint, set of X-Y-Time points, and a buffer, return the n nearest-in-time zonal stats for all bands of the specified raster assets.

## Development

The enclosed Dockerfile creates the environment that is used for development.
Development occurs on an AWS EC2 instance in the us-west-2 region.

Example:

```bash
tony@dev-host:~/dev/cibolabs/pixelstac$ make build-dev
...
tony@dev-host:~/dev/cibolabs/pixelstac$ make run-dev
docker run -it --mount type=bind,src=/home/tony/dev/cibolabs/pixelstac,dst=/root/pixelstac  --mount type=bind,src=/tmp,dst=/tmp pixelstac:dev
# Now, in the container, source the activate_dev file to initialise the dev environment
root@5d63691b9aa8:~/pixelstac# source activate_dev
Obtaining file:///root/pixelstac
  Preparing metadata (setup.py) ... done
Installing collected packages: pixelstac
  Running setup.py develop for pixelstac
Successfully installed pixelstac-dev
WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager. It is recommended to use a virtual environment instead: https://pip.pypa.io/warnings/venv
root@5d63691b9aa8:~/pixelstac#
```

## Assumptions

- GDAL is available on the system
- in order to open the STAC assets for the Items returned from pixelstac.query():
  - assets have a http, https, or ftp URL (as their href attribute)
  - no authentication is required to access them
  - the GDAL on the system was been built against libcurl
  - GDAL's CPL_VSIL_CURL_ALLOWED_EXTENSIONS environment variable is set and
    contains the filename extensions of the assets, e.g.
    `CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF,.tiff,.vrt,.jp2"` 
  - see [GDAL /vsicurl driver](https://gdal.org/user/virtual_file_systems.html#vsicurl-http-https-ftp-files-random-access)
  - For exampe, you should be able to read tif files if the following command
    returns information about the file,
    `CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif" gdalinfo /vsicurl/https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/54/H/VE/2022/7/S2A_54HVE_20220730_0_L2A/B02.tif`
- All assets of all items returned from pixelstac.query() have the same
  coordinate reference system so that the buffer value used to define the
  ROI is applied consistently across all assets
- The coordinate reference system of the assets being read define north as up.

## Tests

Require:
- pytest
- CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"
- the earth-search stac with endpoint https://earth-search.aws.element84.com/v0
  and sentinel-2-l2a-cogs collection

To run all tests, from the project's root directory:

```bash
pytest tests/
```