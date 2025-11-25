#!/bin/bash
# Test script to verify QEMU arguments without deploying

set -e

cd "$(dirname "$0")"

# Build image if needed
if [ "$1" = "--build" ]; then
    echo "Building image..."
    make docker-image
fi

# Run container temporarily to see QEMU args
echo "Testing QEMU arguments..."
docker run --rm \
    --privileged \
    -v $(pwd)/alpine.iso:/cdrom/alpine.iso:ro \
    -e QEMU_DISK_SIZE="12G" \
    -e QEMU_ARGS="-cdrom /cdrom/alpine.iso
-boot d
-vnc :0
-device virtio-net-pci,netdev=p01,bus=pci.1,addr=0x2
-netdev tap,id=p01,ifname=tap1,script=/etc/tc-tap-ifup,downscript=no" \
    vrnetlab/baremetal:latest \
    --trace 2>&1 | grep -A 1 "qemu cmd:"

echo ""
echo "To build and test: ./test-qemu-args.sh --build"
echo "To just test: ./test-qemu-args.sh"
