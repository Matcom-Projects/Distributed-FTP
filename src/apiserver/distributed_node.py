import socket
import threading
import json
import time
import os
from collections import defaultdict

class DistributedFileSystem:
    MULTICAST_GROUP = "224.1.1.1"
    MULTICAST_PORT = 5000
    NODE_PORT = 6000
    LOCK_EXPIRATION_TIME = 300  # Segundos antes de liberar un lock automáticamente

    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.filesystem_path = os.path.join(self.script_dir, "filesystem.json")
        self.lock_path = os.path.join(self.script_dir, "lock.json")
        self.node_start_time = time.time()
        self.discovered_nodes = set()
        self.global_lock = self.load_global_lock()

        # Iniciar servicios en hilos separados
        threading.Thread(target=self.send_heartbeat, daemon=True).start()
        threading.Thread(target=self.listen_for_heartbeats, daemon=True).start()
        threading.Thread(target=self.start_server, daemon=True).start()
        threading.Thread(target=self.cleanup_expired_locks, daemon=True).start()

        # Sincronizar con el nodo más antiguo
        self.sync_filesystem_with_oldest()

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]

    def send_heartbeat(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        while True:
            message = json.dumps({"ip": self.get_local_ip(), "port": self.NODE_PORT})
            sock.sendto(message.encode(), (self.MULTICAST_GROUP, self.MULTICAST_PORT))
            time.sleep(5)

    def listen_for_heartbeats(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", self.MULTICAST_PORT))

        mreq = socket.inet_aton(self.MULTICAST_GROUP) + socket.inet_aton("0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        while True:
            data, _ = sock.recvfrom(1024)
            node_info = json.loads(data.decode())
            if node_info["ip"] != self.get_local_ip():
                self.discovered_nodes.add((node_info["ip"], node_info["port"]))
                print(f'Se encontró al nodo: {node_info["ip"]}')

    def load_global_lock(self):
        try:
            with open(self.lock_path, "r") as f:
                return json.load(f) or {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_global_lock(self, data, propagate=True):
        with open(self.lock_path, "w") as f:
            json.dump(data, f, indent=4)
        if propagate:
            self.propagate_global_lock(data)

    def cleanup_expired_locks(self):
        while True:
            current_time = time.time()
            if self.global_lock and current_time - self.global_lock.get("timestamp", 0) > self.LOCK_EXPIRATION_TIME:
                print("Lock global expirado, liberando...")
                self.global_lock = {}
                self.save_global_lock(self.global_lock)
            time.sleep(60)  # Verificar cada minuto

    def request_global_lock(self):
        responses = self.communicate_with_nodes({"type": "LOCK_REQUEST"})
        if all(resp.get("status") == "OK" for resp in responses):
            self.global_lock = {
                "node": self.get_local_ip(),
                "timestamp": time.time()
            }
            self.save_global_lock(self.global_lock)
            return True
        return False

    def release_global_lock(self):
        if self.global_lock:
            self.global_lock = {}
            self.save_global_lock(self.global_lock)

    def propagate_global_lock(self, data):
        self.broadcast_message({"type": "LOCK_UPDATE", "lock": data})

    def load_filesystem(self):
        try:
            with open(self.filesystem_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print("NO DELVOLVI NADAAA")
            return None

    def save_filesystem(self, data, propagate=True):
        data["last_update"] = time.time()
        with open(self.filesystem_path, "w") as f:
            json.dump(data, f, indent=4)
        if propagate:
            self.propagate_filesystem()

    def propagate_filesystem(self):
        self.broadcast_message({"type": "FILESYSTEM_UPDATE"})
        for ip, port in self.discovered_nodes:
            try:
                with socket.create_connection((ip, port), timeout=5) as sock:
                    # Enviar el archivo JSON
                    self.send_json_file(sock, self.filesystem_path)
            except:
                pass

    def communicate_with_nodes(self, message):
        responses = []
        for ip, port in self.discovered_nodes:
            try:
                with socket.create_connection((ip, port), timeout=5) as sock:
                    sock.sendall(json.dumps(message).encode())
                    response = json.loads(sock.recv(1024).decode())
                    responses.append(response)
            except:
                pass
        return responses

    def get_oldest_node(self):
        responses = self.communicate_with_nodes({"type": "NODE_START_TIME", "timestamp": self.node_start_time})
        responses.append({"ip": self.get_local_ip(), "timestamp": self.node_start_time})
        return min(responses, key=lambda x: x["timestamp"])["ip"]

    def sync_filesystem_with_oldest(self):
        """
        Sincroniza el sistema de archivos con el nodo más antiguo.
        """
        # Obtener el nodo más antiguo
        oldest_node_ip = self.get_oldest_node()
        
        # Si el nodo más antiguo no es el actual, solicitar el sistema de archivos
        if oldest_node_ip != self.get_local_ip():
            try:
                # Conectar al nodo más antiguo
                with socket.create_connection((oldest_node_ip, self.NODE_PORT), timeout=5) as sock:
                    # Enviar solicitud de sistema de archivos
                    sock.sendall(json.dumps({"type": "FILESYSTEM_REQUEST"}).encode())
                    
                    # Recibir el archivo JSON del sistema de archivos
                    self.receive_json_file(sock, self.filesystem_path)
                    
                    # Cargar el sistema de archivos recibido
                    self.file_system.load_from_json(self.filesystem_path)
                    print("[INFO] Sistema de archivos sincronizado con el nodo más antiguo.")
            except Exception as e:
                print(f"[ERROR] No se pudo sincronizar con el nodo más antiguo: {e}")

    def handle_request(self, client_socket):
        try:
            data = json.loads(client_socket.recv(1024).decode())
            response = {}
            if data["type"] == "FILESYSTEM_UPDATE":
                self.receive_json_file(client_socket, self.filesystem_path)
                response = {"status": "UPDATED"}
            elif data["type"] == "LOCK_REQUEST":
                response = {"status": "OK"} if not self.global_lock else {"status": "DENIED"}
            elif data["type"] == "LOCK_UPDATE":
                self.global_lock = data["lock"]
                self.save_global_lock(self.global_lock, propagate=False)
                response = {"status": "LOCKS_UPDATED"}
            elif data["type"] == "NODE_START_TIME":
                response = {"ip": self.get_local_ip(), "timestamp": self.node_start_time}
            elif data["type"] == "FILESYSTEM_REQUEST":
                # Enviar el archivo JSON del sistema de archivos
                self.send_json_file(client_socket, self.filesystem_path)
                response = {"status": "UPDATED"}
            client_socket.sendall(json.dumps(response).encode())
        except:
            pass
        finally:
            client_socket.close()

    def start_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("0.0.0.0", self.NODE_PORT))
        server.listen(5)
        while True:
            client, _ = server.accept()
            threading.Thread(target=self.handle_request, args=(client,)).start()

    def broadcast_message(self, message):
        for ip, port in self.discovered_nodes:
            try:
                with socket.create_connection((ip, port), timeout=5) as sock:
                    sock.sendall(json.dumps(message).encode())
            except:
                pass

    def send_json_file(sock, file_path):
        # Leer el archivo JSON
        with open(file_path, "rb") as f:
            file_data = f.read()

        # Enviar el tamaño del archivo
        file_size = len(file_data)
        sock.sendall(str(file_size).encode())

        # Esperar confirmación del receptor
        confirmation = sock.recv(1024).decode()
        if confirmation != "READY":
            raise Exception("El receptor no está listo para recibir el archivo.")

        # Enviar el archivo en fragmentos
        sock.sendall(file_data)

    def receive_json_file(sock, file_path):
        # Recibir el tamaño del archivo
        file_size = int(sock.recv(1024).decode())

        # Confirmar que está listo para recibir el archivo
        sock.sendall("READY".encode())

        # Recibir el archivo en fragmentos
        received_data = b""
        while len(received_data) < file_size:
            chunk = sock.recv(1024)
            if not chunk:
                break
            received_data += chunk

        # Guardar el archivo recibido
        with open(file_path, "wb") as f:
            f.write(received_data)

# class DistributedFileSystem:
#     MULTICAST_GROUP = "224.1.1.1"
#     MULTICAST_PORT = 5000
#     NODE_PORT = 6000
#     LOCK_EXPIRATION_TIME = 300  # Segundos antes de liberar un lock automáticamente

#     def __init__(self):
#         self.script_dir = os.path.dirname(os.path.abspath(__file__))
#         self.filesystem_path = os.path.join(self.script_dir, "filesystem.json")
#         self.lock_path = os.path.join(self.script_dir, "lock.json")
#         self.node_start_time = time.time()
#         self.discovered_nodes = set()

#         threading.Thread(target=self.send_heartbeat, daemon=True).start()
#         threading.Thread(target=self.listen_for_heartbeats, daemon=True).start()
#         threading.Thread(target=self.start_server, daemon=True).start()
#         self.sync_filesystem_with_oldest()
    
#     def get_local_ip(self):
#         s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         s.connect(("8.8.8.8", 80))
#         return s.getsockname()[0]
    
#     def send_heartbeat(self):
#         sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
#         sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
#         while True:
#             message = json.dumps({"ip": self.get_local_ip(), "port": self.NODE_PORT})
#             sock.sendto(message.encode(), (self.MULTICAST_GROUP, self.MULTICAST_PORT))
#             time.sleep(5)

#     def listen_for_heartbeats(self):
#         sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
#         sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#         sock.bind(("", self.MULTICAST_PORT))

#         mreq = socket.inet_aton(self.MULTICAST_GROUP) + socket.inet_aton("0.0.0.0")
#         sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

#         while True:
#             data, _ = sock.recvfrom(1024)
#             node_info = json.loads(data.decode())
#             if node_info["ip"] != self.get_local_ip():
#                 self.discovered_nodes.add((node_info["ip"], node_info["port"]))
#                 print(f'Se encontró al nodo: {node_info["ip"]}')

#     def load_locks(self):
#         try:
#             with open(self.lock_path, "r") as f:
#                 return json.load(f) or {}
#         except (FileNotFoundError, json.JSONDecodeError):
#             return {}

#     def save_locks(self, data, propagate=True):
#         with open(self.lock_path, "w") as f:
#             json.dump(data, f, indent=4)
#         if propagate:
#             self.propagate_locks(data)

#     def request_lock(self, action, target):
#         responses = self.communicate_with_nodes({"type": "LOCK_REQUEST", "target": target})
#         if all(resp.get("status") == "OK" for resp in responses):
#             locks = self.load_locks()
#             locks[target] = {"action": action, "timestamp": time.time(), "node": self.get_local_ip()}
#             self.save_locks(locks)
#             return True
#         return False

#     def release_lock(self, target):
#         locks = self.load_locks()
#         if target in locks:
#             del locks[target]
#             self.save_locks(locks)

#     def propagate_locks(self, data):
#         self.broadcast_message({"type": "LOCK_UPDATE", "locks": data})

#     def load_filesystem(self):
#         try:
#             with open(self.filesystem_path, "r") as f:
#                 return json.load(f)
#         except FileNotFoundError:
#             return None

#     def save_filesystem(self, data, propagate=True):
#         data["last_update"] = time.time()
#         with open(self.filesystem_path, "w") as f:
#             json.dump(data, f, indent=4)
#         if propagate:
#             self.propagate_filesystem(data)

#     def propagate_filesystem(self, data):
#         self.broadcast_message({"type": "FILESYSTEM_UPDATE", "data": data})

#     def communicate_with_nodes(self, message):
#         responses = []
#         for ip, port in self.discovered_nodes:
#             try:
#                 with socket.create_connection((ip, port), timeout=5) as sock:
#                     sock.sendall(json.dumps(message).encode())
#                     response = json.loads(sock.recv(1024).decode())
#                     responses.append(response)
#             except:
#                 pass
#         return responses

#     def get_oldest_node(self):
#         responses = self.communicate_with_nodes({"type": "NODE_START_TIME", "timestamp": self.node_start_time})
#         responses.append({"ip": self.get_local_ip(), "timestamp": self.node_start_time})
#         return min(responses, key=lambda x: x["timestamp"])["ip"]

#     def sync_filesystem_with_oldest(self):
#         oldest_node_ip = self.get_oldest_node()
#         if oldest_node_ip != self.get_local_ip():
#             responses = self.communicate_with_nodes({"type": "FILESYSTEM_REQUEST"})
#             for resp in responses:
#                 if resp.get("data"):
#                     self.save_filesystem(resp["data"], propagate=False)
#                     break

#     def handle_request(self, client_socket):
#         try:
#             data = json.loads(client_socket.recv(1024).decode())
#             response = {}
#             if data["type"] == "FILESYSTEM_UPDATE":
#                 self.save_filesystem(data["data"], propagate=False)
#                 response = {"status": "UPDATED"}
#             elif data["type"] == "LOCK_REQUEST":
#                 locks = self.load_locks()
#                 response = {"status": "OK"} if data["target"] not in locks else {"status": "DENIED"}
#             elif data["type"] == "LOCK_UPDATE":
#                 self.save_locks(data["locks"], propagate=False)
#                 response = {"status": "LOCKS_UPDATED"}
#             elif data["type"] == "NODE_START_TIME":
#                 response = {"ip": self.get_local_ip(), "timestamp": self.node_start_time}
#             elif data["type"] == "FILESYSTEM_REQUEST":
#                 response = {"data": self.load_filesystem()}
#             client_socket.sendall(json.dumps(response).encode())
#         except:
#             pass
#         finally:
#             client_socket.close()

#     def start_server(self):
#         server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         server.bind(("0.0.0.0", self.NODE_PORT))
#         server.listen(5)
#         while True:
#             client, _ = server.accept()
#             threading.Thread(target=self.handle_request, args=(client,)).start()

# if __name__ == "__main__":
#     dfs = DistributedFileSystem()


# # Ruta completa del script
# script_path = os.path.abspath(__file__)
# # Directorio donde está el script
# script_dir = os.path.dirname(script_path)

# FILESYSTEM_JSON = os.path.join(script_dir, "filesystem.json")
# LOCK_FILE = os.path.join(script_dir, "lock.json")
# LOCK_EXPIRATION_TIME = 300  # Segundos antes de liberar un lock automáticamente

# NODE_START_TIME = time.time()  # Guardar la hora de inicio del nodo

# MULTICAST_GROUP = "224.1.1.1"
# MULTICAST_PORT = 5000
# NODE_PORT = 6000
# DISCOVERED_NODES=set()

# def send_heartbeat():
#     """Envía un mensaje multicast anunciando este nodo."""
#     sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
#     sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

#     while True:
#         message = json.dumps({"ip": get_local_ip(), "port": NODE_PORT})
#         sock.sendto(message.encode(), (MULTICAST_GROUP, MULTICAST_PORT))
#         time.sleep(5)

# def listen_for_heartbeats():
#     """Escucha mensajes multicast de otros nodos."""
#     sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
#     sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#     sock.bind(("", MULTICAST_PORT))

#     mreq = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton("0.0.0.0")
#     sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

#     while True:
#         data, _ = sock.recvfrom(1024)
#         node_info = json.loads(data.decode())

#         if node_info["ip"] != get_local_ip():
#             DISCOVERED_NODES.add((node_info["ip"], node_info["port"]))
#             print(f'Se encontro al nodo: {node_info["ip"]}')

# def get_local_ip():
#     """Obtiene la IP local de este nodo."""
#     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     s.connect(("8.8.8.8", 80))
#     return s.getsockname()[0]


# # ----------------- CARGA Y GUARDADO DE LOCKS -----------------

# def load_locks():
#     """Carga los bloqueos actuales desde lock.json de forma segura."""
#     try:
#         with open(LOCK_FILE, "r") as f:
#             content = f.read().strip()
#             if not content:
#                 return {}
#             return json.loads(content)
#     except (FileNotFoundError, json.JSONDecodeError):
#         return {}

# def save_locks(data, propagate=True):
#     """Guarda los bloqueos en lock.json y los propaga a otros nodos."""
#     with open(LOCK_FILE, "w") as f:
#         json.dump(data, f, indent=4)
    
#     if propagate:
#         propagate_locks(data)

# def request_lock(action, target):
#     """Solicita un lock distribuido consultando a todos los nodos."""
#     responses = communicate_with_nodes({"type": "LOCK_REQUEST", "target": target})
    
#     if all(resp.get("status") == "OK" for resp in responses):
#         locks = load_locks()
#         locks[target] = {"action": action, "timestamp": time.time(), "node": get_local_ip()}
#         save_locks(locks)
#         return True
#     return False

# def release_lock(target):
#     """Libera un lock."""
#     locks = load_locks()
#     if target in locks:
#         del locks[target]
#         save_locks(locks)


# def propagate_locks(data):
#     for ip, port in DISCOVERED_NODES:
#         try:
#             with socket.create_connection((ip, port), timeout=10) as sock:
#                 sock.sendall(json.dumps({"type": "LOCK_UPDATE", "locks": data}).encode())
#         except:
#             pass

# # ----------------- CARGA Y GUARDADO DEL FILESYSTEM -----------------

# def load_filesystem():
#     """Carga el filesystem.json en memoria."""
#     try:
#         with open(FILESYSTEM_JSON, "r") as f:
#             return json.load(f)
#     except FileNotFoundError:
#         return None

# def save_filesystem(data, propagate=True):
#     """Guarda filesystem.json y lo replica en todos los nodos."""
#     data["last_update"] = time.time()
#     with open(FILESYSTEM_JSON, "w") as f:
#         json.dump(data, f, indent=4)
    
#     if propagate:
#         propagate_filesystem(data)

# def propagate_filesystem(data):
#     for ip, port in DISCOVERED_NODES:
#         try:
#             with socket.create_connection((ip, port), timeout=10) as sock:
#                 sock.sendall(json.dumps({"type": "FILESYSTEM_UPDATE", "data": data}).encode())
#         except:
#             pass

# # ----------------- PROPAGACIÓN Y SINCRONIZACIÓN -----------------

# def communicate_with_nodes(message):
#     """Envía un mensaje a todos los nodos y recoge sus respuestas."""
#     responses = []
#     for ip, port in DISCOVERED_NODES:
#         try:
#             with socket.create_connection((ip, port), timeout=5) as sock:
#                 sock.sendall(json.dumps(message).encode())
#                 response = json.loads(sock.recv(1024).decode())
#                 responses.append(response)
#         except:
#             pass
#     return responses

# def get_oldest_node():
#     """Obtiene el nodo con la hora de inicio más antigua."""
#     responses = communicate_with_nodes({"type": "NODE_START_TIME", "timestamp": NODE_START_TIME})
#     responses.append({"ip": get_local_ip(), "timestamp": NODE_START_TIME})
    
#     oldest_node = min(responses, key=lambda x: x["timestamp"])
#     return oldest_node["ip"]

# def sync_filesystem_with_oldest():
#     """Sincroniza el filesystem con el nodo más antiguo al unirse a la red."""
#     oldest_node_ip = get_oldest_node()
#     if oldest_node_ip != get_local_ip():
#         responses = communicate_with_nodes({"type": "FILESYSTEM_REQUEST"})
#         for resp in responses:
#             if resp.get("data"):
#                 save_filesystem(resp["data"], propagate=False)
#                 break

# # ----------------- SERVIDOR DE REPLICACIÓN -----------------

# def handle_request(client_socket):
#     """Maneja solicitudes de otros nodos."""
#     try:
#         data = json.loads(client_socket.recv(1024).decode())
#         response = {}
        
#         if data["type"] == "FILESYSTEM_UPDATE":
#             save_filesystem(data["data"], propagate=False)
#             response = {"status": "UPDATED"}
        
#         elif data["type"] == "LOCK_REQUEST":
#             locks = load_locks()
#             if data["target"] not in locks:
#                 response = {"status": "OK"}
#             else:
#                 response = {"status": "DENIED"}
        
#         elif data["type"] == "LOCK_UPDATE":
#             save_locks(data["locks"], propagate=False)
#             response = {"status": "LOCKS_UPDATED"}
        
#         elif data["type"] == "NODE_START_TIME":
#             response = {"ip": get_local_ip(), "timestamp": NODE_START_TIME}
        
#         elif data["type"] == "FILESYSTEM_REQUEST":
#             response = {"data": load_filesystem()}
        
#         client_socket.sendall(json.dumps(response).encode())
#     except:
#         pass
#     finally:
#         client_socket.close()

# def start_server():
#     """Servidor que maneja sincronización de filesystem y locks."""
#     server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     server.bind(("0.0.0.0", NODE_PORT))
#     server.listen(5)
    
#     while True:
#         client, _ = server.accept()
#         threading.Thread(target=handle_request, args=(client,)).start()

# # ----------------- INICIAR SISTEMA -----------------
# # Iniciar descubrimiento de nodos
# threading.Thread(target=send_heartbeat, daemon=True).start()
# threading.Thread(target=listen_for_heartbeats, daemon=True).start()

# threading.Thread(target=start_server, daemon=True).start()
# sync_filesystem_with_oldest()