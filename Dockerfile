FROM ubuntu:22.04

ENV TZ=Australia/Brisbane
ARG DEBIAN_FRONTEND=noninteractive

# Use us-west-2 mirrors.
RUN sed -i 's/http:\/\/ports./http:\/\/us-west-2.ec2.ports./g' /etc/apt/sources.list

# Update Ubuntu software stack and install required dependencies
RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install -y curl python3-pip git python3-gdal gdal-bin \
    python3-pytest python3-coverage python3-dateutil python3-requests
#                python3-dev python3-requests python3-pip curl python3-psycopg2 \
#                python3-dev python3-requests python3-pip curl \
#                wget git g++ cmake libhdf5-dev libgdal-dev unzip
RUN apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*

# pypi packages
# pystac-client, monitor updates and test regularly
RUN pip install pystac-client==0.4.0

# Needed?
#ENV PATH=${SW_VOLUME}/bin:${SW_VOLUME}/local/bin:${PATH}
#ENV PYTHONPATH=${SW_VOLUME}/local/lib/python3.10/dist-packages:${SW_VOLUME}/lib/python3.10/site-packages
#ENV LD_LIBRARY_PATH=${SW_VOLUME}/lib

ENV PYTHONUNBUFFERED=1

ENV GDAL_PAM_ENABLED=NO
ENV GDAL_CACHEMAX=1024000000
ENV GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR
ENV GDAL_HTTP_MERGE_CONSECUTIVE_RANGES=YES
ENV GDAL_HTTP_MULTIPLEX=YES
ENV CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF,.tiff,.vrt,.zip"
ENV VSI_CACHE=True
ENV VSI_CACHE_SIZE=1024000000
ENV GDAL_HTTP_MAX_RETRY=10
ENV GDAL_HTTP_MAX_RETRY=3
ENV CPL_ZIP_ENCODING=UTF-8

WORKDIR /root/pixeldriller
