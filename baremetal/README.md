# Baremetal VM with Sushy Redfish Emulator

Generic QEMU VM container managed by libvirt with Sushy-tools Redfish BMC emulation.

## Features

- libvirt-managed QEMU/KVM virtual machines
- Sushy-tools Redfish API for BMC emulation (compatible with OpenShift bare metal installer)
- Serial console access via telnet
- VNC graphics support
- CD-ROM ISO mounting
- Configurable disk size, memory, and vCPUs

## Architecture

```
Container
├── libvirtd (manages QEMU VM)
├── QEMU VM (created via virt-install)
└── sushy-emulator (Redfish API on port 8000)
```

Unlike the regular `baremetal` container which runs QEMU directly, this uses:
- **libvirt** to manage the VM lifecycle via virt-install
- **sushy-emulator** to expose a Redfish BMC API for tools like OpenShift that expect BMC control

## Environment Variables

### QEMU_DISK_SIZE
Size of the VM disk. Default: `10G`

Examples: `20G`, `50G`, `100G`

### QEMU_MEMORY
RAM in MB. Default: `2048`

Example: `4096`, `8192`

### VCPU
Number of virtual CPUs. Default: `1`

Example: `2`, `4`

## Usage

### Build Image

```bash
cd baremetal-sushy
make docker-image
```

### Containerlab Example

```yaml
name: sushy-test
topology:
  nodes:
    bmc:
      kind: linux
      image: vrnetlab/baremetal-sushy:latest
      binds:
        - /path/to/installer.iso:/cdrom/installer.iso:ro
      ports:
        - "5000:5000"  # Serial console
        - "8000:8000"  # Redfish API
        - "5900:5900"  # VNC
      env:
        QEMU_DISK_SIZE: "50G"
        QEMU_MEMORY: "8192"
        VCPU: "4"
```

### Access Serial Console

```bash
telnet localhost 5000
```

### Access VNC Console

```bash
remote-viewer vnc://localhost:5900
```

### Access Redfish API

```bash
curl http://localhost:8000/redfish/v1/
curl http://localhost:8000/redfish/v1/Systems
curl http://localhost:8000/redfish/v1/Systems/vm1
```

### Control VM via Redfish

```bash
# Power on
curl -X POST http://localhost:8000/redfish/v1/Systems/vm1/Actions/ComputerSystem.Reset \
  -H "Content-Type: application/json" \
  -d '{"ResetType": "On"}'

# Power off
curl -X POST http://localhost:8000/redfish/v1/Systems/vm1/Actions/ComputerSystem.Reset \
  -H "Content-Type: application/json" \
  -d '{"ResetType": "ForceOff"}'

# Set boot device to CD-ROM
curl -X PATCH http://localhost:8000/redfish/v1/Systems/vm1 \
  -H "Content-Type: application/json" \
  -d '{"Boot": {"BootSourceOverrideTarget": "Cd"}}'
```

## OpenShift Integration

This container is designed to work with OpenShift's bare metal installer:

```yaml
# install-config.yaml
platform:
  baremetal:
    hosts:
      - name: master-0
        role: master
        bmc:
          address: redfish://containerlab-host:8000/redfish/v1/Systems/vm1
          disableCertificateVerification: true
        bootMACAddress: "52:54:00:xx:xx:xx"
```

The OpenShift installer can control the VM's power state and boot order via the Redfish API.

## Differences from Regular baremetal

| Feature | baremetal | baremetal-sushy |
|---------|-----------|-----------------|
| QEMU management | Direct subprocess | libvirt domains |
| BMC emulation | None | Sushy Redfish API |
| Networking | tc-mirred | libvirt default |
| Use case | General containerlab | OpenShift bare metal |

## Known Limitations

- No tc-mirred networking support (uses libvirt default networking)
- Requires privileged mode for KVM access
- libvirt networking may conflict with containerlab networking
- Designed primarily for OpenShift bare metal installation workflows

## Troubleshooting

### Check libvirt status

```bash
docker exec <container> virsh list --all
docker exec <container> virsh dominfo vm1
```

### Check sushy-emulator logs

```bash
docker logs <container>
```

### Verify Redfish API

```bash
curl http://localhost:8000/redfish/v1/Systems/vm1 | jq
```
