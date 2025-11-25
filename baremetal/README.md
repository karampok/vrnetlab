# Baremetal QEMU VM for vrnetlab

Generic QEMU VM container that boots from an empty disk, allowing manual OS installation via serial console.

## Features

- Boot from empty disk (no pre-installed OS)
- Per-interface NIC types (virtio-net-pci, igb, e1000, etc.)
- Full QEMU customization via QEMU_ARGS environment variable
- No management interface (data plane only)
- Multi-interface networking via tc-mirred
- CentOS Stream 10 base with /usr/libexec/qemu-kvm

## Environment Variables

### QEMU_DISK_SIZE
Size of the empty base disk. Default: `10G`

Examples: `20G`, `50G`, `100G`

### QEMU_MEMORY
RAM in MB. Default: `2048`

Example: `4096`

### QEMU_NIC_TYPES
Comma-separated list of NIC types per interface. Must match number of interfaces.

Example: `virtio-net-pci,igb,e1000`

Supported types:
- `virtio-net-pci` (recommended, best performance)
- `igb` (Intel 82576 Gigabit)
- `e1000` (Intel PRO/1000)
- `e1000e` (Intel 82574L Gigabit)
- `rtl8139` (Realtek 8139)

### QEMU_NIC_TYPE
Single NIC type for all interfaces (fallback if QEMU_NIC_TYPES not set).

Default: `virtio-net-pci`

### QEMU_ARGS
Additional QEMU arguments (newline-separated).

Example:
```yaml
QEMU_ARGS: |
  -cpu host
  -smp 4
  -m 4096
  -machine q35
```

## Usage

### Build Image

```bash
cd baremetal
make docker-image
```

### Containerlab Example

```yaml
name: baremetal-test
topology:
  nodes:
    vm1:
      kind: generic_vm
      image: vrnetlab/baremetal:latest
      ports:
        - "5001:5000"  # Serial console
        - "4001:4000"  # QEMU monitor
      env:
        QEMU_DISK_SIZE: "20G"
        QEMU_MEMORY: "4096"
        QEMU_NIC_TYPES: "virtio-net-pci,igb"
        QEMU_ARGS: |
          -cpu host
          -smp 4
          -machine q35
    router:
      kind: linux
      image: alpine:latest
  links:
    - endpoints: ["vm1:eth1", "router:eth1"]
    - endpoints: ["vm1:eth2", "router:eth2"]
```

### Access Serial Console

```bash
telnet localhost 5001
```

### Access QEMU Monitor

```bash
telnet localhost 4001
```

## Installing an OS

1. Deploy the topology with containerlab
2. Connect to serial console: `telnet localhost 5001`
3. Mount ISO via QEMU monitor or use network boot (PXE)
4. Follow OS installation steps in serial console
5. Restart container to boot from installed OS

## Known Limitations

- No snapshot support (changes persist across container restarts)
- No management interface (serial console only)
- Requires KVM support for acceptable performance
- Initial boot timeout is 60 seconds if VM produces no console output

## Troubleshooting

### VM doesn't start

Check container logs: `docker logs <container-name>`

Verify KVM is available: `ls -la /dev/kvm`

### NICs not appearing

Check NIC type count matches number of interfaces:
```yaml
env:
  QEMU_NIC_TYPES: "virtio-net-pci,igb"  # For 2 interfaces
```

Use containerlab with `--nics` or ensure links are defined.

### Slow performance

Enable KVM: Ensure `/dev/kvm` is accessible in container (usually requires privileged mode or device mapping).

Check QEMU args include `-cpu host` for better performance.

### Console shows nothing

Wait up to 60 seconds - VM is marked running after timeout even without console output.

If using custom QEMU_ARGS, ensure serial console is not overridden.

## Architecture Notes

This implementation:
- Extends `vrnetlab.VM` parent class
- Replaces parent's qemu_args to use /usr/libexec/qemu-kvm
- Loses snapshot support (intentional for persistent OS installation)
- Creates empty base disk on first run, then uses overlay disks
- Supports tc-mirred connection mode for transparent L2 networking

## Commit History

The implementation consists of atomic commits:
1. Fix logger initialization bug
2. Add Dockerfile dependencies and permissions
3. Improve disk path handling with instance variable
4. Make KVM detection conditional
