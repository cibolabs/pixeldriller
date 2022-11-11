#!/usr/bin/env python

"""
Benchmark or profile pixelstac.

Fixed properties:

- STAC endpoint: https://earth-search.aws.element84.com/v0
- collection = 'sentinel-s2-l2a-cogs'
- bands = ['B02', 'B03']
- buffer = 50 m either side of point
- search for images 10 days either side of the point's date

Benchmark mode::

    > python3 -m profiles.benchmark --mode benchmark --repeat 1 --read_from 0 --read_to 25

Profiling mode, to create the file pstac.profile with profiling information::

    > python3 -m profiles.benchmark --mode profile --pstats pstac.profile --read_from 0 --read_to 25

To read the profile information, in pstac.profile, use the pstats
profiler either from within python
https://docs.python.org/3/library/profile.html#instant-user-s-manual
or the stats browser
https://www.stefaanlippens.net/python_profiling_with_pstats_interactive_mode/

"""

import json
import time
import datetime
import argparse
import pathlib
import timeit
import cProfile
import logging
import sys

from osgeo import osr

from pixelstac import pixelstac
from pixelstac import pointstats

MODE_PROFILE = 'profile'
MODE_BENCHMARK = 'benchmark'

def get_cmdargs():
    """
    Get the command line arguments.

    """
    parser = argparse.ArgumentParser(
        description="Benchmark or profile pixelstac.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    # Benchmark and profiling options.
    parser.add_argument(
        "--mode", default=MODE_BENCHMARK,
        choices=[MODE_BENCHMARK, MODE_PROFILE],
        help='Run in one of these modes.')
    parser.add_argument("--repeat", default=1, type=int,
        help=("Run the test this many times. Only relevant for " +
              f"{MODE_BENCHMARK} mode." ))
    parser.add_argument("--pstats", default=None,
        help=("The output profile stats file, which is readable by the " +
              f"pstats module. Only relevant for {MODE_PROFILE} mode. " +
              "The default is to print to standard output."))
    # Options when reading points from file.
    points_file = pathlib.Path(__file__).parent / 'points.geojson'
    parser.add_argument(
        "--points_file", default=points_file,
        help="GeoJson file with data points.")
    parser.add_argument(
        "--read_from", default=0, type=int,
        help="The index of the first point in the --points_file file to read from.")
    parser.add_argument(
        "--read_to", default=None, type=int,
        help="The index of the last point in the --points_file file to read up to.")
    parser.add_argument(
        "--concurrent", action="store_true",
        help="Extract the stats in concurrent threads")
    parser.add_argument(
        "--verbose", "-v", action='count', default=0)
    args = parser.parse_args()
    # Configure log level based on verbosity.
    # -v=warnings, -vv=informational, -vvv=debug
    levels = {0:logging.ERROR, 1:logging.WARNING, 2:logging.INFO,
              3:logging.DEBUG}
    logging.basicConfig(
        level=levels[args.verbose],
        stream=sys.stdout)
    return args


def create_points(json_file, read_from, read_to):
    """
    Return a list of pixelstac.Point objects from the given json objects.

    read_from and read_to are the indices of the first and last points to
    read from the file.

    """
    with open(json_file, 'r') as fh:
        feat_coll = json.load(fh)
    sp_ref = osr.SpatialReference()
    sp_ref.ImportFromEPSG(4326)
    dt = datetime.timedelta(days=10) # 10 days either side
    buff = 50 # 50 m buffer around point.
    shp = pointstats.ROI_SHP_SQUARE
    points = []
    for feature in feat_coll['features'][read_from:read_to]:
        geo_x, geo_y = feature['geometry']['coordinates']
        gmtime = time.gmtime(feature['properties']['time']/1000)
        coll_time = datetime.datetime(*gmtime[:6], tzinfo=datetime.timezone.utc)
        # Also add all the field data (a dict) from the geojson.
        field_data = feature['properties']
        points.append(
            pointstats.Point(
                (geo_x, geo_y, coll_time), sp_ref, dt, buff, shp, 
                other_attributes=field_data))
    return points


def run_query():
    """Run a pixelstac query."""
    # Extract
    points = create_points(
        bm_cmdargs.points_file, bm_cmdargs.read_from, bm_cmdargs.read_to)
    endpoint = "https://earth-search.aws.element84.com/v0"
    collections = ['sentinel-s2-l2a-cogs']
    raster_assets = ['B02', 'B03']
    pt_stats_list = pixelstac.query(
        endpoint, points, raster_assets, collections=collections,
        std_stats=[pointstats.STATS_RAW, pointstats.STATS_MEAN],
        concurrent=bm_cmdargs.concurrent)
    print(f"Collected {len(points)} sets of stats.")


def run_benchmark():
    """Console entry point configured in setup.cfg."""
    if bm_cmdargs.mode == MODE_BENCHMARK:
        duration = timeit.repeat(run_query, repeat=bm_cmdargs.repeat, number=1)
        print(f"Executed pixelstac.query {bm_cmdargs.repeat} times " +
              f"with results: {duration} seconds.")
    else:
        cProfile.run('run_query()', bm_cmdargs.pstats)
        print(f"Wrote profile stats to {bm_cmdargs.pstats}.")


if __name__ == '__main__':
    bm_cmdargs = get_cmdargs() # available in global namespace.
    run_benchmark()
