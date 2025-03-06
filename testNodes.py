import asyncio
import argparse
import os

from kademlia.network import Server
from kademlia.storage import ForgetfulStorage
import platform
import time
import stat
import json
import socket
FILESYSTEM_JSON = "filesystem.json"
class File:
    """Representa un archivo en el sistema de archivos."""
    def __init__(self, name, content="",permissions=0o644):
        self.name = name
        self.content = content
        self.created_at = time.time()
        self.modified_at = time.time()
        self.permissions = permissions
        self.nlink = 1
        self.size = len(content)

    def read(self):
        return self.content

    def write(self, new_content):
        self.content = new_content
        self.modified_at = time.time()
        self.size = len(new_content)

    def append(self, extra_content):
        self.content += extra_content
        self.modified_at = time.time()
        self.size += len(extra_content)

    def to_dict(self):
        """Convierte el archivo en un diccionario para serialización JSON."""
        return {
            "type": "file",
            "name": self.name,
            "content": self.content,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "permissions": stat.filemode(self.permissions),
            "nlink": self.nlink,
            "size": self.size,
            "mtime": time.strftime('%b %d %H:%M', time.gmtime(self.modified_at))
        }

    @staticmethod
    def from_dict(data):
        """Crea un archivo a partir de un diccionario JSON."""
        file = File(data["name"], data["content"])
        file.created_at = data["created_at"]
        file.modified_at = data["modified_at"]
        file.permissions = int(data["permissions"], 8)
        file.nlink = data["nlink"]
        file.size = data["size"]
        return file


class Directory:
    """Representa un directorio en el sistema de archivos."""
    def __init__(self, name,permissions=0o755):
        self.name = name
        self.contents = {}  # Diccionario para almacenar archivos y subdirectorios
        self.created_at = time.time()
        self.permissions = permissions
        self.size=0
        self.nlink = 2 

    def list_contents(self):
        return list(self.contents.keys())

    def to_dict(self):
        """Convierte el directorio en un diccionario JSON."""
        return {
            "type": "directory",
            "name": self.name,
            "created_at": self.created_at,
            "size": self.size,
            "permissions": stat.filemode(self.permissions),
            "nlink": self.nlink,
            "mtime": time.strftime('%b %d %H:%M', time.gmtime(self.created_at)),
            "contents": {name: item.to_dict() for name, item in self.contents.items()}
        }

    @staticmethod
    def from_dict(data):
        """Crea un directorio a partir de un diccionario JSON."""
        directory = Directory(data["name"])
        directory.created_at = data["created_at"]
        directory.nlink = data["nlink"]
        for name, item in data["contents"].items():
            if item["type"] == "file":
                directory.contents[name] = File.from_dict(item)
            else:
                directory.contents[name] = Directory.from_dict(item)
        return directory


class FileSystem:
    """Sistema de archivos básico en memoria con soporte para exportar e importar JSON."""
    def __init__(self):
        self.root = Directory("/")
        self.path_map = {"/": self.root}

    def resolve_path(self, path):
        """Convierte una ruta en un objeto (archivo o directorio)."""
        path = path.strip("/")
        if path == "":
            return self.root

        if path in self.path_map:
            return self.path_map[path]
        
        parts = path.split("/")
        node = self.root

        for part in parts:
            if isinstance(node, Directory) and part in node.contents:
                node = node.contents[part]
            else:
                return None
        return node

    def mkdir(self, path):
        """Crea un nuevo directorio."""
        parent_path, dir_name = path.rsplit("/", 1) if "/" in path else ("", path)
        parent = self.resolve_path(parent_path)

        if parent and isinstance(parent, Directory) and dir_name not in parent.contents:
            new_dir = Directory(dir_name)
            parent.contents[dir_name] = new_dir
            self.path_map[path] = new_dir
            print(self.path_map)
            return f"Directorio '{path}' creado exitosamente."
        return "Error: No se pudo crear el directorio."

    def touch(self, path):
        """Crea un archivo vacío."""
        parent_path, file_name = path.rsplit("/", 1) if "/" in path else ("", path)
        parent = self.resolve_path(parent_path)

        if parent and isinstance(parent, Directory) and file_name not in parent.contents:
            new_file = File(file_name)
            parent.contents[file_name] = new_file
            self.path_map[path] = new_file
            return f"Archivo '{path}' creado exitosamente."
        return "Error: No se pudo crear el archivo."

    def write_file(self, path, content):
        """Escribe contenido en un archivo."""
        file = self.resolve_path(path)

        if file and isinstance(file, File):
            file.write(content)
            return f"Contenido escrito en '{path}'."
        return "Error: Archivo no encontrado."

    def read_file(self, path):
        """Lee el contenido de un archivo."""
        file = self.resolve_path(path)

        if file and isinstance(file, File):
            return file.read()
        return "Error: Archivo no encontrado."

    def rm(self, path):
        """Elimina un archivo o directorio."""
        parent_path, name = path.rsplit("/", 1) if "/" in path else ("", path)
        parent = self.resolve_path(parent_path)

        if parent and isinstance(parent, Directory) and name in parent.contents:
            del parent.contents[name]
            del self.path_map[path]
            return f"'{path}' eliminado exitosamente."
        return "Error: No se pudo eliminar."

    def mv(self, old_path, new_path):
        """Mueve o renombra un archivo o directorio."""
        item = self.resolve_path(old_path)
        if item is None:
            return "Error: Elemento no encontrado."

        parent_path, name = new_path.rsplit("/", 1) if "/" in new_path else ("", new_path)
        parent = self.resolve_path(parent_path)

        if not parent or not isinstance(parent, Directory):
            return "Error: No se pudo mover el archivo, el destino no es un directorio válido."

        # Eliminar de la ubicación original
        self.rm(old_path)

        # Mover el objeto al nuevo directorio
        parent.contents[name] = item
        self.path_map[new_path] = item
        return f"'{old_path}' renombrado/movido a '{new_path}'."

    def ls(self, path="/"):
        """Lista los archivos y directorios dentro de un directorio."""
        directory = self.resolve_path(path)

        if directory and isinstance(directory, Directory):
            return directory.list_contents()
        return "Error: Directorio no encontrado."

    def save_to_json(self, filename):
        """Guarda el sistema de archivos en un archivo JSON."""
        data = self.root.to_dict()  # Convertir sistema de archivos a diccionario
        data["last_update"] = time.time()  # Agregar marca de tiempo
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)

    def load_from_json(self, filename):
        """Carga el sistema de archivos desde un archivo JSON."""
        
        with open(filename, "r") as f:
            data = json.load(f)
            # json_data=json.loads(data)
            # print(,"DATA DEL JSONN")
            self.root = Directory.from_dict(data)  # Asegurar acceso a "root"
            self.path_map = {"/": self.root}  # Reiniciar mapa de rutas
            print("Sistema de archivos cargado exitosamente.")


            '''
            self.file_system=FileSystem()<======= asi se inicia la instancia d la clase, aqui no esta cargado el json, debes cargarlo como esta abajo
        
            self.file_system.load_from_json(FILESYSTEM_JSON)<======= asi se carga de un json ya existente FILESYSTEM_JSON es el path al json.
        
            self.file_system.save_to_json(FILESYSTEM_JSON)<======= asi se salva en un json en el path FILESYSTEM_JSON

            self.file_system.mkdir(path)<========= asi crea una carpeta en la instancia de la clase, si quieres que se guarde en el json debes aplicar lo q esta arriba

            self.file_system.resolve_path(path) te devuelve el directorio o archivo de ese path

            self.file_system.rm(path) remueve lo q haya en ese path ya sea directorio o archivo
             '''

# Function to retrieve the local IP address
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    return local_ip
async def store_data(node, key, value):
    await node.set(key, value)

async def retrieve_data(node, key):
    value = await node.get(key)
    return value

async def handle_client(reader, writer, node: Server, fileSystem:FileSystem):
    """Handles remote commands sent via socket"""
    addr = writer.get_extra_info("peername") #<---------------
    print(f"New connection from {addr}")
    writer.write(b"220 FTP service ready.\r\n") #<---------------b\r\n asi????
    
#b"220 FTP service ready.\r\n"  <=============== asiiiiiii
    passive_socket = None
    passive_port = None
    
    reader_N=None
    writer_N=None
    def safe_reader_writer(r,w):
        print("Guardando Reader Writer")
        nonlocal reader_N
        reader_N=r
        nonlocal writer_N
        writer_N=w    
    while True:
        
        data = await reader.readline() # Read data from client
        if not data:
            print(f"Connection closed from client {addr}")
            break

        command = data.decode().strip()
        action, *args = command.split(' ', 1)
        arg = args[0] if args else None
        print (command)
        if action == "USER":
            print("pidiendo usuario")
            
            writer.write(b'331 User name okay, need password.\r\n')
            print("enviado usuario")
            
        elif action == "PASS":
            print("poniendo contraseña")
            writer.write(b'230 User logged in.\r\n')
        elif action =="SYST":
            print("pidiendo sistema")
            system_name = platform.system()
            writer.write(f'215 {system_name} Type: L8\r\n'.encode())
            
        elif action == "MKD":    
            ans = fileSystem.mkdir(arg)
            print(ans)
            fileSystem.save_to_json(FILESYSTEM_JSON)
            print ("se guarda el json local")
            with open(FILESYSTEM_JSON, "r") as file:
                data = json.load(file)
            await node.set(FILESYSTEM_JSON, str(data).encode())
            print("SE guarda el json")
            writer.write(f'257 "{arg}" created.\r\n'.encode())
        
        elif action == "PWD":
                writer.write(f'257 "este mismo"'.encode())

        elif action == "CWD":
            # if arg and os.path.isdir(arg):
            #     self.cwd = arg
                writer.write(b'250 Directory successfully changed.')
            # else:
            #     writer.write(b'550 Failed to change directory.')

        elif action == "QUIT":
            writer.write(b'221 Goodbye.')
            break
        elif action == "PASV":
            passive_socket = await asyncio.start_server(
                lambda r, w: safe_reader_writer(r,w), "0.0.0.0", 0 , # Bind to an available port,
            )
            
            passive_port = passive_socket.sockets[0].getsockname()[1]
            p1, p2 = passive_port // 256, passive_port % 256
            local_ip = get_local_ip()
            
            # Format the IP address for the PASV response
            ip_parts = local_ip.split('.')
            ip_response = ','.join(ip_parts + [str(p1), str(p2)])
            
            writer.write(f'227 Entering Passive Mode ({ip_response}).\r\n'.encode())
        
        elif action == "LIST":
            if writer_N:
                await passive_socket.start_serving()
                dir_contents = fileSystem.ls(arg or "/")
                print(dir_contents, "  EL contenido del directorio")
                print("data connection started")
                writer.write(b'150 Here comes the directory listing.\r\n')
                file_details = ['Permissions  Links  Size           Last-Modified  Name']
                directory = fileSystem.resolve_path("/")
                for item in directory.contents.values():
                    item_data = item.to_dict()
                    details = {
                        'mode': item_data["permissions"].ljust(11),
                        'nlink': str(item_data["nlink"]).ljust(6),
                        'size': str(item_data["size"]).ljust(5),
                        'mtime': item_data["mtime"].ljust(12),
                        'name': item_data["name"]
                    }
                    file_details.append('{mode}  {nlink} {size}          {mtime}   {name}'.format(**details))

                dir_list = '\n'.join(file_details) + '\r\n'
                listing = '\r\n'.join(dir_contents) + '\r\n'
                writer_N.write(dir_list.encode())
                
                writer_N.close()
                await writer_N.wait_closed()
                print('1')
                # passive_socket.close()
                # print('3')
                # await passive_socket.wait_closed()
                passive_socket = None
                print("cerrada la conexion")
                writer.write(b'226 Directory send OK.\r\n')
            else:
                writer.write(b'425 Use PASV first.\r\n')
        
        elif action == "FEAT":
            writer.write(b'211-Features:\r\n')
            writer.write(b' EPRT\r\n')
            writer.write(b' EPSV\r\n')
            writer.write(b' MDTM\r\n')
            writer.write(b' PASV\r\n')
            writer.write(b' REST STREAM\r\n')
            writer.write(b' SIZE\r\n')
            writer.write(b' TVFS\r\n')
            writer.write(b'211 End\r\n')

        else:
            print(f"Command not implemented: {command}")
            writer.write(b"502 Command not implemented.\r\n")

        await writer.drain()  # Ensure data is sent

    print(f"Connection closed from {addr}")
    writer.close()
    await writer.wait_closed()

async def start_tcp_server(node:Server, port):
    """Starts a TCP server for remote clients"""
    jsonKad = await node.get(FILESYSTEM_JSON)
    print(jsonKad,"  EL json qe llegoo")
    file_system = FileSystem()
    if jsonKad:
        with open(FILESYSTEM_JSON, "w") as file:
            json.dump(json.loads(jsonKad.decode().replace("'", '"')), file, indent=4)
        file_system.load_from_json(FILESYSTEM_JSON)
    else:
        file_system.save_to_json(FILESYSTEM_JSON)
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, node,fileSystem=file_system), "0.0.0.0", port
    )
    addr = server.sockets[0].getsockname()
    
    print(f"Listening for remote commands on {addr}")

    async with server:
        await server.serve_forever()

async def run_node(port, command_port, bootstrap_ip=None, bootstrap_port=None):
    node = Server(storage=ForgetfulStorage())
    await node.listen(port)

    if bootstrap_ip and bootstrap_port:
        await node.bootstrap([(bootstrap_ip, bootstrap_port)])
        print(f"Node started on port {port} and connected to {bootstrap_ip}:{bootstrap_port}")
    else:
        print(f"Node started on port {port} (standalone)")

    asyncio.create_task(start_tcp_server(node, command_port))  # Start TCP server for remote commands

    await asyncio.Future()  # Keeps the node running

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True, help="Port to run the Kademlia node")
    parser.add_argument("--command_port", type=int, required=True, help="Port to receive FTP client-like commands")
    parser.add_argument("--bootstrap_ip", type=str, help="Bootstrap node IP")
    parser.add_argument("--bootstrap_port", type=int, help="Bootstrap node Port")

    args = parser.parse_args()
    asyncio.run(run_node(args.port, args.command_port, args.bootstrap_ip, args.bootstrap_port))
