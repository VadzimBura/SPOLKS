__author__ = 'vadzim'

import socket
from file_transmitter import FileTransmitter
from utils import Utils


def main():
    args = Utils.arg_parser()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    if args.server:
        s.bind((args.host, args.port_read))
        while True:
            print '\nServer mode'
            FileTransmitter.send_file_udp(s, args.file)
            print 'Done\n'
    else:
        print '\nClient mode'
        FileTransmitter.receive_file_udp(s, args.file, args.host, args.port)

    s.close()

if __name__ == '__main__':
    main()


