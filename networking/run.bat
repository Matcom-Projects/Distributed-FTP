docker run -d --rm --name chord1 -e PYTHONUNBUFFERED=1 --cap-add NET_ADMIN --network clients chord
docker run -d --rm --name chord2 -e PYTHONUNBUFFERED=1 --cap-add NET_ADMIN --network clients chord "10.0.10.2"

docker run -d --rm --name chord3 -e PYTHONUNBUFFERED=1 --cap-add NET_ADMIN --network servers chord "10.0.10.3"