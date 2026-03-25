FROM public.ecr.aws/docker/library/debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive
ARG SUSHY_TOOLS_VERSION="2.2.0"

COPY --from=ghcr.io/astral-sh/uv:0.5.18 /uv /uvx /bin/

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
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install sushy-tools and libvirt-python using pip
RUN pip3 install --break-system-packages --no-cache-dir \
    sushy-tools==${SUSHY_TOOLS_VERSION} \
    libvirt-python

# Create configuration directories and runtime dirs
RUN mkdir -p /etc/sushy /etc/libvirt /var/run/libvirt /run/libvirt /var/lib/libvirt/images /var/log/libvirt/qemu

# Copy launch script, healthcheck, and configuration
COPY launch.py /launch.py
RUN chmod +x /launch.py
COPY healthcheck.py /healthcheck.py
COPY sushy-emulator.conf /etc/sushy/sushy-emulator.conf
COPY libvirtd.conf /etc/libvirt/libvirtd.conf
COPY qemu.conf /etc/libvirt/qemu.conf

ENV PYTHONUNBUFFERED=1

EXPOSE 8000 5900
HEALTHCHECK CMD ["/healthcheck.py"]

ENTRYPOINT ["/usr/bin/tini", "--", "/launch.py"]
