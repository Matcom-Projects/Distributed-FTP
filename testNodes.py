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
    def __init__(self, name,key ,content="",permissions=0o644):
        self.name = name
        self.content = content
        self.key=key
        self.created_at = time.time()
        self.modified_at = time.time()
        self.permissions = permissions
        self.nlink = 1
        self.size = len(content)

    def to_dict(self):
        """Convierte el archivo en un diccionario para serialización JSON."""
        return {
            "type": "file",
            "name": self.name,
            "key": self.key,
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
        file = File(data["name"], data["key"])
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

    def touch(self, path,key):
        """Crea un archivo vacío."""
        parent_path, file_name = path.rsplit("/", 1) if "/" in path else ("", path)
        parent = self.resolve_path(parent_path)

        if parent and isinstance(parent, Directory) and file_name not in parent.contents:
            new_file = File(file_name,key)
            parent.contents[file_name] = new_file
            self.path_map[path] = new_file
            return f"Archivo '{path}' creado exitosamente."
        return "Error: No se pudo crear el archivo."

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
    await writer.drain()

    authenticated = False
    username = ''
    data_type = 'ASCII'
    restart_point = 0
    path_to_change = None
    current_dir = "/"

    # Define users dictionary - you might want to move this to a configuration file
    users = {'user': 'user1234'} 
    
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


    '''
            FALTA POR IMPLEMENTAAAAAAAAARRR COMANDOS:
            1- PORT
            2- RETR
            3- STOR
            4- STOU
            5- REIN >>> TAREA PENDIENTE:  FALTA POR CERRAR EL SOCKET ABIERTO EN PORT O PASV.
            6- APPE
            7- ABOR
            8- NLST
            9- DELE >>> TAREA PENDIENTE:  NECESITAS BORRAR EL ARCHIVO DE LA RED KADEMLIA.
    '''

    while True:
        
        data = await reader.readline() # Read data from client
        if not data:
            print(f"Connection closed from client {addr}")
            break

        try:
            #AQUIIIIIIIIIIII <<<<=========<<<<<<<<<<<<<<<============
            # Load filesystem state
            # This would need to be adapted to your specific filesystem implementation
            # fileSystem.load_from_json() or similar function
            pass
        except Exception as e:
            print(f"Error loading filesystem: {e}")

        command = data.decode().strip()
        action, *args = command.split(' ', 1)
        arg = args[0] if args else None
        print (command)

        if command == "USER":
            username = args
            if username in users:
                writer.write(b'331 User name okay, need password.\r\n')
            else:
                writer.write(b'530 User incorrect.\r\n')
            await writer.drain()
            
        elif command == "PASS":
            password = args
            if users.get(username) == password:
                authenticated = True
                writer.write(b'230 User logged in.\r\n')
            else:
                writer.write(b'530 Password incorrect.\r\n')
            await writer.drain()

        elif not authenticated:
            writer.write(b'530 Not logged in.\r\n')
            await writer.drain()

        elif command == "PWD":
            writer.write(f'257 "{current_dir}"\r\n'.encode())
            await writer.drain()

        elif command == "CWD":
            if args:
                new_dir = args
                resolved_path = f"{current_dir}/{new_dir}".replace("//", "/")
                if fileSystem.resolve_path(resolved_path):
                    current_dir = resolved_path
                    writer.write(b"250 Directory successfully changed.\r\n")
                else:
                    writer.write(b"550 Failed to change directory.\r\n")
            else:
                writer.write(b"501 Syntax error in parameters or arguments.\r\n")
            await writer.drain()

        elif command == "MKD":
            try:
                dir_name = args
                resolved_path = f"{current_dir}/{dir_name}".replace("//", "/")
                result = fileSystem.mkdir(resolved_path)
                
                if "exitosamente" in result or result:
                    # Save filesystem state
                    fileSystem.save_to_json(FILESYSTEM_JSON)  # Update to your actual save method
                    
                    # Propagate changes to other nodes if needed
                    # Adapt to your node.set() or similar functionality
                    with open(FILESYSTEM_JSON, "r") as file:
                        data = json.load(file)
                    await node.set(FILESYSTEM_JSON, str(data).encode())
                    
                    writer.write(f'257 "{dir_name}" created.\r\n'.encode())
                else:
                    writer.write(b"550 Directory creation failed (already exists).\r\n")
            except Exception as e:
                writer.write(b"501 Syntax error in parameters or arguments.\r\n")
                print(f"Error in MKD: {e}")
            await writer.drain()
        
        elif command == "ACCT":
            try:
                # Start with account status header
                writer.write(b'211-Account status.\r\n')
                await writer.drain()
                
                # User information
                writer.write(f'Name: {username}\r\n'.encode())
                await writer.drain()
                
                # Check authentication status
                if authenticated:
                    # Note: This is typically not recommended for security reasons
                    # Showing password in the response, but keeping for compatibility
                    writer.write(f'Authentication: Authenticated\r\n'.encode())
                    await writer.drain()
                else:
                    writer.write(f'Authentication: Not authenticated\r\n'.encode())
                    await writer.drain()
                    
                # End of status
                writer.write(b'211 End of account status.\r\n')
                await writer.drain()
            except Exception as e:
                writer.write(b'500 Error processing account information.\r\n')
                await writer.drain()
                print(f"Error in ACCT command: {e}")
        
        elif command == "LIST":
            try:
                writer.write(b'150 Here comes the directory listing\r\n')
                await writer.drain()
                
                # Determine which directory to list
                list_path = current_dir
                if args:
                    # If path provided, resolve it relative to current directory
                    list_path = f"{current_dir}/{args}".replace("//", "/")
                
                # Get directory object from virtual filesystem
                directory = fileSystem.resolve_path(list_path)
                
                if not directory or not isinstance(directory, Directory):
                    writer.write(b"550 Failed to list directory.\r\n")
                    await writer.drain()
                    continue

                if writer_N:
                    await passive_socket.start_serving()
                    file_details = ['Permissions  Links  Size           Last-Modified  Name']
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
                
            except Exception as e:
                writer.write(f'550 Failed to list directory: {e}\r\n'.encode())
                print(f'Error listing directory: {e}')
            
            await writer.drain()

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

            await writer.drain()

        elif command == "REIN":
            # Reset session state variables to default values
            authenticated = False
            username = ''
            data_type = 'ASCII'
            restart_point = 0
            path_to_change = None
            # Note: We don't reset current_dir - user needs to navigate again
            
            # Clean up any active data connections
            # await close_data_connection()
            # NECESITAS CERRAR LAS CONEXIONES EN CASO DE ABRIRLAS
            
            writer.write(b'220 Service ready for new user.\r\n')
            await writer.drain()

        elif command == "CDUP":
            # If already at root directory, can't go up further
            if current_dir == "/":
                writer.write(b'550 Already at root directory.\r\n')
            else:
                # Split the path and remove the last component
                path_parts = current_dir.strip("/").split("/")
                
                # If we have parts left, build new path; otherwise, go to root
                if len(path_parts) > 1:
                    parent_path = "/" + "/".join(path_parts[:-1])
                else:
                    parent_path = "/"
                
                # Verify the parent directory exists in the filesystem
                if fileSystem.resolve_path(parent_path):
                    current_dir = parent_path  # Update current directory
                    writer.write(b'200 Directory changed to parent directory.\r\n')
                else:
                    writer.write(b'550 Failed to change directory.\r\n')
            await writer.drain()

        elif command == "TYPE":
            try:
                data_type_arg = args.upper()
                if data_type_arg == 'A':
                    data_type = 'ASCII'
                    writer.write(b'200 Type set to ASCII.\r\n')
                elif data_type_arg == 'I':
                    data_type = 'Binary'
                    writer.write(b'200 Type set to Binary.\r\n')
                else:
                    writer.write(b'504 Type not implemented.\r\n')
            except Exception as e:
                writer.write(b'501 Syntax error in parameters.\r\n')
                print(f"Error in TYPE command: {e}")
            await writer.drain()

        elif command == "STRU":
            try:
                structure_type = args.upper()
                if structure_type == 'F':
                    # 'F' is File structure (the only one we implement)
                    writer.write(b'200 File structure set to file.\r\n')
                else:
                    # We don't implement Record ('R') or Page ('P') structures
                    writer.write(b'504 Structure not implemented.\r\n')
            except Exception as e:
                writer.write(b'501 Syntax error in parameters.\r\n')
                print(f"Error in STRU command: {e}")
            await writer.drain()

        elif command == "MODE":
            try:
                mode_type = args.upper()
                if mode_type == 'S':
                    # 'S' is Stream mode (the only one we implement)
                    writer.write(b'200 Mode set to stream.\r\n')
                else:
                    # We don't implement Block ('B') or Compressed ('C') modes
                    writer.write(b'504 Mode not implemented.\r\n')
            except Exception as e:
                writer.write(b'501 Syntax error in parameters.\r\n')
                print(f"Error in MODE command: {e}")
            await writer.drain()

        elif command == "REST":
            try:
                # Parse the restart position
                byte_offset = int(args)
                restart_point = byte_offset
                writer.write(b"350 Restart marker accepted.\r\n")
            except ValueError:
                writer.write(b"501 Syntax error in parameters - must be a number.\r\n")
            except Exception as e:
                writer.write(b"501 Syntax error in parameters.\r\n")
                print(f"Error in REST command: {e}")
            await writer.drain()

        elif command == "RNFR":
            try:
                filename = args
                resolved_path = f"{current_dir}/{filename}".replace("//", "/")

                # Check if the file or directory exists in the virtual filesystem
                item_to_rename = fileSystem.resolve_path(resolved_path)

                if item_to_rename:
                    # Store the path for the subsequent RNTO command
                    path_to_change = resolved_path
                    writer.write(b"350 Ready for RNTO.\r\n")
                else:
                    writer.write(b"550 File or directory not found.\r\n")
            except Exception as e:
                writer.write(b"550 Error processing rename request.\r\n")
                print(f"Error in RNFR: {e}")
            await writer.drain()

        elif command == "RNTO":
            if not path_to_change:
                writer.write(b"503 RNFR required before RNTO.\r\n")
                await writer.drain()
                continue

            try:
                new_name = args
                old_path = path_to_change

                # Calculate parent directory from old path
                parts = old_path.strip("/").split("/")
                if len(parts) == 1:
                    parent_path = "/"  # If item is in root
                else:
                    parent_path = "/" + "/".join(parts[:-1])
                new_path = f"{parent_path}/{new_name}".replace("//", "/")
                
                # Get parent directory object from virtual filesystem
                parent_directory = fileSystem.resolve_path(parent_path)
                if not parent_directory or not isinstance(parent_directory, Directory):
                    writer.write(b"550 Failed to rename: parent directory not found.\r\n")
                    await writer.drain()
                    continue

                # Get old filename/key (last part of old_path)
                old_key = parts[-1]

                # Check item exists in parent directory
                if old_key not in parent_directory.contents:
                    writer.write(b"550 File or directory not found in parent's directory.\r\n")
                    await writer.drain()
                    continue

                # Get object to rename
                item = parent_directory.contents[old_key]
                
                # Remove old entry from directory and path map
                del parent_directory.contents[old_key]
                del fileSystem.path_map[old_path]

                # Update object name
                item.name = new_name

                # Insert object with new name and update path map
                parent_directory.contents[new_name] = item
                fileSystem.path_map[new_path] = item

                # Save filesystem changes
                fileSystem.save_to_json(FILESYSTEM_JSON)
                
                # Propagate changes to other nodes
                with open(FILESYSTEM_JSON, "r") as file:
                    data = json.load(file)
                await node.set(FILESYSTEM_JSON, str(data).encode())
                
                writer.write(b"250 Requested file action completed.\r\n")
                path_to_change = None  # Reset the path_to_change variable
            except Exception as e:
                writer.write(b"550 Rename failed.\r\n")
                print(f"Error renaming file/directory: {e}")
            await writer.drain()

        elif command == "RMD":
            try:
                dir_name = args
                # Build the complete virtual path for the directory
                resolved_path = f"{current_dir}/{dir_name}".replace("//", "/")
                
                # Get the directory object from virtual filesystem
                item = fileSystem.resolve_path(resolved_path)
                
                # Verify the object exists and is a directory
                if item and isinstance(item, Directory):
                    # Remove the directory
                    result = fileSystem.rm(resolved_path)
                    
                    # Check if removal was successful
                    if result and ("exitosamente" in result or "success" in result.lower()):
                        # Save filesystem changes
                        fileSystem.save_to_json(FILESYSTEM_JSON)
                        
                        # Propagate changes to other nodes
                        with open(FILESYSTEM_JSON, "r") as file:
                            data = json.load(file)
                        await node.set(FILESYSTEM_JSON, str(data).encode())
                        
                        writer.write(b"250 Directory deleted successfully.\r\n")
                    else:
                        writer.write(b"550 Failed to delete directory.\r\n")
                else:
                    writer.write(b"550 Directory not found.\r\n")
            except Exception as e:
                writer.write(b"550 Failed to delete directory.\r\n")
                print(f"Error in RMD: {e}")
            await writer.drain()

        elif command == "DELE":
            try:
                filename = args
                # Build the complete virtual path for the file
                resolved_path = f"{current_dir}/{filename}".replace("//", "/")
                
                # Get the file object from virtual filesystem
                item = fileSystem.resolve_path(resolved_path)
                
                # Verify the object exists and is a file
                if item and isinstance(item, File):
                    # Remove the file
                    result = fileSystem.rm(resolved_path)
                    
                    # Check if removal was successful
                    if result and ("exitosamente" in result or "success" in result.lower()):
                        # Save filesystem changes
                        fileSystem.save_to_json(FILESYSTEM_JSON)
                        
                        # Propagate changes to other nodes
                        with open(FILESYSTEM_JSON, "r") as file:
                            data = json.load(file)
                        await node.set(FILESYSTEM_JSON, str(data).encode())
                        ####### ELIMINAAAAAAAR EL ARCHIVOOOO DEL NODO KADEMLIA TAMBIEEEEEEN
                        
                        writer.write(b"250 Requested file action okay, completed.\r\n")
                    else:
                        writer.write(b"550 File not found or permission denied.\r\n")
                else:
                    writer.write(b"550 File not found or permission denied.\r\n")
            except Exception as e:
                writer.write(b"501 Syntax error in parameters or arguments.\r\n")
                print(f"Error in DELE: {e}")
            await writer.drain()

        elif action =="SYST":
            print("pidiendo sistema")
            system_name = platform.system()
            writer.write(f'215 {system_name} Type: L8\r\n'.encode())
            await writer.drain()

        elif command =="NOOP":
            writer.write(b"200 OK.\r\n")
            await writer.drain()

        elif command == "QUIT":
            writer.write(b"221 Closing connection, goodbye.\r\n")
            await writer.drain()
            break

        elif command =="ALLO":
            writer.write(b'200 Command not needed.\r\n')
            await writer.drain()

        elif command =="SITE":
            writer.write(b"503 Command not implemented.\r\n")
            await writer.drain()


        elif command =="SMNT":
            writer.write(b"503 Command not implemented.\r\n")
            await writer.drain()
        
        elif command == "STAT":
            if not args:
                # STAT without arguments - show server status
                writer.write(b"211-FTP Server Status:\r\n")
                await writer.drain()
                        
                # Get the server host address from the socket
                writer.write(f"Connected to {addr}\r\n".encode('utf-8'))
                await writer.drain()
                        
                writer.write(f"Current directory: {current_dir}\r\n".encode('utf-8'))
                await writer.drain()
                        
                writer.write(b"211 End of status.\r\n")
                await writer.drain()
            else:
                writer.write(b"503 Command not implemented.\r\n")
                await writer.drain()

        elif command =="HELP":
                writer.write(b'214 The following commands are recognized.\r\n')
                await writer.drain()
                response=""                
                response+='USER <SP> <nombre-usuario> <CRLF>\r\n'
                response+='PASS <SP> <contraseña> <CRLF>\r\n'
                response+='ACCT <SP> <información-cuenta> <CRLF>\r\n'
                response+='CWD  <SP> <nombre-ruta> <CRLF>\r\n'
                response+='CDUP <CRLF>\r\n'
                response+='SMNT <SP> <nombre-ruta> <CRLF>\r\n'
                response+='QUIT <CRLF>\r\n'
                response+='REIN <CRLF>\r\n'
                response+='PORT <SP> <dirIP-puerto> <CRLF>\r\n'
                response+='PASV <CRLF>\r\n'
                response+='TYPE <SP> <código-tipo> <CRLF>\r\n'
                response+='STRU <SP> <código-estructura> <CRLF>\r\n'
                response+='MODE <SP> <código-modo> <CRLF>\r\n'
                response+='RETR <SP> <nombre-ruta> <CRLF>\r\n'
                response+='STOR <SP> <nombre-ruta> <CRLF>\r\n'
                response+='STOU <CRLF>\r\n'
                response+='APPE <SP> <nombre-ruta> <CRLF>\r\n'
                response+='ALLO [<SP> <entero-decimal>] | [<SP> R <SP> <entero-decimal>] <CRLF>\r\n'
                response+='REST <SP> <marcador> <CRLF>\r\n'
                response+='RNFR <SP> <nombre-ruta> <CRLF>\r\n'
                response+='RNTO <SP> <nombre-ruta> <CRLF>\r\n'
                response+='ABOR <CRLF>\r\n'
                response+='DELE <SP> <nombre-ruta> <CRLF>\r\n'
                response+='RMD  <SP> <nombre-ruta> <CRLF>\r\n'
                response+='MKD  <SP> <nombre-ruta> <CRLF>\r\n'
                response+='PWD  <CRLF>\r\n'
                response+='LIST [<SP> <nombre-ruta>] <CRLF>\r\n'
                response+='NLST [<SP> <nombre-ruta>] <CRLF>\r\n'
                response+='SITE <SP> <cadena> <CRLF>\r\n'
                response+='SYST <CRLF>\r\n'
                response+='STAT [<SP> <nombre-ruta>] <CRLF>\r\n'
                response+='HELP [<SP> <cadena>] <CRLF>\r\n'
                response+='NOOP <CRLF>\r\n'
                writer.write(response.encode())
                await writer.drain()
                writer.write(b'214 Help OK.\r\n')
                await writer.drain()
        
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
            await writer.drain()

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
