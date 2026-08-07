# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

vrnetlab packages network operating system virtual machines (VMs) as Docker containers, enabling their use
with containerlab for network topology simulation and testing. This is a fork of plajjan/vrnetlab that adds
container-native networking through tc-mirred redirects, eliminating the need for the vr-xcon VM.

Key concepts:
- Each vendor/platform (e.g., cisco/xrv9k, nokia/sros) has its own subdirectory with a build system
- VMs run inside containers via QEMU/KVM
- Container interfaces (eth1+) are stitched to VM TAP interfaces using tc-mirred for transparent L2 pipes
- The common/vrnetlab.py module provides the core VM lifecycle management
- Each platform has a launch.py that inherits from the VM class in common/vrnetlab.py

## Repository Structure

```
vrnetlab/
├── common/                        # Core vrnetlab Python modules
│   ├── vrnetlab.py               # Base VM class with QEMU management
│   └── healthcheck.py            # Container healthcheck script
├── {vendor}/{platform}/          # Per-platform directories (e.g., cisco/xrv9k)
│   ├── Makefile                  # Build configuration (sets VENDOR, NAME, IMAGE_FORMAT, VERSION regex)
│   ├── README.md                 # Platform-specific documentation
│   └── docker/
│       ├── Dockerfile            # Container image definition
│       └── launch.py             # Platform-specific VM implementation (inherits from vrnetlab.VM)
├── makefile.include              # Common build logic included by all platform Makefiles
├── makefile-install.include      # Optional install mode logic
├── makefile-sanity.include       # Build sanity checks
├── vrnetlab-base.dockerfile      # Base container image with QEMU and dependencies
└── build-base-image.sh           # Script to build the base image
```

## Building Images

Building a vendor image:

1. Place the vendor VM image file (qcow2, vmdk, iso, etc.) in the appropriate vendor/platform directory
2. Run `make` or `make docker-image` from that directory
3. The Makefile extracts the version from the filename using VERSION regex and tags the image accordingly
4. Built image name format: `vrnetlab/{vendor}_{platform}:{version}`

Example for Cisco XRv9k:
```bash
cd cisco/xrv9k
# Place xrv9k-fullk9-x-7.11.1.qcow2 in this directory
make docker-image
# Produces: vrnetlab/vr-xrv9k:7.11.1
```

The build process:
- Copies the VM image to docker/ subdirectory
- Copies common/vrnetlab.py and common/healthcheck.py to docker/
- Runs docker build with IMAGE and VERSION build args
- Cleans up copied files after build

Install mode (optional, platform-specific):
```bash
make docker-image INSTALL=true
```
This pre-boots the VM during image build to complete first-time setup, reducing subsequent boot times.

Building the base image (rarely needed):
```bash
./build-base-image.sh 0.1.0
```

## Connection Modes

vrnetlab supports different ways to connect container interfaces to VM interfaces, configured via the
`--connection-mode` flag in launch.py:

- `tc` (tc-mirred): Default for containerlab. Uses tc redirect for transparent L2 pipe between container
  eth interfaces and VM TAP interfaces. Best performance and LACP support.
- `bridge`: Linux bridge connecting eth and tap interfaces. No STP support.
- `ovs-bridge`: Open vSwitch bridge. Better than Linux bridge for some use cases.
- `macvtap`: Requires mounting /dev, less commonly used.

The connection mode affects how gen_nics() in vrnetlab.py creates network device arguments for QEMU.

## Management Interfaces

Two modes:
- **Pass-through** (CLAB_MGMT_PASSTHROUGH=true): VM uses assigned management IP directly, management
  traffic passes through transparently
- **Host-forwarded** (default): VM uses 10.0.0.15/24, outgoing traffic NATed to container management IP,
  specific ports forwarded

## Common Development Tasks

Running a built image with containerlab:
```yaml
# topology.clab.yaml
name: test-lab
topology:
  nodes:
    r1:
      kind: vr-xrv9k
      image: vrnetlab/vr-xrv9k:7.11.1
```

Testing version extraction regex:
```bash
cd cisco/xrv9k
make IMAGE=xrv9k-fullk9-x-7.11.1.qcow2 version-test
```

Accessing VM serial console (from host):
```bash
docker exec -it clab-test-lab-r1 telnet localhost 5000
```

QEMU monitor access:
```bash
docker exec -it clab-test-lab-r1 telnet localhost 4000
```

## Platform-Specific Implementation

Each platform's launch.py typically:
1. Imports vrnetlab module
2. Defines a VM subclass (e.g., XRv9k_vm(vrnetlab.VM))
3. Customizes QEMU arguments in __init__ (disk type, serial ports, machine type, CPU, etc.)
4. Overrides methods like bootstrap_spin() for platform-specific boot logic and configuration
5. Implements bootstrap_config() to generate initial configuration
6. Defines main() to parse args and instantiate the VM

Key methods to override:
- `__init__()`: Set platform-specific QEMU args, NIC counts, resources
- `bootstrap_spin()`: Wait for boot, detect readiness, apply initial config
- `bootstrap_config()`: Generate startup configuration
- `gen_mgmt()`: Customize management interface setup (if needed)

## Environment Variables

Common variables for all platforms:
- `CONNECTION_MODE`: Network connection mode (tc, bridge, ovs-bridge, macvtap)
- `VCPU`: Number of virtual CPUs
- `RAM`: Memory in MB
- `BOOT_DELAY`: Delay in seconds before starting VM
- `CLAB_MGMT_PASSTHROUGH`: Enable pass-through management (true/false)
- `RESTORE_SNAPSHOT`: Restore from snapshot file (1 to enable)

## Snapshotting

Create a snapshot:
```bash
docker exec <container> touch /snapshot-save
docker cp <container>:/snapshot-output.tar ./snapshot.tar
```

Restore from snapshot:
```bash
docker run -e RESTORE_SNAPSHOT=1 -v $(pwd)/snapshot.tar:/snapshot.tar:ro vrnetlab/{image}
```

## Resetting VMs

Force reset VMs without recreating the container:
```bash
docker exec <container> touch /reset                    # Reset all VMs
docker exec <container> sh -c 'echo "0" > /reset'       # Reset VM 0
docker exec <container> sh -c 'echo "1,2" > /reset'     # Reset VMs 1 and 2
```

## Python Environment

The project uses uv for Python dependency management:
- Dependencies defined in pyproject.toml and uv.lock
- Base image runs scripts with `uv run /launch.py`
- For local development, add common/ to Python path (see dev-notes.md)

VSCode/Pylance configuration:
```json
{
    "python.analysis.extraPaths": ["common"]
}
```

## Important Files

- `common/vrnetlab.py`: Core VM class (~1400 lines). Handles QEMU lifecycle, network setup, serial console
  interaction, boot detection, configuration injection, snapshot/restore.
- `vrnetlab-base.dockerfile`: Base Debian bookworm-slim image with QEMU, bridge-utils, iproute2, socat, etc.
- Per-platform `docker/launch.py`: Entry point for each platform, customizes VM behavior.
- Per-platform `Makefile`: Defines VENDOR, NAME, IMAGE_FORMAT, IMAGE_GLOB, VERSION regex.

## Special Cases

### Baremetal VM
The baremetal/ directory provides a generic QEMU VM container for custom OS installation:
- Creates empty disk on startup
- No pre-installed OS
- Full control over QEMU args via QEMU_ARGS env var
- Per-interface NIC types via QEMU_NIC_TYPES
- Useful for testing custom configurations or OSes not officially supported

### XRv9k Install Mode
XRv9k has a 20+ minute first boot. Enable INSTALL=true to pre-boot during image build, but note
this bakes in certain values and may cause issues in some scenarios.

## Architecture Notes

The VM class in vrnetlab.py manages:
- Disk overlay creation (qemu-img create with backing file)
- QEMU argument construction (machine type, CPU, memory, NICs, serial ports)
- NIC generation based on connection mode
- Serial console communication (telnetlib or scrapli)
- Bootstrap process (wait for boot, apply config)
- Healthcheck coordination
- Snapshot save/restore

Platform implementations customize this base by extending the VM class and overriding methods as needed.
