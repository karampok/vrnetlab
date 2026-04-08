FROM public.ecr.aws/docker/library/debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive

# Install libvirt, QEMU/KVM, virt-install, and networking tools
RUN apt-get update -qy && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    libvirt-daemon-system \
    libvirt-clients \
    libvirt-dev \
    virtinst \
    qemu-kvm \
    qemu-utils \
    ovmf \
    iproute2 \
    bridge-utils \
    socat \
    telnet \
    iputils-ping \
    curl \
    tini \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Create configuration directories and runtime dirs
RUN mkdir -p /etc/libvirt/storage/autostart /var/run/libvirt /run/libvirt /var/lib/libvirt/images /var/lib/libvirt/default /var/log/libvirt/qemu

COPY default-pool.xml /etc/libvirt/storage/default.xml
RUN ln -s /etc/libvirt/storage/default.xml /etc/libvirt/storage/autostart/default.xml

COPY libvirtd.conf /etc/libvirt/libvirtd.conf
COPY qemu.conf /etc/libvirt/qemu.conf
COPY launch.py /launch.py
RUN chmod +x /launch.py

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/usr/bin/tini", "--", "/launch.py"]
