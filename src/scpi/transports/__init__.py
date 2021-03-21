"""Transport layers for the SCPI module"""
try:
    from .rs232 import RS232Transport
except:
    pass
from .tcp import TCPTransport
