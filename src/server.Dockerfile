FROM python:alpine

# Copy the ftp_root folder into the container
COPY ftp_root /ftp_root
WORKDIR /app

COPY networking/routing.sh /app
COPY src/server.py /app


RUN chmod +x /app/routing.sh



ENTRYPOINT [ "/app/routing.sh" ]