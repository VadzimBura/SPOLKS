__author__ = 'vadzim'

import multiprocessing
import socket
from pool import Pool
from multiprocessing import Queue, Lock
from file_transmitter import FileTransmitter
from constants import Constants


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