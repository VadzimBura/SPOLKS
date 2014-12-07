__author__ = 'vadzim'

from multiprocessing import Process
from constants import Constants
from utils import Utils


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
        return process1_info[0] == worker_state.process.pid\
               or (worker_state.process.pid is None
                   and process1_info[1] == worker_state.process.name)