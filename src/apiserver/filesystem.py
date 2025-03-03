import time
import json
import stat

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
        self.nlink = 2 

    def list_contents(self):
        return list(self.contents.keys())

    def to_dict(self):
        """Convierte el directorio en un diccionario JSON."""
        return {
            "type": "directory",
            "name": self.name,
            "created_at": self.created_at,
            "size": 0.0,
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
        directory.permissions = int(data["permissions"], 8)
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
        with open(filename, "w") as f:
            json.dump(self.root.to_dict(), f, indent=4)

    def load_from_json(self, filename):
        """Carga el sistema de archivos desde un archivo JSON."""

        with open(filename, "r") as f:
            data = json.load(f)
            self.root = Directory.from_dict(data)
            self.path_map = {"/": self.root}  # Reinicializar el mapa de rutas
            print("Sistema de archivos cargado exitosamente.")