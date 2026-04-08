#!/usr/bin/env python3

import glob
import hashlib
import json
import os
import sys
import subprocess
import time
import logging
import signal


def mac_from_uuid(uuid_str, index):
    h = hashlib.md5(f"{uuid_str}-{index}".encode()).digest()
    mac = bytearray(h[:6])
    mac[0] = (mac[0] | 0x02) & 0xfe  # locally administered, unicast
    return ':'.join(f'{b:02x}' for b in mac)


def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def main():
    logger = setup_logging()

    logger.info("Starting virtlogd...")
    subprocess.Popen(['virtlogd', '--daemon'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logger.info("Starting libvirtd...")
    subprocess.run(['libvirtd', '--daemon'], check=True)
    time.sleep(3)
    subprocess.run(['virsh', 'list', '--all'], check=True, capture_output=True)
    logger.info("libvirtd ready")

    disk_path = '/var/lib/libvirt/images/vm1.qcow2'
    disk_size = os.environ.get('QEMU_DISK_SIZE', '50G')
    logger.info(f"Creating disk {disk_path} size={disk_size}")
    subprocess.run(['qemu-img', 'create', '-f', 'qcow2', disk_path, disk_size], check=True)

    machine = os.environ.get('QEMU_MACHINE', 'q35')
    memory = os.environ.get('QEMU_MEMORY', '8192')
    os_variant = os.environ.get('QEMU_OS_VARIANT', 'rhel9.1')
    uuid = os.environ.get('VM_UUID')
    vcpus = os.environ.get('VCPU', '4')

    cmd = [
        'virt-install',
        '--connect', 'qemu:///system',
        '--name', 'vm1',
        '--machine', machine,
        '--memory', memory,
        '--vcpus', vcpus,
        '--disk', f'path={disk_path},format=qcow2',
        '--os-variant', os_variant,
        '--boot', 'firmware=efi,firmware.feature0.name=secure-boot,firmware.feature0.enabled=no',
        '--graphics', 'vnc,port=5900,listen=0.0.0.0',
        '--noautoconsole',
        '--import',
    ]

    if uuid:
        cmd += ['--uuid', uuid]
        logger.info(f"Using VM UUID: {uuid}")

    has_iso = False
    if os.path.isdir('/cdrom'):
        isos = [f for f in os.listdir('/cdrom') if f.endswith('.iso')]
        if isos:
            has_iso = True
            cmd += ['--cdrom', os.path.join('/cdrom', isos[0])]
            cmd.remove('--import')

    eth_ifaces = sorted(
        (os.path.basename(p) for p in glob.glob('/sys/class/net/eth*')),
        key=lambda x: int(x[3:])
    )
    logger.info(f"Detected eth interfaces: {eth_ifaces}")
    for idx, iface in enumerate(eth_ifaces):
        script_path = f'/etc/tc-tap-{iface}-ifup'
        with open(script_path, 'w') as f:
            f.write(f"""#!/bin/bash
TAP=$1
ip link set {iface} up
ip link set $TAP up
tc qdisc del dev {iface} clsact 2>/dev/null || true
tc qdisc del dev $TAP clsact 2>/dev/null || true
tc qdisc add dev {iface} clsact
tc filter add dev {iface} ingress flower action mirred egress redirect dev $TAP
tc qdisc add dev $TAP clsact
tc filter add dev $TAP ingress flower action mirred egress redirect dev {iface}
""")
        os.chmod(script_path, 0o755)
        mac = mac_from_uuid(uuid, idx) if uuid else None
        mac_arg = f',mac={mac}' if mac else ''
        cmd += ['--network', f'model=virtio,type=ethernet{mac_arg},xpath0.create=./script,xpath1.set=./script/@path,xpath1.value={script_path}']
        logger.info(f"Added network for {iface} mac={mac} via {script_path}")

    logger.info("Running virt-install...")
    subprocess.run(cmd, check=True)
    logger.info("VM created")
    if not has_iso:
        subprocess.run(['virsh', 'destroy', 'vm1'], check=False)
        logger.info("No ISO mounted, VM powered off — waiting for BMC to provision")
    bmc_ip = '<bmc>'
    try:
        data = json.loads(subprocess.run(
            ['ip', '--json', 'a', 's', 'dev', 'bmc'], capture_output=True, text=True
        ).stdout)
        for addr in data[0].get('addr_info', []):
            if addr['family'] == 'inet':
                bmc_ip = addr['local']
                break
    except Exception:
        pass
    domain_uuid = uuid or subprocess.run(
        ['virsh', 'domuuid', 'vm1'], capture_output=True, text=True
    ).stdout.strip()
    logger.info(f"remote-viewer vnc://{bmc_ip}:5900")
    logger.info(f"curl http://{bmc_ip}:8000/redfish/v1/Systems/{domain_uuid}")
    logger.info(
        f"bmcs-clab.yaml:\n"
        f"- user: \"admin\"\n"
        f"  password: \"dummy\"\n"
        f"  address: \"redfish-virtualmedia+http://{bmc_ip}:8000/redfish/v1/Systems/{domain_uuid}\""
    )

    def signal_handler(signum, frame):
        result = subprocess.run(['virsh', 'list', '--name'], capture_output=True, text=True)
        for vm_name in result.stdout.strip().split('\n'):
            if vm_name:
                subprocess.run(['virsh', 'destroy', vm_name], check=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    while True:
        time.sleep(5)


if __name__ == '__main__':
    main()
