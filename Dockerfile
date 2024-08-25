FROM python:3.12

LABEL org.opencontainers.image.url https://home.ttb-network.top/
LABEL org.opencontainers.image.source https://github.com/TTB-Network/python-openbmclapi
LABEL org.opencontainers.image.vendor TTB-Network
LABEL org.opencontainers.image.licenses MIT
LABEL org.opencontainers.image.title python-openbmclapi

WORKDIR /opt/python-openbmclapi
ADD . .

RUN pip install -r requirements.txt
ENV cluster.port=8080
EXPOSE $cluster.port
CMD ["python", "./main.py"]
