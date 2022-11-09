# Profiling and benchmarking

This directory contains profiling and benchmarking code.
This README contains the results of historic profiling and benchmarking
that has been performed, which may not be reflected in the current code.

## 9 November 2022

## Benchark

Average time for three runs:

| num points queried | average run time (secs) |
| ------------------ | ----------------------- |
| 1                  | 5.3                     |
| 5                  | 15.2                    |
| 25                 | 77.7                    |

Fixed properties:

- data: points.geojson
- STAC endpoint: https://earth-search.aws.element84.com/v0
- collection: 'sentinel-s2-l2a-cogs'
- bands: ['B02', 'B03']
- buffer: = 50 m either side of point
- temporal range: 10 days either side of the point's date

```bash
# One point
> python3 -m profiles.benchmark --mode benchmark --repeat 1 --read_from 0 --read_to 1
Collected 1 sets of stats.
Executed pixelstac.query 1 times with results: [5.9512473326176405] seconds.
> python3 -m profiles.benchmark --mode benchmark --repeat 1 --read_from 100 --read_to 101
Collected 1 sets of stats.
Executed pixelstac.query 1 times with results: [3.798935057595372] seconds.
> python3 -m profiles.benchmark --mode benchmark --repeat 1 --read_from 1000 --read_to 1001
Collected 1 sets of stats.
Executed pixelstac.query 1 times with results: [6.16525112092495] seconds.

# Five points
> python3 -m profiles.benchmark --mode benchmark --repeat 1 --read_from 0 --read_to 5
Collected 5 sets of stats.
Executed pixelstac.query 1 times with results: [10.424907058477402] seconds.
> python3 -m profiles.benchmark --mode benchmark --repeat 1 --read_from 100 --read_to 105
Collected 5 sets of stats.
Executed pixelstac.query 1 times with results: [14.301447238773108] seconds.
> python3 -m profiles.benchmark --mode benchmark --repeat 1 --read_from 1000 --read_to 1005
Collected 5 sets of stats.
Executed pixelstac.query 1 times with results: [20.960727352648973] seconds.

# 25 points
> python3 -m profiles.benchmark --mode benchmark --repeat 1 --read_from 0 --read_to 25
Collected 25 sets of stats.
Executed pixelstac.query 1 times with results: [54.86757488921285] seconds.
> python3 -m profiles.benchmark --mode benchmark --repeat 1 --read_from 100 --read_to 125
Collected 25 sets of stats.
Executed pixelstac.query 1 times with results: [83.82501234486699] seconds.
> python3 -m profiles.benchmark --mode benchmark --repeat 1 --read_from 1000 --read_to 1025
Collected 25 sets of stats.
Executed pixelstac.query 1 times with results: [94.45151347108185] seconds.
```

## Profile

It seems that most time is spent in pointstats.calc_stats, which is split
between opening the gdal dataset and reading the arrays in.

```bash
> python3 -m profiles.benchmark --mode profile --pstats pstac.profile --read_from 0 --read_to 25
Collected 25 sets of stats.
Wrote profile stats to pstac.profile.
> python3 -m pstats pstac.profile
pstac.profile% strip
pstac.profile% sort cumulative
pstac.profile% stats 30
Wed Nov  9 11:33:56 2022    pstac.profile

         350651 function calls (350254 primitive calls) in 60.491 seconds

   Ordered by: cumulative time
   List reduced from 881 to 30 due to restriction <30>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      4/1    0.000    0.000   60.491   60.491 {built-in method builtins.exec}
        1    0.000    0.000   60.491   60.491 <string>:1(<module>)
        1    0.001    0.001   60.491   60.491 benchmark.py:97(run_query)
        1    0.000    0.000   60.463   60.463 pixelstac.py:52(query)
       25    0.001    0.000   57.947    2.318 pointstats.py:98(calc_stats)
      316    0.007    0.000   57.946    0.183 pointstats.py:131(calc_stats)
      632    0.048    0.000   57.887    0.092 asset_reader.py:115(read_roi)
      632    0.004    0.000   35.169    0.056 gdal.py:3643(ReadAsArray)
      632    0.005    0.000   35.161    0.056 gdal_array.py:393(BandReadAsArray)
      632    0.001    0.000   35.147    0.056 gdal_array.py:109(BandRasterIONumPy)
      632   35.146    0.056   35.146    0.056 {built-in method osgeo._gdal_array.BandRasterIONumPy}
      632    0.002    0.000   22.367    0.035 asset_reader.py:105(asset_info)
      632    0.027    0.000   22.364    0.035 asset_reader.py:45(__init__)
     1264    0.002    0.000   21.889    0.017 gdal.py:4110(Open)
     1264   21.887    0.017   21.887    0.017 {built-in method osgeo._gdal.Open}
       26    0.000    0.000    2.404    0.092 stac_io.py:181(read_json)
       26    0.000    0.000    2.364    0.091 stac_api_io.py:57(read_text)
       26    0.001    0.000    2.363    0.091 stac_api_io.py:103(request)
       25    0.000    0.000    2.345    0.094 pixelstac.py:164(stac_search)
       26    0.001    0.000    2.343    0.090 sessions.py:626(send)
      341    0.000    0.000    2.340    0.007 item_search.py:634(items)
       50    0.000    0.000    2.340    0.047 item_search.py:606(item_collections)
       50    0.000    0.000    2.234    0.045 stac_api_io.py:208(get_pages)
      442    0.001    0.000    2.181    0.005 socket.py:691(readinto)
      442    0.001    0.000    2.180    0.005 ssl.py:1262(recv_into)
      442    0.001    0.000    2.180    0.005 ssl.py:1120(read)
      442    2.179    0.005    2.179    0.005 {method 'read' of '_ssl._SSLSocket' objects}
       26    0.001    0.000    2.155    0.083 adapters.py:394(send)
       26    0.001    0.000    2.143    0.082 connectionpool.py:518(urlopen)
       26    0.001    0.000    2.135    0.082 connectionpool.py:357(_make_request)
```
