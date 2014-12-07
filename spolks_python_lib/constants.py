__author__ = 'vadzim'


class Constants:
    FILE_CHUNK_SIZE = 32
    DEFAULT_HOST = '127.0.0.1'
    DEFAULT_PORT = 3000
    DEFAULT_TIMEOUT = 60
    SERVER_ECHO = 'SERVER'
    OK_STATUS = 'OK'
    ERROR_STATUS = 'ERROR'
    MAX_CONN_ATTEMPTS = 5
    ACK = 'ACK'
    FIN = 'FIN'
    TCP_FIN = '\0\0\0\0\0'
    INIT_TRANSMIT = 'INT'
    COMMAND_ESCAPE = '!'
    POOL_SIZE = 1
    WORKER_BUSY = 1
    WORKER_IDLE = 0