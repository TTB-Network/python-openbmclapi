FROM python:3.12-alpine

LABEL org.opencontainers.image.url https://python-openbmclapi.ttb-network.top/
LABEL org.opencontainers.image.source https://github.com/TTB-Network/python-openbmclapi
LABEL org.opencontainers.image.vendor TTB-Network
LABEL org.opencontainers.image.licenses MIT
LABEL org.opencontainers.image.title python-openbmclapi

ENV timezone=Asia/Shanghai

WORKDIR /opt/python-openbmclapi
ADD . .

RUN pip install -r requirements.txt

EXPOSE 6543
CMD ["python", "./main.py"]