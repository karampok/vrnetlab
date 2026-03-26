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

deploy:
	sudo clab deploy -t vm_setup.clab.yaml
	kind export kubeconfig --name cluster
	kubectl wait --for=condition=Ready node --all --timeout=180s
	docker network disconnect kind cluster-control-plane
	docker network disconnect kind cluster-worker
	sed -i 's|server: https://127.0.0.1:[0-9]*|server: https://172.20.0.10:6443|' ~/.kube/config

destroy:
	sudo clab destroy -t vm_setup.clab.yaml

.PHONY: docker-image clean deploy destroy
