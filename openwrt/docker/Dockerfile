FROM ghcr.io/srl-labs/vrnetlab-base:0.2.1
LABEL maintainer="Andreas Cymbal takalele@konnex.me"


RUN uv add click

ARG IMAGE
COPY $IMAGE* /
COPY *.py /
