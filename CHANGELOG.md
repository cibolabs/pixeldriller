# Change log

## [Unreleased]

## [v0.2.0 - 2023-01-17]

First public release.

### Added

- support for selecting the nearest n items to the field survey date
- pass the ignore_val parameter in drill.drill to the downstream calc_stats
- support for specifying STAC-specific item properties to filter the
  STAC searches by
- This changelog, contributing, and license
- .flake8 for linting and CI steps

### Changed

- Wrote tutorial and developer guide
- Reviewed and edited the python docstrings
- Refactored the module and class names
- the Point constructor no longer takes a tuple for the x, y, time point,
  which are now single-value parameters
- A point's coordinate reference system can be specified using an epsg number
- drill.create_stac_drillers will accept the STAC endpoint as a string

### Fixed

## [v0.1.1 - 2022-12-]

### Added

- initial work on the Sphinx docs
- The ArrayInfo.isempty() function

### Changed

- improved handling of failed image reads, ItemPoints.read_data() returns
  a bool for successful or failed reads

### Fixed

- improved handling of failed image reads

## [v0.1.0 ]

First release, not for public use
