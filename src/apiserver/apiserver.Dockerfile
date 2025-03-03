FROM python:alpine

# Copy the ftp_root folder into the container
COPY src/ftp_root /app/ftp_root
WORKDIR /app

COPY src/router/routing.sh /app
COPY src/apiserver/apiserver.py /app
COPY src/apiserver/filesystem.py /app
COPY src/apiserver/lock.json /app
COPY src/apiserver/distributed_node.py /app

RUN chmod +x /app/routing.sh



ENTRYPOINT [ "/app/routing.sh" ]