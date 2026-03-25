VENDOR=Baremetal-Sushy
NAME=Baremetal-Sushy
VERSION=latest
SUSHY_VERSION=2.2.0

# Build the baremetal-sushy container with libvirt and sushy-emulator
docker-image:
	@echo "Building vrnetlab/baremetal-sushy:$(VERSION)"
	(cd docker; docker build \
		--build-arg VERSION=$(VERSION) \
		--build-arg SUSHY_TOOLS_VERSION=$(SUSHY_VERSION) \
		-t vrnetlab/baremetal-sushy:$(VERSION) .)

clean:
	@echo "Nothing to clean (all files are in docker/ directory)"

.PHONY: docker-image clean
