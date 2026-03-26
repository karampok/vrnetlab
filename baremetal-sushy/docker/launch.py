#!/usr/bin/env python3

import os
import sys
import subprocess
import time
import logging
import signal


def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def main():
    logger = setup_logging()

    # Start libvirt daemons
    logger.info("Starting virtlogd...")
    subprocess.Popen(['virtlogd', '--daemon'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logger.info("Starting libvirtd...")
    subprocess.run(['libvirtd', '--daemon'], check=True)
    time.sleep(3)
    subprocess.run(['virsh', 'list', '--all'], check=True, capture_output=True)
    logger.info("libvirtd ready")

    # Create disk
    disk_path = '/var/lib/libvirt/images/vm1.qcow2'
    disk_size = os.environ.get('QEMU_DISK_SIZE', '50G')
    logger.info(f"Creating disk {disk_path} size={disk_size}")
    subprocess.run(['qemu-img', 'create', '-f', 'qcow2', disk_path, disk_size], check=True)

    # Create and start VM
    memory = os.environ.get('QEMU_MEMORY', '8192')
    vcpus = os.environ.get('VCPU', '4')
    os_variant = os.environ.get('QEMU_OS_VARIANT', 'detect=on,require=off')

    cmd = [
        'virt-install',
        '--connect', 'qemu:///system',
        '--name', 'vm1',
        '--memory', memory,
        '--vcpus', vcpus,
        '--disk', f'path={disk_path},format=qcow2',
        '--os-variant', os_variant,
        '--network', 'model=virtio,type=ethernet,xpath0.create=./script,xpath1.set=./script/@path,xpath1.value=/etc/tc-tap-eth10-ifup',
        '--graphics', 'vnc,port=5900,listen=0.0.0.0',
        '--noautoconsole',
        '--import',
    ]

    if os.path.isdir('/cdrom'):
        isos = [f for f in os.listdir('/cdrom') if f.endswith('.iso')]
        if isos:
            cmd += ['--cdrom', os.path.join('/cdrom', isos[0])]
            cmd.remove('--import')

    # Write tc-mirred ifup script for eth10 <-> tap
    with open('/etc/tc-tap-eth10-ifup', 'w') as f:
        f.write("""#!/bin/bash
TAP=$1
ip link set eth10 up
ip link set $TAP up
tc qdisc add dev eth10 clsact
tc filter add dev eth10 ingress flower action mirred egress redirect dev $TAP
tc qdisc add dev $TAP clsact
tc filter add dev $TAP ingress flower action mirred egress redirect dev eth10
""")
    os.chmod('/etc/tc-tap-eth10-ifup', 0o755)

    logger.info("Running virt-install...")
    subprocess.run(cmd, check=True)
    logger.info("VM created")
    logger.info("remote-viewer vnc://172.20.0.2:5900")

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
