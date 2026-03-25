#!/usr/bin/env python3

import subprocess
import sys
import urllib.request

def check_libvirt():
    """Check if libvirtd is running"""
    try:
        result = subprocess.run(
            ['virsh', 'list', '--all'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

def check_sushy():
    """Check if sushy-emulator is responding"""
    try:
        response = urllib.request.urlopen('http://localhost:8000/redfish/v1/', timeout=5)
        return response.status == 200
    except Exception:
        return False

def main():
    if not check_libvirt():
        print("libvirt not running")
        sys.exit(1)

    if not check_sushy():
        print("sushy-emulator not responding")
        sys.exit(1)

    print("healthy")
    sys.exit(0)

if __name__ == '__main__':
    main()
