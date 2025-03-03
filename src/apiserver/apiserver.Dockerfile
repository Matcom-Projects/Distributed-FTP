FROM python:alpine

# Copy the ftp_root folder into the container
COPY src/ftp_root /app/ftp_root
WORKDIR /app

COPY src/networking/routing.sh /app
COPY src/apiserver/apiserver.py /app
COPY src/apiserver/filesystem.py /app


RUN chmod +x /app/routing.sh



ENTRYPOINT [ "/app/routing.sh" ]