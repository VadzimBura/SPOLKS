__author__ = 'vadzim'

import sys
import socket
import os
import select
import argparse


class Constants:
    FILE_CHUNK_SIZE = 1024
    DEFAULT_HOST = '127.0.0.1'
    DEFAULT_PORT = 3000
    DEFAULT_TIMEOUT = 60
    SERVER_ECHO = 'SERVER'
    OK_STATUS = 'OK'
    ERROR_STATUS = 'ERROR'
    MAX_CONN_ATTEMPTS = 5
    ACK = 'ACK'
    FIN = 'FIN'
    INIT_TRANSMIT = 'INT'
    COMMAND_ESCAPE = '!'


class Utils:
    @staticmethod
    def arg_parser():
        parser = argparse.ArgumentParser()
        group = parser.add_mutually_exclusive_group()
        group.add_argument('-s', '--server', help='Run as server', action='store_true')
        group.add_argument('-c', '--client', help='Run as client', action='store_true')
        parser.add_argument('-hn', '--host', help='Destination host (client mode)', default='127.0.0.1')
        parser.add_argument('-p', '--port', type=int, help='Port to listen/connect to', default=3000)
        parser.add_argument('-u', '--udp', type=bool, help='Use UDP protocol', default=False)
        parser.add_argument('-pr', '--port_read', type=int, help='Port to read from when using UDP', default=3000)
        parser.add_argument('-pw', '--port_write', type=int, help='Port to write in when using UDP', default=3001)
        parser.add_argument('-f', '--file', help='File to send (server mode)', default='test.test')
        return parser.parse_args()

    @staticmethod
    def to_kilobytes(number):
        return number / 1024

    @staticmethod
    def pack_package(command, data):
        if not command is None:
            return "{0}{1}{0}{2}".format(Constants.COMMAND_ESCAPE, command, data)
        else:
            return data

    @staticmethod
    def unpack_package(package):
        if package[0] == Constants.COMMAND_ESCAPE and package[4] == Constants.COMMAND_ESCAPE:
            command = package[1:4]
            payload = package[5:]
        else:
            command = ''
            payload = package

        return {
            'command': command,
            'payload': payload
        }


def establish_connection(s, host, port):
    if s.recvfrom(Constants.FILE_CHUNK_SIZE)[0] != Constants.SERVER_ECHO:
        return False
    s.sendto(Constants.OK_STATUS, (host, port))
    return True


class FileTransmitter:
    @staticmethod
    def send_file_tcp(s, filename):
        sending_file = open(filename, 'rb')
        filesize = os.stat(filename).st_size
        oob_sent = 0
        try:
            bytes_sent = int(s.recv(Constants.FILE_CHUNK_SIZE))
            print "Already sent {0} / {1}".format(bytes_sent, filesize)
        except:
            print 'Lost Connection'
            return 0
        sending_file.seek(int(bytes_sent), 0)

        while True:
            chunk = sending_file.read(Constants.FILE_CHUNK_SIZE)
            if not chunk:
                break
            try:
                s.settimeout(Constants.DEFAULT_TIMEOUT)
                s.send(chunk)
            except socket.error:
                print 'Transfer fail'
                return 0
            bytes_sent += Constants.FILE_CHUNK_SIZE
            percent = int(float(bytes_sent) * 100 / float(filesize))
            print "{0} / {1} Kb sent ({2}%)".format(Utils.to_kilobytes(bytes_sent),
                                                    Utils.to_kilobytes(filesize), percent)
            sys.stdout.write('\033M')
            if (percent % 10 == 0) & (oob_sent != percent) & (percent < 91):
                oob_sent = percent
                sys.stdout.write('\033D')
                print '\033[37;1;41m Urgent flag sent at {0}% \033[0m'.format(percent)
                s.send(b'{}'.format(percent / 10), socket.MSG_OOB)

        sending_file.close()

    @staticmethod
    def receive_file_tcp(s, filename):
        receiving_file = open(filename, 'ab')

        bytes_received = os.path.getsize(filename)
        s.settimeout(Constants.DEFAULT_TIMEOUT)
        print "Already received {0}".format(bytes_received)
        try:
            s.send(str(bytes_received))
        except:
            print 'Lost Connection'
            return 0

        while True:
            try:
                oob = s.recv(2, socket.MSG_OOB)
            except socket.error, value:
                oob = None
            if oob:
                print '\033[0;32m OOB data: {0} Kb ({1}0%) received \033[0m' \
                    .format(Utils.to_kilobytes(bytes_received), oob)
            else:
                chunk = s.recv(Constants.FILE_CHUNK_SIZE)
                bytes_received += Constants.FILE_CHUNK_SIZE
                receiving_file.write(chunk)
            if not chunk:
                break
        receiving_file.close()

    @staticmethod
    def send_file_udp_m(s, filename, host, port):
        sending_file = open(filename, 'rb')
        filesize = os.stat(filename).st_size
        try:
            if not establish_connection(s, host, port):
                return
            s.settimeout(Constants.DEFAULT_TIMEOUT)

            bytes_sent = int(s.recvfrom(Constants.FILE_CHUNK_SIZE)[0])
            s.sendto(Constants.OK_STATUS, (host, port))
            print "Already sent {0} / {1}".format(bytes_sent, filesize)
        except socket.error:
            print socket.error
            return
        sending_file.seek(int(bytes_sent), 0)

        while True:
            chunk = sending_file.read(Constants.FILE_CHUNK_SIZE)
            if not chunk:
                break
            try:
                s.sendto(Constants.SERVER_ECHO, (host, port))
                if s.recvfrom(Constants.FILE_CHUNK_SIZE)[0] != Constants.OK_STATUS:
                    return
                s.sendto(chunk, (host, port))
                if s.recvfrom(Constants.FILE_CHUNK_SIZE)[0] != Constants.OK_STATUS:
                    return
            except socket.error:
                print 'Transfer fail'
                return
            bytes_sent += Constants.FILE_CHUNK_SIZE
            percent = int(float(bytes_sent) * 100 / float(filesize))

            print "{0} / {1} Kb sent ({2}%)".format(Utils.to_kilobytes(bytes_sent),
                                                    Utils.to_kilobytes(filesize), percent)
            sys.stdout.write('\033M')
        sending_file.close()

    @staticmethod
    def receive_file_udp_m(s, filename, host, port):
        receiving_file = open(filename, 'ab')
        bytes_received = os.path.getsize(filename)
        print "Already received {0} Kb".format(Utils.to_kilobytes(bytes_received))
        try:
            s.sendto(Constants.SERVER_ECHO, (host, port))
            if s.recvfrom(Constants.FILE_CHUNK_SIZE)[0] != Constants.OK_STATUS:
                return
            s.settimeout(Constants.DEFAULT_TIMEOUT)
            s.sendto(str(bytes_received), (host, port))
            if s.recvfrom(Constants.FILE_CHUNK_SIZE)[0] != Constants.OK_STATUS:
                return
        except socket.error:
            print socket.error
            return

        while True:
            try:
                if not establish_connection(s, host, port):
                    return
                chunk = s.recvfrom(Constants.FILE_CHUNK_SIZE)[0]
                s.sendto(Constants.OK_STATUS, (host, port))
                bytes_received += Constants.FILE_CHUNK_SIZE

                if not chunk:
                    break
                receiving_file.write(chunk)
                print "Received {0} Kb".format(Utils.to_kilobytes(bytes_received))
                sys.stdout.write('\033M')
            except socket.error:
                return
        receiving_file.close()

    @staticmethod
    def send_file_udp(s, filename):
        bytes_sent = 0

        sending_file = open(filename, 'rb')
        filesize = os.stat(filename).st_size

        while True:
            package, client_address = s.recvfrom(Constants.FILE_CHUNK_SIZE)
            unpacked_package = Utils.unpack_package(package)

            if unpacked_package['command'] == Constants.INIT_TRANSMIT:
                bytes_sent = int(unpacked_package['payload'])
                sending_file.seek(bytes_sent)
                data = sending_file.read(Constants.FILE_CHUNK_SIZE)
                if not data:
                    s.sendto(Utils.pack_package(Constants.FIN, ''), client_address)
                    sending_file.close()
                    break
                else:
                    s.sendto(Utils.pack_package(Constants.ACK, data), client_address)

            package, client_address = s.recvfrom(Constants.FILE_CHUNK_SIZE)
            unpacked_package = Utils.unpack_package(package)

            if unpacked_package['command'] == Constants.ACK:
                bytes_sent += len(data)
                percent = int(float(bytes_sent) * 100 / float(filesize))

                print "{0} / {1} Kb sent ({2}%)".format(Utils.to_kilobytes(bytes_sent),
                                                        Utils.to_kilobytes(filesize), percent)

    @staticmethod
    def receive_file_udp(s, filename, host, port):
        receiving_file = open(filename, 'ab')

        bytes_received = os.path.getsize(filename)
        s.settimeout(Constants.DEFAULT_TIMEOUT)
        while True:
            s.sendto(Utils.pack_package(Constants.INIT_TRANSMIT, str(bytes_received)), (host, port))
            response, _ = s.recvfrom(Constants.FILE_CHUNK_SIZE)

            unpacked_response = Utils.unpack_package(response)
            if not unpacked_response['command'] == Constants.FIN:
                receiving_file.write(unpacked_response['payload'])
            else:
                print 'File received'
                receiving_file.close()
                break
            bytes_received += len(unpacked_response['payload'])
            s.sendto(Utils.pack_package(Constants.ACK, ''), (host, port))

            print "Received {0} Kb".format(Utils.to_kilobytes(bytes_received))
            sys.stdout.write('\033M')
        s.close()

    @staticmethod
    def send_file_multicast(s, filename):
        connections = {}
        filesize = os.stat(filename).st_size
        try:
            while True:
                readable, _, _ = select.select([s], [], [])
                for rd in readable:
                        bytes_sent = 0
                        package, client_address = s.recvfrom(Constants.FILE_CHUNK_SIZE)
                        key = ''.join(map(str, client_address))
                        unpacked_package = Utils.unpack_package(package)
                        print client_address
                        if not connections.has_key(key) or connections[key] is None:
                            connections[key] = open(filename, 'rb')

                        if unpacked_package['command'] == Constants.INIT_TRANSMIT:
                            bytes_sent = int(unpacked_package['payload'])
                            connections[key].seek(bytes_sent)
                            data = connections[key].read(Constants.FILE_CHUNK_SIZE)
                            if not data:
                                rd.sendto(Utils.pack_package(Constants.FIN, ''), client_address)
                                connections[key].close()
                                connections[key] = None
                            else:
                                rd.sendto(Utils.pack_package(Constants.ACK, data), client_address)

                        # package, client_address = s.recvfrom(Constants.FILE_CHUNK_SIZE)
                        # unpacked_package = Utils.unpack_package(package)
                        #
                        # if unpacked_package['command'] == Constants.ACK \
                        #         and not connections[key] is None:
                        bytes_sent += len(data)
                        percent = int(float(bytes_sent) * 100 / float(filesize))

                        print "{0} / {1} Kb sent to client {2}({3}%)".format(Utils.to_kilobytes(bytes_sent),
                                                                             Utils.to_kilobytes(filesize), key,
                                                                             percent)
            s.close()
        except socket.error, value:
            print value
        except Exception, value:
            print value
        except socket.EBADF:
            print 'FD'


    @staticmethod
    def receive_file_multicast(s, filename, host, port):
        receiving_file = open(filename, 'ab')

        bytes_received = os.path.getsize(filename)
        # s.settimeout(Constants.DEFAULT_TIMEOUT)
        while True:
            s.sendto(Utils.pack_package(Constants.INIT_TRANSMIT, str(bytes_received)), (host, port))
            response, server_address = s.recvfrom(Constants.FILE_CHUNK_SIZE)

            unpacked_response = Utils.unpack_package(response)
            if not unpacked_response['command'] == Constants.FIN:
                receiving_file.write(unpacked_response['payload'])
            else:
                print 'File received'
                receiving_file.close()
                break
            bytes_received += len(unpacked_response['payload'])
            # s.sendto(Utils.pack_package(Constants.ACK, ''), server_address)

            print "Received {0} Kb".format(Utils.to_kilobytes(bytes_received))
            sys.stdout.write('\033M')
            # s.close()


def main():
    args = Utils.arg_parser()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    if args.server:
        s.bind((args.host, args.port))
        print '\nServer mode'
        while True:
            FileTransmitter.send_file_multicast(s, args.file)
    else:
        print '\nClient mode'
        FileTransmitter.receive_file_multicast(s, args.file, args.host, args.port)

    s.close()

if __name__ == '__main__':
    main()