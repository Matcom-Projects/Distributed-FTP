import os
import socket
import threading
import platform

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
USER <SP> <nombre-usuario> <CRLF>
PASS <SP> <contraseña> <CRLF>
ACCT <SP> <información-cuenta> <CRLF>
CWD  <SP> <nombre-ruta> <CRLF>
CDUP <CRLF>
SMNT <SP> <nombre-ruta> <CRLF>
QUIT <CRLF>
REIN <CRLF>
PORT <SP> <dirIP-puerto> <CRLF>
PASV <CRLF>
ok        TYPE <SP> <código-tipo> <CRLF>
STRU <SP> <código-estructura> <CRLF>
MODE <SP> <código-modo> <CRLF>
RETR <SP> <nombre-ruta> <CRLF>
STOR <SP> <nombre-ruta> <CRLF>
STOU <CRLF>
APPE <SP> <nombre-ruta> <CRLF>
ALLO <SP> <entero-decimal>
    [<SP> R <SP> <entero-decimal>] <CRLF>
REST <SP> <marcador> <CRLF>
RNFR <SP> <nombre-ruta> <CRLF>
RNTO <SP> <nombre-ruta> <CRLF>
ABOR <CRLF>
DELE <SP> <nombre-ruta> <CRLF>
RMD  <SP> <nombre-ruta> <CRLF>
MKD  <SP> <nombre-ruta> <CRLF>
PWD  <CRLF>
LIST [<SP> <nombre-ruta>] <CRLF>
NLST [<SP> <nombre-ruta>] <CRLF>
SITE <SP> <cadena> <CRLF>
ok        SYST <CRLF>
STAT [<SP> <nombre-ruta>] <CRLF>
ok        HELP [<SP> <cadena>] <CRLF>
ok        NOOP <CRLF>
'''

# Configuración del servidor
HOST = '127.0.0.1'
PORT = 21
ROOT_DIR = os.path.abspath("ftp_root")  # Directorio raíz para el FTP

# Crear el directorio raíz si no existe
os.makedirs(ROOT_DIR, exist_ok=True)

class FTPServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.data_type='ASCII'
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"Servidor FTP iniciado en {self.host}:{self.port}")
        while True:
            client_socket, client_address = self.server_socket.accept()
            print(f"Conexión establecida con {client_address}")
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

    def handle_client(self, client_socket):
        cwd = ROOT_DIR
        client_socket.send(b"220 Servicio FTP listo\r\n")
        
        while True:
            data = client_socket.recv(1024).decode().strip()
            if not data:
                break

            print(f"Comando recibido: {data}")
            command, *args = data.split()
            command = command.upper()
            response = ""

            if command == "USER":
                pass
            elif command == "PASS":
                pass
            elif command == "PWD":
                pass
            elif command == "CWD":
                pass
            elif command == "LIST":
                pass
            elif command == "RETR":
                pass
            elif command == "STOR":
                pass
            elif command == "QUIT":
                pass
            elif command =="ACCT":
                pass
            elif command =="CDUP":
                pass
            elif command =="SMNT":
                pass
            elif command =="REIN":
                pass
            elif command =="PORT":
                pass
            elif command =="PASV":
                pass
            elif command =="TYPE":
                data_type = data.split()[1]
                if data_type == 'A':
                    self.data_type = 'ASCII'
                    response = '200 Type set to ASCII.\r\n'
                elif data_type == 'I':
                    self.data_type = 'Binary'
                    response = '200 Type set to Binary.\r\n'
                else:
                    response = '504 Type not implemented.\r\n'
            elif command =="STRU":
                pass
            elif command =="MODE":
                pass
            elif command =="STOU":
                pass
            elif command =="APPE":
                pass
            elif command =="ALLO":
                pass
            elif command =="REST":
                pass
            elif command =="RNFR":
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
                response = "200 OK\r\n"
            else:
                response = "502 Comando no implementado\r\n"

            client_socket.send(response.encode())

        client_socket.close()
        print("Conexión cerrada")

if __name__ == "__main__":
    ftp_server = FTPServer(HOST, PORT)
    try:
        ftp_server.start()
    except KeyboardInterrupt:
        print("Servidor detenido")