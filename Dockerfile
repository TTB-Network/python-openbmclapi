FROM python:3.12

LABEL org.opencontainers.image.url https://home.ttb-network.top/
LABEL org.opencontainers.image.source https://github.com/TTB-Network/python-openbmclapi
LABEL org.opencontainers.image.vendor TTB-Network
LABEL org.opencontainers.image.licenses MIT
LABEL org.opencontainers.image.title python-openbmclapi

WORKDIR /opt/python-openbmclapi
ADD . .

RUN pip install --user pipx
RUN pipx install poetry
RUN pipx ensurepath
RUN poetry install
RUN poetry shell
ENV port=80
EXPOSE $port
CMD ["python", "./main.py"]
