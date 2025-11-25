#!/usr/bin/env python3

import datetime
import logging
import os
import re
import signal
import sys
import time

import vrnetlab

# Module-level logger for use before super().__init__()
logger = logging.getLogger(__name__)


def handle_SIGCHLD(signal, frame):
    os.waitpid(-1, os.WNOHANG)


def handle_SIGTERM(signal, frame):
    sys.exit(0)


signal.signal(signal.SIGINT, handle_SIGTERM)
signal.signal(signal.SIGTERM, handle_SIGTERM)
signal.signal(signal.SIGCHLD, handle_SIGCHLD)

TRACE_LEVEL_NUM = 9
logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")


def trace(self, message, *args, **kws):
    if self.isEnabledFor(TRACE_LEVEL_NUM):
        self._log(TRACE_LEVEL_NUM, message, args, **kws)


logging.Logger.trace = trace


class BaremetalVM(vrnetlab.VM):
    def __init__(self, hostname, username, password, nics, conn_mode):
        # Get disk size from environment or use default
        disk_size = os.getenv("QEMU_DISK_SIZE", "10G")
        disk_image = "/baremetal-disk.qcow2"

        # Validate disk size format (basic check)
        if not disk_size[-1] in ['K', 'M', 'G', 'T']:
            logger.warning(f"Invalid QEMU_DISK_SIZE format: {disk_size}, using default 10G")
            disk_size = "10G"

        # Create base disk if it doesn't exist (using module-level logger)
        if not os.path.exists(disk_image):
            logger.info(f"Creating empty disk: {disk_image} ({disk_size})")
            vrnetlab.run_command(
                ["qemu-img", "create", "-f", "qcow2", disk_image, disk_size]
            )

        # Get memory from environment or use default
        ram = int(os.getenv("QEMU_MEMORY", "2048"))

        # Call parent constructor (this creates self.logger)
        super(BaremetalVM, self).__init__(
            username, password, disk_image=disk_image, ram=ram
        )

        # Store overlay disk path for safer access in replace_qemu_args_with_custom
        # Parent creates overlay with pattern: /baremetal-disk.qcow2 -> /baremetal-disk-overlay.qcow2
        self.overlay_disk_image = re.sub(r"(\.[^.]+$)", r"-overlay\1", disk_image)
        self.logger.debug(f"Overlay disk path: {self.overlay_disk_image}")

        # Default NIC type for management interface
        self.nic_type = "virtio-net-pci"
        self.num_nics = nics
        self.hostname = hostname
        self.conn_mode = conn_mode

        # Parse per-interface NIC types from environment
        # Format: QEMU_NIC_TYPES="virtio-net-pci,virtio-net-pci,igb,igb"
        nic_types_str = os.getenv("QEMU_NIC_TYPES", "")
        if nic_types_str:
            self.nic_types = nic_types_str.split(",")
            # Warn if count doesn't match num_nics
            if len(self.nic_types) != self.num_nics:
                self.logger.warning(
                    f"QEMU_NIC_TYPES count ({len(self.nic_types)}) doesn't match "
                    f"--nics ({self.num_nics}). Missing NICs will use default type."
                )
        else:
            # Fallback to single type for all interfaces
            default_type = os.getenv("QEMU_NIC_TYPE", "virtio-net-pci")
            self.nic_types = [default_type] * self.num_nics

        self.replace_qemu_args_with_custom()

        # Fix QEMU args that are incorrectly combined (parent bug + QEMU_ARGS parsing)
        # Arguments like "-chardev socket,..." should be ["-chardev", "socket,..."]
        # Arguments like "-cdrom /path" should be ["-cdrom", "/path"]
        # This must happen AFTER replace_qemu_args_with_custom() to catch QEMU_ARGS too
        fixed_args = []
        for arg in self.qemu_args:
            # Handle options that should be split on first space
            if " " in arg and arg.startswith("-"):
                parts = arg.split(" ", 1)
                fixed_args.extend(parts)
            else:
                fixed_args.append(arg)
        self.qemu_args = fixed_args

        # Log QEMU version for debugging
        import subprocess
        try:
            result = subprocess.run(["qemu-system-x86_64", "--version"],
                                  capture_output=True, text=True, timeout=5)
            self.logger.info(f"QEMU version: {result.stdout.strip()}")
        except Exception as e:
            self.logger.warning(f"Could not get QEMU version: {e}")

    def replace_qemu_args_with_custom(self):
        """Extend parent's qemu_args with custom QEMU_ARGS"""
        extra_args = os.getenv("QEMU_ARGS", "")

        # DON'T replace - just extend parent's args with custom ones
        if extra_args:
            args_list = [arg.strip() for arg in extra_args.split('\n') if arg.strip()]
            self.logger.info(f"Appending custom QEMU args: {args_list}")
            self.qemu_args.extend(args_list)

        self.logger.debug(f"Final QEMU args: {' '.join(self.qemu_args)}")

    def gen_mgmt(self):
        """Override parent to disable management interface"""
        self.logger.info("Management interface disabled for baremetal VM")
        return []

    def gen_nics(self):
        """Override parent to disable auto NIC generation - use QEMU_ARGS instead"""
        # Create tc-tap-ifup script in case QEMU_ARGS references it
        if self.conn_mode == "tc":
            self.create_tc_tap_ifup()

        self.logger.info("Auto NIC generation disabled - using manual QEMU_ARGS")
        return []

    def gen_nics_original(self):
        """Override parent gen_nics to support per-interface NIC types"""
        import math

        self.nic_provision_delay()
        res = []

        if self.conn_mode == "tc":
            self.create_tc_tap_ifup()

        start_eth = self.start_nic_eth_idx
        end_eth = self.start_nic_eth_idx + self.num_nics
        pci_bus_ctr = 0

        self.logger.info(f"Network setup: conn_mode={self.conn_mode}, num_nics={self.num_nics}, start_eth={start_eth}")

        for i in range(start_eth, end_eth):
            pci_bus_ctr += 1
            x = pci_bus_ctr
            pci_bus = math.floor(x / self.nics_per_pci_bus) + 1
            addr = (x % self.nics_per_pci_bus) + 1

            # Check if container interface exists
            if not os.path.exists(f"/sys/class/net/{self.data_intf_prefix}{i}"):
                if i >= self.highest_provisioned_nic_num:
                    continue
                # Create dummy interface
                nic_type = self.nic_types[i - start_eth] if (i - start_eth) < len(self.nic_types) else "virtio-net-pci"
                res.extend([
                    "-device",
                    f"{nic_type},netdev=p{i:02d}"
                    + (f",bus=pci.{pci_bus},addr=0x{addr:x}" if self.provision_pci_bus else ""),
                    "-netdev",
                    f"socket,id=p{i:02d},listen=:{i + 10000:02d}",
                ])
                continue

            # Get MAC address
            intf_name = f"{self.data_intf_prefix}{i}"
            mac = self.get_intf_mac(intf_name)
            if not mac:
                mac = vrnetlab.gen_mac(i)

            # Get NIC type for this interface
            nic_type = self.nic_types[i - start_eth] if (i - start_eth) < len(self.nic_types) else "virtio-net-pci"

            self.logger.info(f"Interface {intf_name}: type={nic_type}, mac={mac}")

            res.append("-device")
            res.append(
                f"{nic_type},netdev=p{i:02d},mac={mac}"
                + (f",bus=pci.{pci_bus},addr=0x{addr:x}" if self.provision_pci_bus else "")
            )

            if self.conn_mode == "tc":
                res.append("-netdev")
                res.append(
                    f"tap,id=p{i:02d},ifname=tap{i},script=/etc/tc-tap-ifup,downscript=no"
                )

        return res

    def start(self):
        """Override parent start() to skip serial console connection"""
        # Call parent's start() up to the point where it connects to serial console
        # We'll replicate the necessary parts but skip the telnet connection

        self.logger.info("START ENVIRONMENT VARIABLES".center(60, "-"))
        for var, value in sorted(os.environ.items()):
            self.logger.info(f"{var}: {value}")
        self.logger.info("END ENVIRONMENT VARIABLES".center(60, "-"))

        self.logger.info(
            f"Launching {self.__class__.__name__} with {self.smp} SMP/VCPU and {self.ram} M of RAM"
        )

        mgmt_passthrough_coloured = vrnetlab.format_bool_color(
            self.mgmt_passthrough, "Enabled", "Disabled"
        )
        use_scrapli_coloured = vrnetlab.format_bool_color(
            self.use_scrapli, "Enabled", "Disabled"
        )

        self.logger.info(f"Scrapli: {use_scrapli_coloured}")
        self.logger.info(f"Transparent mgmt interface: {mgmt_passthrough_coloured}")

        self.start_time = datetime.datetime.now()

        cmd = list(self.qemu_args)

        # uuid
        if self.uuid:
            cmd.extend(["-uuid", self.uuid])

        # do we have a fake start date?
        if self.fake_start_date:
            cmd.extend(["-rtc", "base=" + self.fake_start_date])

        # smbios
        for smbios_line in self.smbios:
            quoted_smbios = '"' + smbios_line + '"'
            cmd.extend(["-smbios", quoted_smbios])

        # setup PCI buses - disabled for manual QEMU_ARGS mode
        # if self.provision_pci_bus:
        #     import math
        #     for i in range(1, math.ceil(self.num_nics / self.nics_per_pci_bus) + 1):
        #         cmd.extend(["-device", f"pci-bridge,chassis_nr={i},id=pci.{i}"])

        # generate mgmt NICs
        cmd.extend(self.gen_mgmt())
        # generate normal NICs
        cmd.extend(self.gen_nics())

        self.logger.debug(f"qemu cmd: {' '.join(cmd)}")
        self.logger.debug(f"qemu cmd list: {cmd}")

        import subprocess
        self.p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            outs, errs = self.p.communicate(timeout=2)
            self.logger.info("STDOUT: %s" % outs)
            self.logger.info("STDERR: %s" % errs)
        except:
            pass

        # Connect to QEMU monitor only (not serial console)
        import telnetlib
        for i in range(1, vrnetlab.MAX_RETRIES + 1):
            try:
                self.qm = telnetlib.Telnet("127.0.0.1", 4000 + self.num)
                break
            except:
                self.logger.error(
                    "Unable to connect to qemu monitor (port {}), retrying in a second (attempt {})".format(
                        4000 + self.num, i
                    )
                )
                time.sleep(1)
            if i == vrnetlab.MAX_RETRIES:
                raise Exception(
                    "Unable to connect to qemu monitor on port {}".format(
                        4000 + self.num
                    )
                )

        # Do NOT connect to serial console - leave it available for user access
        self.tn = None

        self.logger.info("Baremetal VM started. Serial console available on port 5000 for user access.")

    def bootstrap_spin(self):
        """Mark VM as running after timeout - no serial console interaction for baremetal"""
        # For baremetal VMs, we don't interact with the serial console during bootstrap
        # Users need exclusive access to the console for OS installation
        if self.spins > 30:
            # After 30 seconds, mark as running
            self.running = True
            startup_time = datetime.datetime.now() - self.start_time
            self.logger.info(f"VM marked as running after {startup_time}")
            return

        self.spins += 1


class Baremetal(vrnetlab.VR):
    def __init__(self, hostname, username, password, nics, conn_mode):
        super(Baremetal, self).__init__(username, password)
        self.vms = [BaremetalVM(hostname, username, password, nics, conn_mode)]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Baremetal VM launcher")
    parser.add_argument("--trace", action="store_true", help="Enable trace logging")
    parser.add_argument("--username", default="root", help="Username (not used)")
    parser.add_argument("--password", default="root", help="Password (not used)")
    parser.add_argument("--hostname", default="baremetal", help="Hostname (not used)")
    parser.add_argument("--nics", type=int, default=1, help="Number of data plane NICs (not used with manual QEMU_ARGS)")
    parser.add_argument("--connection-mode", default="tc", help="Connection mode")
    args = parser.parse_args()

    LOG_FORMAT = "%(asctime)s: %(module)-10s %(levelname)-8s %(message)s"
    logging.basicConfig(format=LOG_FORMAT)
    logger = logging.getLogger()

    logger.setLevel(logging.DEBUG)
    if args.trace:
        logger.setLevel(1)

    vr = Baremetal("baremetal", "root", "root", args.nics, args.connection_mode)
    vr.start()
