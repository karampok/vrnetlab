#!/bin/bash
# Quick script to check QEMU args in running container

CONTAINER="clab-vm-baremetal-vm1"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "Container ${CONTAINER} is not running"
    echo "Deploy with: sudo containerlab deploy -t vm_setup.clab.yaml"
    exit 1
fi

echo "=== QEMU Command ==="
docker logs ${CONTAINER} 2>&1 | grep "qemu cmd:" | tail -1 | sed 's/.*qemu cmd: //'

echo ""
echo "=== QEMU Command List (formatted) ==="
docker logs ${CONTAINER} 2>&1 | grep "qemu cmd list:" | tail -1 | \
    sed "s/.*qemu cmd list: //" | \
    python3 -c "import sys, ast, json; print(json.dumps(ast.literal_eval(sys.stdin.read()), indent=2))"

echo ""
echo "=== Network Interfaces in Container ==="
docker exec ${CONTAINER} ip link show | grep -E "^[0-9]+:|eth|tap"

echo ""
echo "=== TC Filter Rules (tc-mirred) ==="
docker exec ${CONTAINER} tc filter show dev eth1 ingress 2>/dev/null || echo "No eth1 or no tc rules"
