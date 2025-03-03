import os
import io
import socket
import threading
import platform
import uuid
import time
import stat
import sys
import zipfile
from filesystem import FileSystem,Directory,File

# Configuración del servidor
HOST = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
PORT = 21
FILESYSTEM_JSON = "filesystem.json"

class FTPApiServer:
    def __init__(self, host, port,users):
        self.host = host
        self.port = port
        self.data_port=0
        self.data_type='ASCII'
        self.restart_point = 0
        self.users=users
        self.path_to_change=None
        self.file_system = FileSystem()
        self.cwd="/"
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
         # Cargar sistema de archivos si existe un JSON guardado
        try:
            self.file_system.load_from_json(FILESYSTEM_JSON)
            print("[INFO] Sistema de archivos cargado desde JSON.")
        except:
            self.file_system.save_to_json(FILESYSTEM_JSON)
            print("[INFO] No se encontró un archivo JSON, creando nuevo sistema de archivos.")

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"Servidor FTP iniciado en {self.host}:{self.port}")
        while True:
            client_socket, client_address = self.server_socket.accept()
            print(f"Conexión establecida con {client_address}")
            threading.Thread(target=self.handle_client, args=(client_socket,client_address)).start()

    def handle_client(self, client_socket,client_address):
        current_dir = self.cwd
        client_socket.send(b"220 FTP service ready.\r\n")
        authenticated = False
        username = ''
        
        while True:
            data = client_socket.recv(1024).decode()
            if not data:
                break

            print(f"Comando recibido: {data.strip()}")
            command, *args = data.split()
            command = command.upper()

            if command == "USER":
                username = args[0]
                if username in self.users:
                    client_socket.sendall(b'331 User name okay, need password.\r\n')
                else:
                    client_socket.sendall(b'530 User incorrect.\r\n')


            elif command == "PASS":
                password = args[0]
                if self.users.get(username) == password:
                    authenticated = True
                    client_socket.sendall(b'230 User logged in.\r\n')
                else:
                    client_socket.sendall(b'530 Password incorrect in.\r\n')


            elif not authenticated :
                client_socket.sendall(b'530 Not logged in.\r\n')


            elif command == "PWD":
                client_socket.sendall(f'257 "{current_dir}"\r\n'.encode())


            elif command == "CWD":
                if args:
                    new_dir = args[0]
                    resolved_path = f"{current_dir}/{new_dir}".replace("//", "/")
                    if self.file_system.resolve_path(resolved_path):
                        current_dir = resolved_path
                        client_socket.sendall(b"250 Directory successfully changed.\r\n")
                    else:
                        client_socket.sendall(b"550 Failed to change directory.\r\n")
                else:
                    client_socket.sendall(b"501 Syntax error in parameters or arguments.\r\n")
            

            elif command == "LIST":
                try:
                    client_socket.sendall(b'150 Here comes the directory listing\r\n')
                    if not hasattr(self, "data_socket") or not self.data_socket:
                        client_socket.sendall(b"425 Can't open data connection.\r\n")
                        return
                    
                    data_transfer = None  # Asegurar que la variable existe
                    data_transfer, _ = self.data_socket.accept()

                    # Obtener la lista de archivos en el directorio actual
                    directory = self.file_system.resolve_path(current_dir)

                    if directory and isinstance(directory, Directory):
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

                        # Enviar la lista al cliente FTP
                        data_transfer.sendall(dir_list.encode())
                        data_transfer.close()
                        client_socket.sendall(b'226 Directory send OK\r\n')
                    else:
                        if data_transfer:
                            data_transfer.close()
                        client_socket.sendall(b"550 Failed to list directory.\r\n")

                except OSError as e:
                    client_socket.sendall(f'550 Failed to list directory: {e}\r\n'.encode())
                    print(f'Error listing directory: {e}')
                    if data_transfer:
                        data_transfer.close()

            
            elif command == "RETR":
                try:
                    filename = args[0]
                    resolved_path = f"{current_dir}/{filename}".replace("//", "/")
                    item = self.file_system.resolve_path(resolved_path)

                    if not item:
                        client_socket.sendall(b'550 File or directory not found.\r\n')
                        continue

                    if isinstance(item, File):
                        # Si es un archivo, se transfiere normalmente
                        client_socket.sendall(b'150 File status okay, about to open data connection.\r\n')
                        data_transfer, _ = self.data_socket.accept()

                        file_content = item.read()
                        if self.data_type == 'Binary':
                            file_content = file_content.encode()

                        chunk_size = 1024
                        start_position = self.restart_point
                        self.restart_point = 0  # Resetear el punto de reinicio

                        for i in range(start_position, len(file_content), chunk_size):
                            data_transfer.sendall(file_content[i:i + chunk_size])

                        data_transfer.close()
                        client_socket.sendall(b'226 Transfer complete.\r\n')

                    elif isinstance(item, Directory):
                        # Si es una carpeta, la comprimimos en memoria y la enviamos al cliente
                        client_socket.sendall(b'150 Directory transfer starting.\r\n')
                        data_transfer, _ = self.data_socket.accept()

                        # Crear un archivo ZIP en memoria
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            self.add_directory_to_zip(zip_file, item, "")

                        zip_buffer.seek(0)  # Volver al inicio del buffer antes de enviarlo

                        # Enviar los datos ZIP en bloques de 1024 bytes
                        chunk_size = 1024
                        while True:
                            chunk = zip_buffer.read(chunk_size)
                            if not chunk:
                                break
                            data_transfer.sendall(chunk)

                        data_transfer.close()
                        client_socket.sendall(b'226 Directory transfer complete.\r\n')

                except Exception as e:
                    client_socket.sendall(b'550 Failed to retrieve file or directory.\r\n')
                    print(f'Error retrieving file or directory: {e}')
                    if data_transfer:
                        data_transfer.close()


            elif command == "STOR":
                try:
                    filename = args[0]

                    if '.' in filename:
                        # Construir la ruta virtual completa (por ejemplo, "/current_dir/archivo.txt")
                        resolved_path = f"{current_dir}/{filename}".replace("//", "/")
                        
                        client_socket.sendall(b'150 File status okay; about to open data connection.\r\n')
                        data_transfer, _ = self.data_socket.accept()

                        # Recibir el archivo en un buffer de memoria
                        file_buffer = io.BytesIO()
                        while True:
                            up_data = data_transfer.recv(1024)
                            if not up_data:
                                break
                            file_buffer.write(up_data)
                        data_transfer.close()

                        file_buffer.seek(0)
                        # Convertir el contenido según el modo de transferencia (ASCII o Binary)
                        if self.data_type == 'Binary':
                            content = file_buffer.getvalue()  # se mantiene como bytes
                        else:
                            content = file_buffer.getvalue().decode()  # se convierte a texto

                        # Obtener el directorio virtual actual donde se almacenará el archivo
                        parent_directory = self.file_system.resolve_path(current_dir)
                        if parent_directory is None or not isinstance(parent_directory, Directory):
                            client_socket.sendall(b'550 Failed to store file.\r\n')
                        else:
                            # Crear el objeto File en memoria
                            new_file = File(filename, content)
                            # Guardarlo en la estructura del directorio virtual
                            parent_directory.contents[filename] = new_file
                            self.file_system.path_map[resolved_path] = new_file
                            client_socket.sendall(b'226 Transfer complete.\r\n')
                    else:
                        client_socket.sendall(b'550 Error: Only files are allowed.\r\n')
                except Exception as e:
                    client_socket.sendall(b'550 Failed to store file.\r\n')
                    print(f'Error storing file: {e}')
                    if data_transfer:
                        data_transfer.close()


            elif command == "QUIT":
                client_socket.sendall(b"221 Closing connection, goodbye.\r\n")
                break


            elif command =="ACCT":
                client_socket.sendall(b'211 Account status.\r\n')
                response += f'Name: {username}\r\n'
                if authenticated:
                    response += f'Password: {self.users[username]}\r\n'
                else:
                    response += f'Password: {self.admin[username]}\r\n'
                response += '211 End of account status.\r\n'


            elif command == "CDUP":
                # Si estamos en la raíz, no se puede subir más arriba
                if current_dir == "/":
                    client_socket.sendall(b'550 Already at root directory.\r\n')
                else:
                    # Obtener el nuevo directorio padre
                    parent_path = "/".join(current_dir.strip("/").split("/")[:-1])
                    parent_path = "/" if parent_path == "" else parent_path

                    # Verificar si el directorio padre existe en el sistema de archivos virtual
                    if self.file_system.resolve_path(parent_path):
                        current_dir = parent_path  # Actualizar la ruta actual
                        client_socket.sendall(b'200 Directory changed to parent directory.\r\n')
                    else:
                        client_socket.sendall(b'550 Failed to change directory.\r\n')


            elif command =="REIN":
                authenticated = False
                username = ''
                self.data_type = 'ASCII'
                self.restart_point = 0
                client_socket.sendall(b'220 Service ready for new user.\r\n')


            elif command =="PORT":
                try:
                    data = args[0].split(',')
                    host = '.'.join(data[:4])
                    port = int(data[4]) * 256 + int(data[5])
                    self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.data_socket.connect((host, port))
                    client_socket.sendall(b'200 PORT command successful.\r\n')
                except Exception as e:
                    client_socket.sendall(b'425 Can not open data connection.\r\n')
                    print(f'Error opening data connection: {e}')


            elif command =="PASV":
                try:
                    self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.data_socket.bind((self.host, 0))
                    self.data_port = self.data_socket.getsockname()[1]
                    self.data_socket.listen(1)
                    print(self.host)
                    host_bytes = self.host.split('.')
                    port_bytes = [self.data_port // 256, self.data_port % 256]
                    client_socket.sendall(f'227 Entering Passive Mode ({host_bytes[0]},{host_bytes[1]},{host_bytes[2]},{host_bytes[3]},{port_bytes[0]},{port_bytes[1]})\r\n'.encode())
                except Exception as e:
                    client_socket.sendall(b'425 Can not open data connection\r\n')
                    print(f'Error entering passive mode: {e}')


            elif command =="TYPE":
                data_type = args[0]
                if data_type == 'A':
                    self.data_type = 'ASCII'
                    client_socket.sendall(b'200 Type set to ASCII.\r\n')
                elif data_type == 'I':
                    self.data_type = 'Binary'
                    client_socket.sendall(b'200 Type set to Binary.\r\n')
                else:
                    client_socket.sendall(b'504 Type not implemented.\r\n')


            elif command =="STRU":
                structure_type = args[0]
                if structure_type == 'F':
                    client_socket.sendall(b'200 File structure set to file.\r\n')
                else:
                    client_socket.sendall(b'504 Structure not implemented.\r\n')


            elif command =="MODE":
                mode_type = args[0]
                if mode_type == 'S':
                    client_socket.sendall(b'200 Mode set to stream.\r\n')
                else:
                    client_socket.sendall(b'504 Mode not implemented.\r\n')

            
            elif command == "STOU":
                try:
                    filename = args[0]
                    name, ext = filename.rsplit(".", 1)

                    if '.' in filename:
                        filename = str(name)+ str(uuid.uuid1())
                        filename+= str(ext)
                        # Construir la ruta virtual completa (por ejemplo, "/current_dir/archivo.txt")
                        resolved_path = f"{current_dir}/{filename}".replace("//", "/")
                        
                        client_socket.sendall(b'150 File status okay; about to open data connection.\r\n')
                        data_transfer, _ = self.data_socket.accept()

                        # Recibir el archivo en un buffer de memoria
                        file_buffer = io.BytesIO()
                        while True:
                            up_data = data_transfer.recv(1024)
                            if not up_data:
                                break
                            file_buffer.write(up_data)
                        data_transfer.close()

                        file_buffer.seek(0)
                        # Convertir el contenido según el modo de transferencia (ASCII o Binary)
                        if self.data_type == 'Binary':
                            content = file_buffer.getvalue()  # se mantiene como bytes
                        else:
                            content = file_buffer.getvalue().decode()  # se convierte a texto

                        # Obtener el directorio virtual actual donde se almacenará el archivo
                        parent_directory = self.file_system.resolve_path(current_dir)
                        if parent_directory is None or not isinstance(parent_directory, Directory):
                            client_socket.sendall(b'550 Failed to store file.\r\n')
                        else:
                            # Crear el objeto File en memoria
                            new_file = File(filename, content)
                            # Guardarlo en la estructura del directorio virtual
                            parent_directory.contents[filename] = new_file
                            self.file_system.path_map[resolved_path] = new_file
                            client_socket.sendall(b'226 Transfer complete.\r\n')
                    else:
                        client_socket.sendall(b'550 Error: Only files are allowed.\r\n')
                except Exception as e:
                    client_socket.sendall(b'550 Failed to store file.\r\n')
                    print(f'Error storing file: {e}')
                    if data_transfer:
                        data_transfer.close()
            

            elif command == "APPE":
                filename = args[0]
                resolved_path = f"{current_dir}/{filename}".replace("//", "/")

                try:
                    client_socket.sendall(b'150 File status okay; about to open data connection.\r\n')
                    data_transfer, _ = self.data_socket.accept()

                    # Recibir los datos del cliente en memoria
                    file_buffer = io.BytesIO()
                    while True:
                        up_data = data_transfer.recv(1024)
                        if not up_data:
                            break
                        file_buffer.write(up_data)
                    data_transfer.close()

                    file_buffer.seek(0)
                    content = file_buffer.getvalue().decode() if self.data_type == "ASCII" else file_buffer.getvalue()

                    # Verificar si el archivo existe en el sistema de archivos virtual
                    file = self.file_system.resolve_path(resolved_path)

                    if file and isinstance(file, File):
                        file.append(content)  # Agregar contenido al final del archivo existente
                    else:
                        # Si el archivo no existe, crearlo
                        parent_directory = self.file_system.resolve_path(current_dir)
                        if parent_directory and isinstance(parent_directory, Directory):
                            new_file = File(filename, content)
                            parent_directory.contents[filename] = new_file
                            self.file_system.path_map[resolved_path] = new_file

                    client_socket.sendall(b'226 Append successful.\r\n')

                except Exception as e:
                    client_socket.sendall(b'550 Failed to append file.\r\n')
                    print(f'Error appending file: {e}')


            elif command =="ALLO":
                client_socket.sendall(b'200 Command not needed.\r\n')


            elif command =="REST":
                try:
                    byte_offset=args[0]
                    self.restart_point=byte_offset #!Debo de hacer algun tipo de verificacion??
                    client_socket.sendall(b"350 Restart marker accepted.\r\n")
                except:
                    client_socket.sendall(b"501 Syntax error in parameters.\r\n")


            elif command == "RNFR":
                filename = args[0]
                resolved_path = f"{current_dir}/{filename}".replace("//", "/")

                # Verificar si el archivo o directorio existe en la estructura en memoria
                item_to_rename = self.file_system.resolve_path(resolved_path)

                if item_to_rename:
                    self.path_to_change = resolved_path  # Guardar la ruta a renombrar
                    client_socket.sendall(b"350 Ready for RNTO.\r\n")
                else:
                    client_socket.sendall(b"550 File or directory not found.\r\n")


            elif command == "RNTO":
                if not self.path_to_change:
                    client_socket.sendall(b"503 RNFR required before RNTO.\r\n")
                    continue

                try:
                    new_name = args[0]
                    old_path = self.path_to_change

                    # Calcular el directorio padre a partir de la ruta antigua.
                    parts = old_path.strip("/").split("/")
                    if len(parts) == 1:
                        parent_path = "/"  # Si el elemento está en la raíz
                    else:
                        parent_path = "/" + "/".join(parts[:-1])
                    new_path = f"{parent_path}/{new_name}".replace("//", "/")
                    
                    # Obtener el directorio padre en el sistema virtual.
                    parent_directory = self.file_system.resolve_path(parent_path)
                    if not parent_directory or not isinstance(parent_directory, Directory):
                        client_socket.sendall(b"550 Failed to rename: parent directory not found.\r\n")
                        continue

                    # Extraer el nombre antiguo (última parte del old_path).
                    old_key = parts[-1]

                    # Verificar que el elemento exista en el directorio padre.
                    if old_key not in parent_directory.contents:
                        client_socket.sendall(b"550 File or directory not found in parent's directory.\r\n")
                        continue

                    # Obtener el objeto a renombrar.
                    item = parent_directory.contents[old_key]
                    
                    # Eliminar la entrada antigua en el directorio y en el mapa de rutas.
                    del parent_directory.contents[old_key]
                    del self.file_system.path_map[old_path]

                    # Actualizar el nombre del objeto.
                    item.name = new_name

                    # Insertar el objeto con el nuevo nombre y actualizar el mapa.
                    parent_directory.contents[new_name] = item
                    self.file_system.path_map[new_path] = item

                    client_socket.sendall(b"250 Requested file action completed.\r\n")
                    self.path_to_change = None
                except Exception as e:
                    client_socket.sendall(b"550 Rename failed.\r\n")
                    print(f"Error renaming file/directory: {e}")


            elif command =="ABOR":
                if self.data_socket:    
                    self.data_socket.close()
                    self.data_socket=None
                    client_socket.sendall(b"226 Closing data connection. Transfer aborted.\r\n")
                else:
                    client_socket.sendall(b"225 No transfer to abort.\r\n")
                    
            
            elif command == "DELE":
                try:
                    filename = args[0]
                    # Construir la ruta completa virtual del archivo
                    resolved_path = f"{current_dir}/{filename}".replace("//", "/")
                    
                    # Obtener el objeto a través del sistema virtual
                    item = self.file_system.resolve_path(resolved_path)
                    
                    # Verificar que el objeto existe y es un archivo
                    if item and isinstance(item, File):
                        result = self.file_system.rm(resolved_path)
                        if "exitosamente" in result:
                            client_socket.sendall(b"250 Requested file action okay, completed.\r\n")
                        else:
                            client_socket.sendall(b"550 File not found or permission denied.\r\n")
                    else:
                        client_socket.sendall(b"550 File not found or permission denied.\r\n")
                except Exception as e:
                    client_socket.sendall(b"501 Syntax error in parameters or arguments.\r\n")
                    print(f"Error in DELE: {e}")
                    

            elif command == "RMD":
                try:
                    dir_name = args[0]
                    # Construir la ruta virtual completa del directorio
                    resolved_path = f"{current_dir}/{dir_name}".replace("//", "/")
                    
                    # Obtener el objeto desde el sistema virtual
                    item = self.file_system.resolve_path(resolved_path)
                    
                    # Verificar que el objeto existe y es un directorio
                    if item and isinstance(item, Directory):
                        result = self.file_system.rm(resolved_path)
                        if "exitosamente" in result:
                            client_socket.sendall(b"250 Directory deleted successfully.\r\n")
                        else:
                            client_socket.sendall(b"550 Failed to delete directory.\r\n")
                    else:
                        client_socket.sendall(b"550 Directory not found.\r\n")
                except Exception as e:
                    client_socket.sendall(b"550 Failed to delete directory.\r\n")
                    print(f"Error in RMD: {e}")
                    

            elif command == "MKD":
                try:
                    dir_name = args[0]
                    # Construir la ruta virtual completa del nuevo directorio
                    resolved_path = f"{current_dir}/{dir_name}".replace("//", "/")
                    
                    result = self.file_system.mkdir(resolved_path)
                    if "exitosamente" in result:
                        client_socket.sendall(f'257 "{dir_name}" created.\r\n'.encode('utf-8'))
                    else:
                        client_socket.sendall(b"550 Directory creation failed (already exists).\r\n")
                except Exception as e:
                    client_socket.sendall(b"501 Syntax error in parameters or arguments.\r\n")
                    print(f"Error in MKD: {e}")
                    

            elif command == "NLST":
                try:
                    client_socket.sendall(b'150 Here comes the directory listing\r\n')
                    
                    # Determinar el directorio a listar:
                    # Si se proporciona un argumento, se utiliza; de lo contrario, se usa current_dir.
                    parts = data.split()
                    if len(parts) > 1:
                        extra_dir = parts[1]
                        # Construir la ruta virtual completa (suponiendo que extra_dir es relativa)
                        virtual_dir = f"{current_dir}/{extra_dir}".replace("//", "/")
                    else:
                        virtual_dir = current_dir

                    # Obtener el objeto directorio desde el sistema virtual
                    directory_obj = self.file_system.resolve_path(virtual_dir)
                    if not directory_obj or not isinstance(directory_obj, Directory):
                        client_socket.sendall(b'550 Directory not found.\r\n')
                        continue

                    # Obtener la lista de nombres (sin detalles adicionales)
                    file_list = directory_obj.list_contents()
                    # Crear una cadena con cada nombre separado por un salto de línea
                    dir_list = "\n".join(file_list) + "\r\n"

                    # Abrir la conexión de datos para enviar la lista
                    data_transfer, _ = self.data_socket.accept()
                    data_transfer.sendall(dir_list.encode())
                    data_transfer.close()

                    client_socket.sendall(b'226 Directory send OK\r\n')

                except Exception as e:
                    client_socket.sendall(f'550 Failed to list directory: {e}\r\n'.encode())
                    print(f'Error listing directory: {e}')
                    if data_transfer:
                        data_transfer.close()


            elif command =="SITE":
                client_socket.sendall(b"503 Command not implemented.")


            elif command =="SMNT":
                client_socket.sendall(b"503 Command not implemented.")


            elif command =="SYST":
                system_name = platform.system()
                client_socket.sendall(f'215 {system_name} Type: L8\r\n'.encode())


            elif command =="STAT":
                parts = args
        
                # STAT without arguments (server status)
                if len(parts) == 0:
                    client_socket.sendall(b"211-FTP Server Status:\r\n")
                    client_socket.sendall(b"Connected to "+ str(self.host).encode('utf-8') +b"\r\n")
                    client_socket.sendall(b"Current directory: " + current_dir.encode('utf-8') + b"\r\n")
                    client_socket.sendall(b"211 End of status.\r\n")
                else:  # STAT with a file/directory argument
                    target = os.path.join(current_dir, parts[0])
                    if os.path.exists(target):
                        details = self.get_file_info(target)
                        client_socket.sendall(b"213 " + details.encode('utf-8') + b"\r\n")
                    else:
                        client_socket.sendall(b"550 File or directory not found.\r\n")


            elif command =="HELP":
                client_socket.sendall(b'214 The following commands are recognized.\r\n')
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
                client_socket.sendall(response.encode())
                client_socket.sendall(b'214 Help OK.\r\n')


            elif command =="NOOP":
                client_socket.sendall(b"200 OK.\r\n")


            else:
                client_socket.sendall(b"502 Command not implemented.\r\n")
                print(f"comando no implementado {command}")

            self.file_system.save_to_json(FILESYSTEM_JSON)

        client_socket.close()
        print("Conexión cerrada")
    
    def add_directory_to_zip(self, zip_file, directory, parent_path):
        """
        Agrega el contenido de un directorio virtual a un archivo ZIP en memoria.

        :param zip_file: Objeto ZipFile en el que se añadirá el contenido.
        :param directory: Objeto Directory del sistema de archivos virtual.
        :param parent_path: Ruta relativa dentro del ZIP.
        """
        for name, item in directory.contents.items():
            zip_path = f"{parent_path}/{name}".strip("/")  # Ruta dentro del ZIP

            if isinstance(item, File):
                # Agregar archivos al ZIP con su contenido en memoria
                zip_file.writestr(zip_path, item.read())

            elif isinstance(item, Directory):
                # Agregar la carpeta al ZIP (sin contenido, solo para estructurar)
                zip_file.writestr(zip_path + "/", "")

                # Llamada recursiva para procesar subdirectorios
                self.add_directory_to_zip(zip_file, item, zip_path)

    def get_file_info(self, path):
    # """Generate file or directory information."""
        if os.path.isdir(path):
            return f"{path} is a directory."
        else:
            size = os.path.getsize(path)
            mtime = time.ctime(os.path.getmtime(path))
            return f"{path} Size: {size} bytes, Last Modified: {mtime}"

if __name__ == "__main__":
    ftp_server = FTPApiServer(HOST, PORT,{'user': 'user1234'})
    try:
        ftp_server.start()
    except KeyboardInterrupt:
        print("Servidor detenido")