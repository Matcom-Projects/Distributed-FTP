FROM base-image:latest

WORKDIR /app

# Install FTP client
RUN apt-get update && apt-get install -y ftp && apt-get install -y iproute2

COPY routing_client.sh /app


RUN chmod +x /app/routing_client.sh

ENTRYPOINT [ "/bin/sh", "-c","/app/routing_client.sh" ]