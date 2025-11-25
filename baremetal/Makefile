VENDOR=Baremetal
NAME=Baremetal
VERSION=latest

# Override the standard vrnetlab build - baremetal doesn't need an image file
docker-image:
	@echo "Building vrnetlab/baremetal:$(VERSION)"
	cp ../common/healthcheck.py docker/
	cp ../common/vrnetlab.py docker/
	(cd docker; docker build --build-arg VERSION=$(VERSION) -t vrnetlab/baremetal:$(VERSION) .)
	rm -f docker/healthcheck.py docker/vrnetlab.py

clean:
	rm -f docker/healthcheck.py docker/vrnetlab.py

.PHONY: docker-image clean
