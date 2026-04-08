VENDOR=Baremetal-Sushy
NAME=Baremetal-Sushy
VERSION=latest

# Build the baremetal-sushy container with libvirt and QEMU
docker-image:
	@echo "Building vrnetlab/baremetal-sushy:$(VERSION)"
	(cd docker; docker build \
		--build-arg VERSION=$(VERSION) \
		-t vrnetlab/baremetal-sushy:$(VERSION) .)

clean:
	@echo "Nothing to clean (all files are in docker/ directory)"

deploy:
	mkdir -p /tmp/bmh1-libvirt
	sudo containerlab deploy -t vm_setup.clab.yaml
	kind export kubeconfig --name cluster
	docker network disconnect kind cluster-control-plane
	sed -i 's|server: https://127.0.0.1:[0-9]*|server: https://172.20.0.10:6443|' ~/.kube/config
	kubectl wait --for=condition=Ready node --all --timeout=180s

destroy:
	sudo containerlab destroy -t vm_setup.clab.yaml --cleanup

.PHONY: docker-image clean deploy destroy
