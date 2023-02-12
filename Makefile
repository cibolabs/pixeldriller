TAG=pixeldriller:dev
PWD=$(shell pwd)
WORKDIR=/root/pixeldriller # working directing inside the container

default: build-dev

# activate_dev is sourced from within the container. It installs an editable
# version of this package in the container.
build-dev: activate_dev
	docker build --tag $(TAG) --rm .

run-dev:
	docker run -it --mount type=bind,src=$(PWD),dst=$(WORKDIR) --mount type=bind,src=/tmp,dst=/tmp $(TAG)

# Create the activate_dev file. It is sourced from within the container.
# It installs an editable version of the pixelstac package in the container.
activate_dev:
	echo "pip install --editable ." > activate_dev

clean:
	rm activate_dev
