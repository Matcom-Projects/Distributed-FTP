import time
from itertools import takewhile
import operator
from collections import OrderedDict
from abc import abstractmethod, ABC



class IStorage(ABC):
    """
    Local storage for this node.
    IStorage implementations of get must return the same type as put in by set
    """

    @abstractmethod
    def __setitem__(self, key, value):
        """
        Set a key to the given value.
        """

    @abstractmethod
    def __getitem__(self, key):
        """
        Get the given key.  If item doesn't exist, raises C{KeyError}
        """

    @abstractmethod
    def get(self, key, default=None):
        """
        Get given key.  If not found, return default.
        """

    @abstractmethod
    def iter_older_than(self, seconds_old):
        """
        Return the an iterator over (key, value) tuples for items older
        than the given secondsOld.
        """

    @abstractmethod
    def __iter__(self):
        """
        Get the iterator for this storage, should yield tuple of (key, value)
        """


import os
import time
import uuid
from collections import OrderedDict

class ForgetfulStorage(IStorage):
    def __init__(self, ttl=604800, storage_dir="storage"):
        """
        By default, max age is a week.
        The `storage_dir` is the directory where the files will be saved.
        """
        self.data = OrderedDict()
        self.ttl = ttl
        self.storage_dir = storage_dir
        if not os.path.exists(storage_dir):
            print("Creando La carpeta  "+ storage_dir)
            os.makedirs(storage_dir)  # Create directory if it doesn't exist

    def __setitem__(self, key, value):
        # Save the timestamp and file name in the data store
        if key in self.data:
            file_path = self.data[key][1]
            os.remove(file_path)
            print(f"Previous file associated with key {hash(key)} deleted successfully")
            del self.data[key]  # Remove existing key if it already exists
        
        # Generate a unique file name (use UUID or key as the file name)
        file_name = os.path.join(self.storage_dir, f"{hash(key)}_{uuid.uuid4().hex}")
        
        # Save the content to a file
        with open(file_name, "wb") as f:
            f.write(value)  # Writing file content (assumed to be in binary form)
        
        
        self.data[key] = (time.monotonic(), file_name)  # Store timestamp and file path
        self.cull()  # Clean up expired items

    def cull(self):
        # Cull expired items based on TTL
        for _, _ in self.iter_older_than(self.ttl):
            # Delete the file and remove it from the data store
            key, file_path = self.data.popitem(last=False)
            os.remove(file_path)

    def get(self, key, default=None):
        self.cull()  # Clean up expired items
        if key in self.data:
            return self[key]
        
        return default

    def __getitem__(self, key):
        self.cull()  # Clean up expired items
        file_path = self.data[key][1]
        # Return the file path or file content
        with open(file_path, "rb") as f:
            return f.read()  # Return file content

    def __repr__(self):
        self.cull()  # Clean up expired items
        return repr(self.data)

    def iter_older_than(self, seconds_old):
        min_birthday = time.monotonic() - seconds_old
        zipped = self._triple_iter()
        matches = takewhile(lambda r: min_birthday >= r[1], zipped)
        return list(map(operator.itemgetter(0, 2), matches))

    def _triple_iter(self):
        ikeys = self.data.keys()
        ibirthday = map(operator.itemgetter(0), self.data.values())
        ivalues = map(operator.itemgetter(1), self.data.values())
        return zip(ikeys, ibirthday, ivalues)

    def __iter__(self):
        self.cull()  # Clean up expired items
        ikeys = self.data.keys()
        ivalues = map(operator.itemgetter(1), self.data.values())
        return zip(ikeys, ivalues)

