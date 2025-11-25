FROM public.ecr.aws/docker/library/debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qy \
   && apt-get install -y --no-install-recommends \
   bridge-utils \
   iproute2 \
   socat \
   qemu-kvm \
   qemu-utils \
   tcpdump \
   ssh \
   inetutils-ping \
   dnsutils \
   iptables \
   nftables \
   telnet \
   netcat-openbsd \
   sshpass \
   python3 \
   python3-pip \
   && rm -rf /var/lib/apt/lists/*

# Install Python dependencies required by vrnetlab.py
RUN pip3 install --break-system-packages --no-cache-dir scrapli passlib pyyaml

COPY *.py /

EXPOSE 22 5000 10000-10099
HEALTHCHECK CMD ["/healthcheck.py"]
ENTRYPOINT ["/launch.py"]
