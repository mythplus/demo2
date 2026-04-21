import os, sys
sys.path.insert(0, os.getcwd())

from server.services import webhook_service
from server.services import memory_service
from server.services import log_service
from server import app
print("all imports ok")
