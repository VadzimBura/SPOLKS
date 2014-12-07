__author__ = 'vadzim'

import socket
from datetime import datetime
from file_transmitter import FileTransmitter
from utils import Utils
from parallel_server import ParallelServer


def main():
    args = Utils.arg_parser()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    if args.server:
        s.bind((args.host, args.port))
        s.listen(1)
        print '\nServer mode'
        server = ParallelServer(s, args.file)
        server.start()
        server.shutdown()
    else:
        print '\nClient mode'
        s.connect((args.host, args.port))
        FileTransmitter.receive_file_tcp(s, str(datetime.now().time()))
    s.close()

if __name__ == '__main__':
    main()