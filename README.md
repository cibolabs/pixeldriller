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
