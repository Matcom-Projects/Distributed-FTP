import socket
import re
import os
from termcolor import colored as col
import shlex

class FTPClient:
    """Clase para interactuar con un servidor FTP."""
    def __init__(self, host, port=21):
        self.host = host
        self.port = port
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.control_socket.settimeout(3)
    
        self.restart_point = 0
        self.data_type = 'ASCII'

    def connect(self):
        """Conecta al servidor FTP."""
        self.control_socket.connect((self.host, self.port))
        self.read_response()

    def read_response(self):
        """Lee la respuesta del servidor FTP."""
        response = ''
        while True:
            part = self.control_socket.recv(1024).decode()
            response += part
            if response.endswith('\r\n') or len(part) < 1024:
                break

        if response.startswith('4') or response.startswith('5'):
            print(col(response, "red"))
        else:
            print(col(response, "green"))
        
        return response

    def send_command(self, command):
        """Envía un comando al servidor FTP y devuelve la respuesta."""
        self.control_socket.sendall(f"{command}\r\n".encode())
        return self.read_response()

    def login(self, username, password):
        """Autentica al usuario en el servidor FTP."""
        try :
            self.send_command('USER ' + username)
            self.send_command('PASS ' + password)
        except Exception as e:
            print(col(f"Error al iniciar sesión: {e}", "red"))
            self.read_response()

    def pasv_mode(self):
        """Establece el modo PASV para la transferencia de datos."""
        try:
            response = self.send_command('PASV')

            if not response.startswith('227'):
                print(col("PASV mode setup failed.", "red"))
                return None
            
            ip_port_pattern = re.compile(r'(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)')
            ip_port_match = ip_port_pattern.search(response)
            if ip_port_match:
                ip_address = '.'.join(ip_port_match.groups()[:4])
                port = (int(ip_port_match.group(5)) << 8) + \
                    int(ip_port_match.group(6))
                data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                data_socket.settimeout(3)
                data_socket.connect((ip_address, port))
                return data_socket
            else:
                print(col("PASV mode setup failed.", "red"))
                return None
        except Exception as e:
            print(col(f"Error en el modo PASV: {e}", "red"))
            return None
        
    def active_mode(self):
        """Establece el modo activo para la transferencia de datos."""
        data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_socket.bind(('', 0))
        data_socket.listen(1)
        data_socket_ip, data_socket_port = data_socket.getsockname()
        ip_parts = data_socket_ip.split('.')
        port_parts = [str(data_socket_port >> 8), str(data_socket_port & 0xFF)]
        port_command = f"{','.join(ip_parts)},{','.join(port_parts)}"
        response = self.send_command(f'PORT {port_command}')
        print(response)
        if response.startswith('200'):
            return data_socket
        else:
            print("Active mode setup failed.")
            return None

    def list_files(self, directory="."):
        """Lista los archivos en el directorio especificado, devolviendo una lista con la distinción entre archivos y carpetas."""
        try:
            data_socket = self.pasv_mode()
            if data_socket is None:
                print(col("No se pudo establecer una conexión de datos.","red"))
                return
            
            self.send_command(f'LIST {directory}')
            data_response = ""
            while True:
                data_part = data_socket.recv(4096).decode()
                if not data_part:
                    break
                data_response += data_part
            data_socket.close()
            self.read_response()

            print(data_response)
    
        except Exception as e:
            print(f"Error al listar archivos: {e}")

    def simple_list_files(self, directory="."):
        """Lista los archivos en el directorio especificado, devolviendo una lista con los nombres de los archivos."""
        try:
            data_socket = self.pasv_mode()
            if data_socket is None:
                print(col("No se pudo establecer una conexión de datos.","red"))
                return
            self.send_command(f'NLST {directory}')
            data_response = ""
            while True:
                data_part = data_socket.recv(4096).decode()
                if not data_part:
                    break
                data_response += data_part
            data_socket.close()
            self.read_response()

            print(data_response)
    
        except Exception as e:
            print(col(f"Error al listar archivos: {e}", "red"))

    def change_directory(self, path):
        """Cambia el directorio actual en el servidor FTP."""
        self.send_command(f'CWD {path}')
    
    def change_directory_up(self):
        """Cambia al directorio padre."""
        self.send_command('CDUP')

    def make_directory(self, dirname):
        """Crea un nuevo directorio en el servidor FTP."""
        self.send_command(f'MKD {dirname}')

    def remove_directory(self, dirname):
        """Elimina un directorio en el servidor FTP."""
        self.send_command(f'RMD {dirname}')

    def delete_file(self, filename):
        """Intenta eliminar un archivo."""
        self.send_command(f'DELE {filename}')

    def rename_file(self, from_name, to_name):
        """Renombra un archivo en el servidor FTP."""
        self.send_command(f'RNFR {from_name}')
        self.send_command(f'RNTO {to_name}')

    def retrieve_file(self, filename, local_filename=''):
        """Descarga un archivo del servidor FTP."""
        if not local_filename:
            local_filename = filename
        
        try:
            data_socket = self.pasv_mode()
            if not data_socket:
                print(col("Error estableciendo modo PASV.","red"))
                return
            
            server_ans = self.send_command(f'RETR {filename}')

            if server_ans.startswith('550'):
                print(col(f"Error, file '{filename}' not found.","red"))
                return

            local_filename = os.path.join(os.getcwd(), 'Downloads', local_filename)
            if not os.path.exists(os.path.join(os.getcwd(), 'Downloads')):
                os.makedirs(os.path.join(os.getcwd(), 'Downloads'))

            with open(local_filename, 'wb') as file:
                while True:
                    data = data_socket.recv(1024)
                    if not data:
                        break
                    file.write(data)
            data_socket.close()
            self.read_response()
        
        except Exception as e:
            print(col(f"Error al descargar archivo: {e}", "red"))

        finally:
            if data_socket:
                data_socket.close()

    def store_file(self, local_filename, filename=''):
        """Sube un archivo al servidor FTP."""
        if not filename:
            filename = local_filename

        try:
            file_path = os.path.abspath(os.path.join(os.getcwd(), local_filename))
            
            if not os.path.exists(file_path):
                print(col(f"Error, file '{file_path}' not found.","red"))
                return
            
            data_socket = self.pasv_mode()
            if not data_socket:
                print("Error estableciendo modo PASV.")
            
            self.send_command(f'STOR {filename}')
            with open(local_filename, 'rb') as file:
                #Debe empezar a leer desde el restart_point
                file.seek(self.restart_point)
                self.restart_point = 0

                print('Subiendo archivo...')
                while True:
                    data = file.read(1024)
                    if not data:
                        break
                    data_socket.sendall(data)
            
            data_socket.close()
            self.read_response()
        
        except Exception as e:
            print(col(f"Error al subir archivo: {e}", "red"))
            if data_socket:
                data_socket.close()

    
    def store_unique_file(self, local_filename, filename=''):
        """Sube un archivo al servidor FTP con un nombre único."""
        if not filename:
            filename = local_filename

        try:
            file_path = os.path.abspath(os.path.join(os.getcwd(), local_filename))
            
            if not os.path.exists(file_path):
                print(col(f"Error, file '{file_path}' not found.","red"))
                return
            
            data_socket = self.pasv_mode()
            if not data_socket:
                print(col("Error estableciendo modo PASV.","red"))
                return
            
            self.send_command(f'STOU {filename}')
            with open(local_filename, 'rb') as file:
                file.seek(self.restart_point)
                self.restart_point = 0
                while True:
                    data = file.read(1024)
                    if not data:
                        break
                    data_socket.sendall(data)
            
            data_socket.close()
            self.read_response()
        
        except Exception as e:
            print(col(f"Error al subir archivo: {e}", "red"))
            if data_socket:
                data_socket.close()

    
    def append_file(self, local_filename, filename=''):
        """Añade un archivo al servidor FTP."""
        if not filename:
            filename = local_filename

        try:
            file_path = os.path.abspath(os.path.join(os.getcwd(), local_filename))
            
            if not os.path.exists(file_path):
                print(col(f"Error, file '{file_path}' not found.","red"))
                return
            
            data_socket = self.pasv_mode()
            if not data_socket:
                print(col("Error estableciendo modo PASV.","red"))
                return
            
            self.send_command(f'APPE {filename}')
            with open(local_filename, 'rb') as file:
                file.seek(self.restart_point)
                self.restart_point = 0
                while True:
                    data = file.read(1024)
                    if not data:
                        break
                    data_socket.sendall(data)
        
            data_socket.close()
            self.read_response()
        
        except Exception as e:
            print(col(f"Error al añadir archivo: {e}", "red"))


    def print_working_directory(self):
        """Imprime el directorio de trabajo actual en el servidor FTP."""
        self.send_command('PWD')
    
    def system(self):
        """Devuelve el sistema operativo del servidor FTP."""
        self.send_command('SYST')
    
    def help(self, command=''):
        """Devuelve la lista de comandos soportados por el servidor FTP."""
        response = self.send_command(f'HELP {command}')

        if response.count('214') == 2:
            return

        # Leer todas las líneas de la respuesta
        while True:
            response = self.read_response()
            if '214' in response:
                break
    
    def noop(self):
        """Comando NOOP."""
        self.send_command('NOOP')
    
    def status(self):
        """Devuelve el estado de la conexión con el servidor FTP."""
        response = self.send_command(f'STAT {command}')

        # If '211' is twice in response then return
        if response.count('211') == 2:
            return

        # Leer todas las líneas de la respuesta
        while True:
            response = self.read_response()
            if '211' in response:
                break
    
    def abort(self): #wtf asi y ya??
        """Aborta la transferencia de datos."""
        self.send_command('ABOR')

    def account_info(self, account_info): 
        """Envía la información de la cuenta al servidor FTP."""
        self.send_command(f'ACCT {account_info}')
    
    def set_transfer_start_position(self, position):
        """Establece la posición de inicio para la descarga de archivos."""
        self.restart_point = int(position)
        self.send_command(f'REST {position}')

    def site_command(self, command):
        """Envía un comando SITE al servidor FTP."""
        self.send_command(f'SITE {command}')
    
    def allocate_space(self, bytes):
        """Reserva espacio en el servidor FTP."""
        self.send_command(f'ALLO {bytes}')
    
    def structure_mount(self, path):
        """Monta una estructura en el servidor FTP."""
        self.send_command(f'SMNT {path}')
    
    def reinitialize(self):
        """Reinicia la conexión con el servidor FTP."""
        self.restart_point = 0
        self.send_command('REIN')

    def file_structure(self, structure):
        """Establece la estructura de un archivo."""
        self.send_command(f'STRU {structure}')
    
    def transfer_mode(self, mode):
        """Establece el modo de transferencia."""
        self.send_command(f'MODE {mode}')
    
    def file_type(self, type):
        """Establece el tipo de archivo."""
        self.send_command(f'TYPE {type}')
        if type == 'I':
            self.data_type = 'BINARY'
        elif type == 'A':
            self.data_type = 'ASCII'
        

    def quit(self):
        """Cierra la sesión y la conexión con el servidor FTP."""
        self.send_command('QUIT')
        self.control_socket.close()
       


if __name__ == "__main__":

    while True:
        print(col("FTP CLient v1.0","blue"))
        print("Servidores FTP de prueba:\nftp.dlptest.com ('dlpuser' 'rNrKYTX9g7z3RgJRmxWuGHbeu')\ntest.rebex.net ('demo' 'password')")
        ftp_host = input(col("Ingrese la dirección del servidor FTP: ","blue"))
        try:
            ftp = FTPClient(ftp_host)
            ftp.connect()
            break
        except Exception as e:
            print(col(f"Error: {e}","red"))


    while True:
        try:
            user_input = input(col("ftp>> ","blue"))

            command_parts = shlex.split(user_input)
            command = command_parts[0].lower()
            args = command_parts[1:]
            print(command_parts)

            if command == 'login':
                ftp.login(*args)
            elif command == 'ls':
                ftp.list_files(*args)
            elif command == 'nls':
                ftp.simple_list_files(*args)
            elif command == 'cd':
                ftp.change_directory(*args)
            elif command == 'cdup':
                ftp.change_directory_up(*args)
            elif command == 'pwd':
                ftp.print_working_directory(*args)
            elif command == 'mkdir':
                ftp.make_directory(*args)
            elif command == 'rd':
                ftp.remove_directory(*args)
            elif command == 'rf':
                ftp.delete_file(*args)
            elif command == 'rename':
                ftp.rename_file(*args)
            elif command == 'dow':
                ftp.retrieve_file(*args)
            elif command == 'upl':
                ftp.store_file(*args)
            elif command == 'uplu':
                ftp.store_unique_file(*args)
            elif command == 'app':
                ftp.append_file(*args)
            elif command == 'sys':
                ftp.system(*args)
            elif command == 'help':
                ftp.help(*args)
            elif command == 'noop':
                ftp.noop(*args)
            elif command == 'stat':
                ftp.status(*args)
            elif command == 'abort':
                ftp.abort(*args)
            elif command == 'acct':
                ftp.account_info(*args)
            elif command == 'rest':
                ftp.set_transfer_start_position(*args)
            elif command == 'site':
                ftp.site_command(*args)
            elif command == 'allo':
                ftp.allocate_space(*args)
            elif command == 'smnt':
                ftp.structure_mount(*args)
            elif command == 'rein':
                ftp.reinitialize(*args)
            elif command == 'stru':
                ftp.file_structure(*args)
            elif command == 'mode':
                ftp.transfer_mode(*args)
            elif command == 'type':
                ftp.file_type(*args)
            elif command == 'quit':
                ftp.quit(*args)
                break
            else:
                print(col("Comando no reconocido. Por favor, inténtelo de nuevo.","red"))
        except Exception as e:
            print(col(f"Error: {e}","red"))