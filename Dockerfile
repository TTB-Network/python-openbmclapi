FROM python:3.12

LABEL org.opencontainers.image.url https://github.com/tianxiu2b2t/python-openbmclapi
LABEL org.opencontainers.image.source https://github.com/tianxiu2b2t/python-openbmclapi
LABEL org.opencontainers.image.vendor tianxiu2b2t
LABEL org.opencontainers.image.licenses MIT
LABEL org.opencontainers.image.title python-openbmclapi

WORKDIR /python-openbmclapi
ADD . .

RUN pip install -r requirements.txt --no-deps
VOLUME /python-openbmclapi/cache
ENV web_port=8080
EXPOSE $web_port
CMD ["python", "./container/main.py"]
