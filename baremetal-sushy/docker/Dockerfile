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
RUN mkdir -p /etc/libvirt /var/run/libvirt /run/libvirt /var/lib/libvirt/images /var/log/libvirt/qemu

# Copy launch script and configuration
COPY launch.py /launch.py
RUN chmod +x /launch.py
COPY libvirtd.conf /etc/libvirt/libvirtd.conf
COPY qemu.conf /etc/libvirt/qemu.conf

ENV PYTHONUNBUFFERED=1

EXPOSE 5900

ENTRYPOINT ["/usr/bin/tini", "--", "/launch.py"]
