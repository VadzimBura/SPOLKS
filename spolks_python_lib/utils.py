import argparse
from constants import Constants


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