__author__ = 'vadzim'

from datetime import datetime
import sys
import os
import select
import multiprocessing
import socket
from multiprocessing import Queue, Lock, Process
import argparse


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
        if package and package[0] == Constants.COMMAND_ESCAPE and package[4] == Constants.COMMAND_ESCAPE:
            command = package[1:4]
            payload = package[5:]
        else:
            command = ''
            payload = package

        return {
            'command': command,
            'payload': payload
        }

    @staticmethod
    def first(array, compare_field, comparator):
        for index, value in enumerate(array):
            if comparator(compare_field, value):
                return value, index
        return ()


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

            print "Received {0} Kb from {1}".format(Utils.to_kilobytes(bytes_received), server_address)
            sys.stdout.write('\033M')
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


class WorkerState:
    def __init__(self, process, state):
        self.process = process
        self.is_busy = state


class Pool:
    def __init__(self, pool_size=Constants.POOL_SIZE, target=None, args=()):
        self.args = args,
        self.target = target
        self.workers = self.init_workers(pool_size, target, args)

    def init_workers(self, pool_size, target, args):
        return [WorkerState(Process(target=target, args=args), Constants.WORKER_IDLE)
                for i in range(pool_size)]

    def change_state(self, worker_pid, worker_name, state):
        worker, index = Utils.first(self.workers, (worker_pid, worker_name), self.compare_worker)

        if not worker is None:
            self.workers[index].is_busy = state

    def extend_pool(self, append_size=Constants.POOL_SIZE):
        old_length = len(self.workers)
        self.workers.extend(self.init_workers(append_size, self.target, self.args[0]))
        return old_length, len(self.workers)

    def has_idle_workers(self):
        for w in self.workers:
            if w.is_busy == Constants.WORKER_IDLE:
                return True

        return False

    def start(self, start_index=0):
        for i, w in enumerate(self.workers):
            if i >= start_index:
                w.process.start()

    def join(self):
        for w in self.workers:
            w.process.join()

    @staticmethod
    def compare_worker(process1_info, worker_state):
        return process1_info[0] == worker_state.process.pid \
               or (worker_state.process.pid is None
                   and process1_info[1] == worker_state.process.name)


def request_handler(s, filename, queue, lock):
    current_process = multiprocessing.current_process()
    while True:
        client_socket, client_address = s.accept()
        lock.acquire()
        print "Worker {0} handles request from {1}\n".format(multiprocessing.current_process().pid,
                                                             client_address)
        lock.release()
        queue.put((current_process.pid, current_process.name, Constants.WORKER_BUSY))
        FileTransmitter.send_file_tcp(client_socket, filename, lock)
        queue.put((current_process.pid, current_process.name, Constants.WORKER_IDLE))
        lock.acquire()
        print "Worker {0} finish with the request from {1}\n".format(multiprocessing.current_process().pid,
                                                                     client_address)
        lock.release()


class ParallelServer:
    def __init__(self, s, filename):
        self.queue = Queue()
        self.lock = Lock()
        self.pool = Pool(Constants.POOL_SIZE, request_handler,
                         (s, filename, self.queue, self.lock))

    def start(self):
        self.pool.start()
        while True:
            # while not self.queue.empty():
            pid, name, state = self.queue.get()
            self.pool.change_state(pid, name, state)
            if not self.pool.has_idle_workers():
                old_length, _ = self.pool.extend_pool(Constants.POOL_SIZE)
                self.lock.acquire()
                print 'Extend pool size'
                self.lock.release()
                self.pool.start(old_length)

    def shutdown(self):
        self.pool.join()
        self.queue.close()


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