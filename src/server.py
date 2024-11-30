import os
import socket
import threading
import platform
import uuid

return_codes={
	100: "The requested action is being initiated, expect another reply before proceeding with a new command.",
	110: "Restart marker reply.",
	120: "Service ready in %s minutes.",
	125: "Data connection already open; transfer starting.",
	150: "File status okay; about to open data connection.",

	200: "Command okay.",
	202: "Command not implemented.",
	211: "System status.",
	212: "Directory status.",
	213: "File status.",
	214: "Help message.",
	215: "FTP server.",
	220: "Service ready for new user.",
	221: "Service closing control connection.",
	225: "Data connection open; no transfer in progress.",
	226: "Closing data connection.",
	227: "Entering Passive Mode.",
	230: "User logged in, proceed.",
	250: "Requested file action okay, completed.",
	257: "File created.",

	331: "User name okay, need password.",
	332: "Need account for login.",
	350: "Requested file action pending further information.",

	421: "Service not available, closing control connection.",
	425: "Can't open data connection.",
	426: "Connection closed; transfer aborted.",
	450: "Requested file action not taken.",
	451: "Requested action aborted. Local error in processing.",
	452: "Requested action not taken.",

	500: "Syntax error, command unrecognized.",
	501: "Syntax error in parameters or arguments.",
	502: "Command not implemented.",
	503: "Bad sequence of commands.",
	504: "Command not implemented for that parameter.",
	530: "Not logged in.",
	532: "Need account for storing files.",
	550: "Requested action not taken.",
	551: "Requested action aborted. Page type unknown.",
	552: "Requested file action aborted.",
	553: "Requested action not taken."
}

'''Las órdenes FTP son las siguientes:
SMNT <SP> <nombre-ruta> <CRLF>
STOU <CRLF>
APPE <SP> <nombre-ruta> <CRLF>
REST <SP> <marcador> <CRLF>
RNFR <SP> <nombre-ruta> <CRLF>
RNTO <SP> <nombre-ruta> <CRLF>
ABOR <CRLF>
DELE <SP> <nombre-ruta> <CRLF>
RMD  <SP> <nombre-ruta> <CRLF>
MKD  <SP> <nombre-ruta> <CRLF>
NLST [<SP> <nombre-ruta>] <CRLF>
SITE <SP> <cadena> <CRLF>
STAT [<SP> <nombre-ruta>] <CRLF>
'''

# Configuración del servidor
HOST = '127.0.0.1'
PORT = 21
ROOT_DIR = os.path.abspath("ftp_root")  # Directorio raíz para el FTP

# Crear el directorio raíz si no existe
os.makedirs(ROOT_DIR, exist_ok=True)

class FTPServer:
    def __init__(self, host, port,users,admin):
        self.host = host
        self.port = port
        self.data_port=0
        self.data_type='ASCII'
        self.restart_point = 0
        self.users=users
        self.admin=admin
        self.path_to_change=''
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
        response = ""
        authenticated = False
        authenticated_admin = False
        username = ''
        
        while True:
            data = client_socket.recv(1024).decode()
            if not data:
                break

            print(f"Comando recibido: {data.strip()}")
            command, *args = data.split()
            command = command.upper()
            response = ""

            if command == "USER":
                username = args[0]
                if username in self.users:
                    response = '331 User name okay, need password.\r\n'
                elif username in self.admin:
                    response= '331 Admin name okay, need password.\r\n'
                else:
                    response = '530 User incorrect.\r\n'


            elif command == "PASS":
                password = args[0]
                if self.admin.get(username) == password:
                    authenticated = True
                    response='230 User logged in.\r\n'
                elif self.users.get(username) == password:
                    authenticated_admin = True
                    response='230 Admin logged in.\r\n'
                else:
                    response='530 Password incorrect in.\r\n'


            elif not authenticated and not authenticated_admin:
                response = '530 Not logged in.\r\n'


            elif command == "PWD":
                relative_dir = os.path.relpath(current_dir, os.path.join(os.getcwd(), self.cwd))
                response = f'257 {relative_dir}\r\n'


            elif command == "CWD":
                if args:
                    new_dir = os.path.abspath(os.path.join(current_dir, args[0]))
                    if os.path.exists(new_dir) and os.path.isdir(new_dir):
                        current_dir = new_dir
                        response = "250 Directory successfully changed.\r\n"
                    else:
                        response = "550 Failed to change directory.\r\n"
                else:
                    response = "501 Syntax error in parameters or arguments.\r\n"


            elif command == "LIST":
                try:
                    response = "150 Here comes the directory listing.\r\n"
                    client_socket.send(response.encode())
                    data_connection, _ = self.data_socket.accept()

                    files = os.listdir(current_dir)
                    file_list = "\r\n".join(files) + "\r\n"
                    data_connection.send(file_list.encode())
                    data_connection.close()
                    response = "226 List of files sent successfully.\r\n"
                except Exception as e:
                    response = f"550 Error al listar archivos: {e}\r\n"


            elif command == "RETR":
                filename = args[0]
                file_path = os.path.abspath(os.path.join(current_dir, filename))

                if not os.path.exists(file_path):
                    response = '550 File not found.\r\n'
                    continue

                try:  
                    client_socket.sendall(b'150 File status okay; about to open data connection.\r\n')
                    data_transfer, _ = self.data_socket.accept()

                    mode = 'rb' if self.data_type == 'Binary' else 'r'
                    with open(file_path, mode) as file:
                        file.seek(self.restart_point)
                        self.restart_point = 0

                        while True:
                            down_data = file.read(1024)
                            if not down_data:
                                break
                            if self.data_type == 'ASCII':
                                down_data = down_data.encode()
                            data_transfer.sendall(down_data)
                                
                    data_transfer.close()
                    response ='226 Transfer complete.\r\n'

                except Exception as e:
                    response ='550 Failed to retrieve file.\r\n'
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
                    with open(file_path, mode) as file:
                        
                        while True:
                            up_data = data_transfer.recv(1024)
                            if not up_data:
                                break
                            if self.data_type == 'ASCII':
                                up_data = up_data.decode()
                            file.write(up_data)

                    data_transfer.close()
                    response = '226 Transfer complete.\r\n'

                except Exception as e:
                    response='550 Failed to store file.\r\n'
                    print(f'Error storing file: {e}')
                    if data_transfer:
                        data_transfer.close()


            elif command == "QUIT":
                response = "221 Closing connection, goodbye.\r\n"
                client_socket.send(response.encode())
                break


            elif command =="ACCT":
                response = '211 Account status.\r\n' 
                response += f'Name: {username}\r\n'
                if authenticated:
                    response += f'Password: {self.users[username]}\r\n'
                else:
                    response += f'Password: {self.admin[username]}\r\n'
                response += '211 End of account status.\r\n'


            elif command =="CDUP":
                current_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
                response = '200 Directory changed to parent directory.\r\n'


            elif command =="REIN":
                authenticated = False
                authenticated_admin=False
                username = ''
                self.data_type = 'ASCII'
                self.restart_point = 0
                response = '220 Service ready for new user.\r\n'


            elif command =="PORT":
                try:
                    data = args[0].split(',')
                    host = '.'.join(data[:4])
                    port = int(data[4]) * 256 + int(data[5])
                    self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.data_socket.connect((host, port))
                    response= '200 PORT command successful.\r\n'
                except Exception as e:
                    response = '425 Can not open data connection.\r\n'
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
                    response= f'227 Entering Passive Mode ({host_bytes[0]},{host_bytes[1]},{host_bytes[2]},{host_bytes[3]},{port_bytes[0]},{port_bytes[1]})\r\n'
                except Exception as e:
                    response= '425 Can not open data connection\r\n'
                    print(f'Error entering passive mode: {e}')


            elif command =="TYPE":
                data_type = args[0]
                if data_type == 'A':
                    self.data_type = 'ASCII'
                    response = '200 Type set to ASCII.\r\n'
                elif data_type == 'I':
                    self.data_type = 'Binary'
                    response = '200 Type set to Binary.\r\n'
                else:
                    response = '504 Type not implemented.\r\n'


            elif command =="STRU":
                structure_type = args[0]
                if structure_type == 'F':
                    response= '200 File structure set to file.\r\n'
                else:
                    response='504 Structure not implemented.\r\n'


            elif command =="MODE":
                mode_type = args[0]
                if mode_type == 'S':
                    response = '200 Mode set to stream.\r\n'
                else:
                    response = '504 Mode not implemented.\r\n'


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
                    response = '226 Transfer complete.\r\n'

                except Exception as e:
                    response='550 Failed to store file.\r\n'
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
                    response = '226 Transfer complete.\r\n'

                except Exception as e:
                    response='550 Failed to store file.\r\n'
                    print(f'Error storing file: {e}')
                    if data_transfer:
                        data_transfer.close()


            elif command =="ALLO":
                response = '200 Command not needed.\r\n'


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
                    response = '550 File not found.\r\n'
                    continue
                client_socket.sendall(b"350 Ready for RNTO.\r\n")
                pass


            elif command =="RNTO":
                pass


            elif command =="ABOR":
                pass


            elif command =="DELE":
                pass


            elif command =="RMD":
                pass


            elif command =="MKD":
                pass


            elif command =="NLST":
                pass


            elif command =="SITE":
                pass


            elif command =="SMNT":
                pass


            elif command =="SYST":
                system_name = platform.system()
                response = f'215 {system_name} Type: L8\r\n'


            elif command =="STAT":
                pass


            elif command =="HELP":
                response= '214 The following commands are recognized.\r\n'                
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
                response+='214 Help OK.\r\n'


            elif command =="NOOP":
                response = "200 OK.\r\n"


            else:
                response = "502 Command not implemented.\r\n"
            print(response,"RESS")
            client_socket.send(response.encode())

        client_socket.close()
        print("Conexión cerrada")

if __name__ == "__main__":
    ftp_server = FTPServer(HOST, PORT,{'user': 'user1234'},{'admin': 'admin1234'})
    try:
        ftp_server.start()
    except KeyboardInterrupt:
        print("Servidor detenido")