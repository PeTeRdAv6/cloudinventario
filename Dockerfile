FROM python:3

COPY [ "src", "/app" ]
COPY [ "cloudinventario", "/app" ]
COPY [ "requirements.txt", "/app" ]

WORKDIR "/app"
RUN [ "pip", "install", "-r", "requirements.txt" ]

VOLUME /conf /conf
VOLUME /data /data

# By default we wait for docker exec
CMD [ "tail", "-f", "/dev/null" ]
