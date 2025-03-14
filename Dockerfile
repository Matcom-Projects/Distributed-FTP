# Use official Python image as a base
FROM base-image:latest

# Set the working directory
WORKDIR /app

# Copy files into the container
COPY server.py /app/
COPY kademlia /app/kademlia


# Expose ports for the nodes
EXPOSE 8468-8499

# Command to run the node (arguments are provided at runtime)
ENTRYPOINT ["python", "server.py"]