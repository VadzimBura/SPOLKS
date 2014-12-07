__author__ = 'vadzim'

# home/vadzim/Programming/spolks_python
import sys
import socket
import os
import select
from constants import Constants
from utils import Utils




class FileTransmitter:
    @staticmethod
    def send_file_tcp(s, filename, lock):
        sending_file = open(filename, 'rb')
        filesize = os.stat(filename).st_size
        client_address = s.getpeername()
        try:
            package = s.recv(Constants.FILE_CHUNK_SIZE)
            bytes_sent = int(package)
            sending_file.seek(bytes_sent)
            while True:
                data = sending_file.read(Constants.FILE_CHUNK_SIZE)
                if not data:
                    sending_file.close()
                    lock.acquire()
                    print "File sent to {0}".format(client_address)
                    sys.stdout.write('\033M')
                    lock.release()
                    break
                else:
                    s.send(data)

                bytes_sent += len(data)
                percent = int(float(bytes_sent) * 100 / float(filesize))

                # lock.acquire()
                # print "{0} / {1} Kb sent to client {2}({3}%)".format(Utils.to_kilobytes(bytes_sent),
                #                                                      Utils.to_kilobytes(filesize), client_address,
                #                                                      percent)
                # sys.stdout.write('\033M')
                # lock.release()
        except socket.error, value:
            print value
        except Exception, value:
            print value
        finally:
            s.close()


    @staticmethod
    def receive_file_tcp(s, filename):
        receiving_file = open(filename, 'ab')

        bytes_received = os.path.getsize(filename)
        s.settimeout(Constants.DEFAULT_TIMEOUT)
        server_address = s.getpeername()
        print "Already received {0} bytes".format(bytes_received)
        try:
            s.send(str(bytes_received))
        except Exception:
            print Exception.message
            return

        while True:
            response = s.recv(Constants.FILE_CHUNK_SIZE)
            if not response:
                print '\nFile received'
                receiving_file.close()
                break
            else:
                receiving_file.write(response)

            bytes_received += len(response)

            # print "Received {0} Kb from {1}".format(Utils.to_kilobytes(bytes_received), server_address)
            # sys.stdout.write('\033M')
        s.close()


    @staticmethod
    def send_file_with_oob_tcp(s, filename):
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
    def receive_file_with_oob_tcp(s, filename):
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
                    unpacked_package = Utils.unpack_package(package)

                    if not connections.has_key(client_address) or connections[client_address] is None:
                        connections[client_address] = open(filename, 'rb')

                    if unpacked_package['command'] == Constants.INIT_TRANSMIT:
                        bytes_sent = int(unpacked_package['payload'])
                        connections[client_address].seek(bytes_sent)
                        data = connections[client_address].read(Constants.FILE_CHUNK_SIZE)
                        if not data:
                            rd.sendto(Utils.pack_package(Constants.FIN, ''), client_address)
                            connections[client_address].close()
                            connections[client_address] = None
                        else:
                            rd.sendto(Utils.pack_package(Constants.ACK, data), client_address)

                    bytes_sent += len(data)
                    percent = int(float(bytes_sent) * 100 / float(filesize))

                    print "{0} / {1} Kb sent to client {2}({3}%)".format(Utils.to_kilobytes(bytes_sent),
                                                                         Utils.to_kilobytes(filesize), client_address,
                                                                         percent)
                    sys.stdout.write('\033M')

        except socket.error, value:
            print value
        except Exception, value:
            print value
        finally:
            s.close()

    @staticmethod
    def receive_file_multicast(s, filename, host, port):
        receiving_file = open(filename, 'ab')

        bytes_received = os.path.getsize(filename)
        s.settimeout(Constants.DEFAULT_TIMEOUT)
        while True:
            s.sendto(Utils.pack_package(Constants.INIT_TRANSMIT, str(bytes_received)), (host, port))
            response, server_address = s.recvfrom(Constants.FILE_CHUNK_SIZE)

            unpacked_response = Utils.unpack_package(response)
            if not unpacked_response['command'] == Constants.FIN:
                receiving_file.write(unpacked_response['payload'])
            else:
                print '\nFile received'
                receiving_file.close()
                break
            bytes_received += len(unpacked_response['payload'])

            print "Received {0} Kb from {1}".format(Utils.to_kilobytes(bytes_received), server_address)
            sys.stdout.write('\033M')
        s.close()
