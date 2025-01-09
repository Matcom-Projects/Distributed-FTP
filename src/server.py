import os
import socket
import threading
import platform
import uuid
import time
import stat

# Configuración del servidor
HOST = '127.0.0.1'
PORT = 21
ROOT_DIR = os.path.abspath("ftp_root")  # Directorio raíz para el FTP

# Crear el directorio raíz si no existe
os.makedirs(ROOT_DIR, exist_ok=True)

class FTPServer:
    def __init__(self, host, port,users):
        self.host = host
        self.port = port
        self.data_port=0
        self.data_type='ASCII'
        self.restart_point = 0
        self.users=users
        self.path_to_change=None
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.cwd=ROOT_DIR

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
                relative_dir = os.path.relpath(current_dir, os.path.join(os.getcwd(), self.cwd))
                client_socket.sendall(f"257 /{relative_dir} \r\n".encode())


            elif command == "CWD":
                if args:
                    new_dir = os.path.abspath(os.path.join(current_dir, args[0]))
                    if os.path.exists(new_dir) and os.path.isdir(new_dir):
                        current_dir = new_dir
                        client_socket.sendall(b"250 Directory successfully changed.\r\n")
                    else:
                        client_socket.sendall(b"550 Failed to change directory.\r\n")
                else:
                    client_socket.sendall(b"501 Syntax error in parameters or arguments.\r\n")


            elif command == "LIST":
                try:
                    client_socket.sendall(b'150 Here comes the directory listing\r\n')
                    data_transfer, _ = self.data_socket.accept()

                    # Obtener la lista de archivos en el directorio actual
                    files = os.listdir(current_dir)

                    # Obtener los detalles de cada archivo
                    file_details = ['Permissions  Links  Size           Last-Modified  Name']
                    for file in files:
                        stats = os.stat(os.path.join(current_dir, file))

                        # Convertir los detalles del archivo a la forma de salida de 'ls -l'
                        details = {
                            'mode': stat.filemode(stats.st_mode).ljust(11),
                            'nlink': str(stats.st_nlink).ljust(6),
                            'size': str(stats.st_size).ljust(5),
                            'mtime': time.strftime('%b %d %H:%M', time.gmtime(stats.st_mtime)).ljust(12),
                            'name': file
                        }
                        file_details.append('{mode}  {nlink} {size}          {mtime}   {name}'.format(**details))

                        # Enviar los detalles de los archivos
                    dir_list = '\n'.join(file_details) + '\r\n'
                    data_transfer.sendall(dir_list.encode())
                    data_transfer.close()
                    client_socket.sendall(b'226 Directory send OK\r\n')
                except Exception as e:
                    client_socket.sendall(f'550 Failed to list directory: {e}\r\n'.encode())
                    print(f'Error listing directory: {e}')
                    if data_transfer:
                        data_transfer.close()


            elif command == "RETR":
                filename = args[0]
                file_path = os.path.abspath(os.path.join(current_dir, filename))

                if not os.path.exists(file_path):
                    client_socket.sendall(b'550 File not found.\r\n')
                    continue

                try:  
                    client_socket.sendall(b'150 File status okay, about to open data connection.\r\n')
                    data_transfer, _ = self.data_socket.accept()

                    mode = 'rb' if self.data_type == 'Binary' else 'r'
                    with open(file_path, 'rb') as file:
                        file.seek(self.restart_point)
                        self.restart_point = 0

                        while True:
                            down_data = file.read(1024)
                            if not down_data:
                                break
                            data_transfer.sendall(down_data)
                                
                    data_transfer.close()
                    client_socket.sendall(b'226 Transfer complete.\r\n')

                except Exception as e:
                    client_socket.sendall(b'550 Failed to retrieve file.\r\n')
                    print(f'Error retrieving file: {e}')
                    if data_transfer:
                        data_transfer.close()


            elif command == "STOR":
                filename = args[0]
                file_path = os.path.abspath(os.path.join(current_dir, filename))

                try:
                    client_socket.sendall(b'150 File status okay; about to open data connection.\r\n')
                    data_transfer, _ = self.data_socket.accept()

                    mode = 'wb' if self.data_type == 'Binary' else 'w'
                    with open(file_path, 'wb') as file:
                        
                        while True:
                            up_data = data_transfer.recv(1024)
                            if not up_data:
                                break
                            file.write(up_data)

                    data_transfer.close()
                    client_socket.sendall(b'226 Transfer complete.\r\n')

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


            elif command =="CDUP":
                current_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
                print(current_dir)
                # Verificar que el directorio padre esté dentro del directorio raíz (ftp_root)
                if os.path.commonpath([current_dir, ROOT_DIR]) != ROOT_DIR:
                    current_dir=self.cwd
                client_socket.sendall(b'200 Directory changed to parent directory.\r\n')


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


            elif command =="STOU":
                filename = str(args[0])+ str(uuid.uuid1())
                file_path = os.path.abspath(os.path.join(current_dir, filename))

                try:
                    client_socket.sendall(b'150 File status okay; about to open data connection.\r\n')
                    data_transfer, _ = self.data_socket.accept()

                    mode = 'wb' if self.data_type == 'Binary' else 'w'
                    with open(file_path, mode) as file:
                        
                        while True:
                            up_data = data_transfer.recv(1024)
                            if not up_data:
                                break
                            if self.data_type == 'ASCII':
                                up_data = up_data.decode()
                            file.write(up_data)

                    data_transfer.close()
                    client_socket.sendall(b'226 Transfer complete.\r\n')

                except Exception as e:
                    client_socket.sendall(b'550 Failed to store file.\r\n')
                    print(f'Error storing file: {e}')
                    if data_transfer:
                        data_transfer.close()
                pass


            elif command =="APPE":
                filename = args[0]
                file_path = os.path.abspath(os.path.join(current_dir, filename))

                try:
                    client_socket.sendall(b'150 File status okay; about to open data connection.\r\n')
                    data_transfer, _ = self.data_socket.accept()

                    mode = 'a' #? Esto debiera ser suficiente para concatenar los datos en un  archivo
                            #? Debo de hacer algo si lo que vien es binario??z``
                    with open(file_path, mode) as file:
                        
                        while True:
                            up_data = data_transfer.recv(1024)
                            if not up_data:
                                break
                            if self.data_type == 'ASCII':
                                up_data = up_data.decode()
                            file.write(up_data)

                    data_transfer.close()
                    client_socket.sendall(b'226 Transfer complete.\r\n')

                except Exception as e:
                    client_socket.sendall(b'550 Failed to store file.\r\n')
                    print(f'Error storing file: {e}')
                    if data_transfer:
                        data_transfer.close()


            elif command =="ALLO":
                client_socket.sendall(b'200 Command not needed.\r\n')


            elif command =="REST":
                try:
                    byte_offset=args[0]
                    self.restart_point=byte_offset #!Debo de hacer algun tipo de verificacion??
                    client_socket.sendall(b"350 Restart marker accepted.\r\n")
                except:
                    client_socket.sendall(b"501 Syntax error in parameters.\r\n")
                


            elif command =="RNFR":
                filename = args[0]
                file_path = os.path.abspath(os.path.join(current_dir, filename))

                if not os.path.exists(file_path):
                    client_socket.sendall(b'550 File not found.\r\n')
                    continue
                self.path_to_change= file_path
                client_socket.sendall(b"350 Ready for RNTO.\r\n")
                pass


            elif command =="RNTO":
                try:
                    new_name= args[0]
                    os.rename(self.path_to_change, new_name)
                    client_socket.sendall(b"250 Requested file action completed.\r\n")
                    self.path_to_change = None
                except ValueError:
                    client_socket.sendall(b"501 Syntax error in parameters.\r\n")
                except FileNotFoundError:
                    client_socket.sendall(b"550 File not found.\r\n")



            elif command =="ABOR":
                if self.data_socket:    
                    self.data_socket.close()
                    self.data_socket=None
                    client_socket.sendall(b"226 Closing data connection. Transfer aborted.\r\n")
                else:
                    client_socket.sendall(b"225 No transfer to abort.\r\n")


            elif command =="DELE":
                try:
                    filename = args[0]
                    file_path = os.path.abspath(os.path.join(current_dir, filename))

                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        client_socket.sendall(b"250 Requested file action okay, completed.\r\n")
                    else:
                        client_socket.sendall(b"550 File not found or permission denied.\r\n")
                except ValueError:
                    client_socket.sendall(b"501 Syntax error in parameters or arguments.\r\n")
                


            elif command =="RMD":
                dir_name = args[0]
                directory_path = os.path.abspath(os.path.join(current_dir, dir_name))
                try:
                    os.rmdir(directory_path)
                    client_socket.sendall(b'250 Directory deleted successfully.\r\n')
                except Exception as e:
                    client_socket.sendall(b'550 Failed to delete directory.\r\n')


            elif command =="MKD":
                try:
                    dir_name = args[0]
                    directory_path = os.path.abspath(os.path.join(current_dir, dir_name))
                # Check if the directory already exists
                    if not os.path.exists(directory_path):
                        os.mkdir(directory_path)
                        client_socket.sendall(f'257 "{dir_name}" created.\r\n'.encode('utf-8'))
                    else:
                        client_socket.sendall(b"550 Directory creation failed (already exists).\r\n")
                except ValueError:
                    client_socket.sendall(b"501 Syntax error in parameters or arguments.\r\n")
                except PermissionError:
                    client_socket.sendall(b"550 Directory creation failed (permission denied).\r\n")


            elif command =="NLST":
                try:
                    client_socket.sendall(b'150 Here comes the directory listing\r\n')
                    extra_dir = data.split()[1]
                    data_transfer, _ = self.data_socket.accept()
                    dir_list = '\n'.join(os.listdir(os.path.join(current_dir, extra_dir))) + '\r\n'
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
                response=''                
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

        client_socket.close()
        print("Conexión cerrada")
        
    def get_file_info(self, path):
    # """Generate file or directory information."""
        if os.path.isdir(path):
            return f"{path} is a directory."
        else:
            size = os.path.getsize(path)
            mtime = time.ctime(os.path.getmtime(path))
            return f"{path} Size: {size} bytes, Last Modified: {mtime}"

if __name__ == "__main__":
    ftp_server = FTPServer(HOST, PORT,{'user': 'user1234'})
    try:
        ftp_server.start()
    except KeyboardInterrupt:
        print("Servidor detenido")