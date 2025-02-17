""" Quake2 specific RCON library using pyrcon
by texnofobix
MIT license
"""
import threading as thread
import socket
import time

REPORT_LINE = '--- ----- ---- --------------- ------- '
REPORT_LINE += '--------------------- -------- ---'

class RconError(Exception):
    """Raised whenever a RCON command cannot be evaluated"""
    pass


class RConnection(object):
    """
    Base class for an RCON "connection", even though RCON is technically
    connectionless (UDP) Initialization takes an address, port, and password
    """
    _host = ''  # host where the server is
    _port = 27960  # virtual port where to forward rcon commands
    _password = ''  # rcon password of the server
    _timeout = 0.5  # default socket timeout
    _rconsendheader = b'\xFF\xFF\xFF\xFF'
    _rconsendstring = 'rcon {0} {1}'  # rcon command pattern
    _rconreplystring = '\xFF\xFF\xFF\xFFprint\n'  # rcon response header
    _badrcon_replies = [
        'Bad rconpassword.',
        'Invalid password.',
        'print\nBad rcon_password.\n'
    ]
    # custom timeouts
    _long_commands_timeout = {'map': 5.0, 'fdir': 5.0, 'dir maps/': 5.0}

    def __init__(self, host, port, password=None):
        """
        :param host: The ip/domain where to send RCON commands
        :param port: The port where to send RCON commands
        :param password: The RCON password
        :raise RconError: If it's not possible to setup the RCON interface
        """
        self.host = host
        self.port = port
        self.password = password
        self.lock = thread.Lock()
        self.socket = socket.socket(type=socket.SOCK_DGRAM)
        self.socket.connect((self.host, self.port))
        self.test_password()

    def _get_host(self):
        return self._host

    def _set_host(self, value):
        try:
            self._host = value.strip()
        except AttributeError:
            raise RconError('expecting hostname')

    """:type : str"""
    host = property(_get_host, _set_host)

    def _get_password(self):
        return self._password

    def _set_password(self, value):
        if value is not None:
            self._password = value.strip()

    """:type : str"""
    password = property(_get_password, _set_password)

    def _get_port(self):
        return self._port

    def _set_port(self, value):
        try:
            self._port = int(value)
        except ValueError:
            raise RconError('bad rcon port supplied')

    """:type : int"""
    port = property(_get_port, _set_port)

    def __enter__(self):
        if self.test():
            return self

    def __exit__(self, type, value, traceback):
        try:
            self.socket.close()
        except (AttributeError, socket.error):
            pass
        finally:
            return traceback or True

    def test_password(self):
        """
        Test the RCON connection
        :raise RconError: When an invalid RCON password is supplied
        """
        response = self.send('status')
        if response in self._badrcon_replies:
            self._password = None
            raise RconError('bad rcon password supplied')
        return True

    def _recvall(self, timeout=0.5):
        """
        Receive the RCON command response
        :param timeout: The timeout between consequent data receive
        :return str: The RCON command response with header stripped out
        """
        response = ''
        self.socket.setblocking(False)
        start = time.time()
        while True:
            if response and time.time() - start > timeout:
                break
            elif time.time() - start > timeout * 2:
                break

            try:
                data = self.socket.recv(4096)[4:]
                if data:
                    response += data.decode('utf-8')
                    start = time.time()
                else:
                    time.sleep(0.1)
            except socket.error:
                pass

        return response

    def send(self, data):
        """
        Send a command over the socket. If password is set use rcon
        :param data: The command to send
        :raise RconError: When it's not possible to evaluate the command
        :return str: The server response to the RCON command
        """
        try:
            if not data:
                raise RconError('no command supplied')
            with self.lock:
                if self.password != '':
                    data = self._rconsendstring.format(self.password, data)
            self.socket.send(self._rconsendheader + bytes(data, 'utf-8'))
        except socket.error as e:
            raise RconError(e.message, e)
        else:
            timeout = self._timeout
            command = data.split(' ')[0]
            if command in self._long_commands_timeout:
                timeout = self._long_commands_timeout[command]
            return self._recvall(timeout=timeout)


class Q2Exception(RconError):
    """ Class exceptions """


class Q2RConnection(RConnection):
    """ Class to allow connections to Quake 2 Servers """

    def __init__(self, host=None, port=27910, password=None):
        super().__init__(host, port, password)
        self.maplist = []
        self.current_map = ""
        self.players = []
        self.serverinfo = {}

    def send(self, data):
        """
        Send a RCON command over the socket
        :param data: The command to send
        :raise Q2Exception: When it's not possible to evaluate the command
        :return str: The server response to the RCON command
        """
        response = super().send(data)

        if response[0:5] != 'print':
            return Q2Exception('no response from server!')

        return response[6:]

    def get_status(self):
        """
        Send a RCON command over the socket
        :raise Q2Exception: When it's not possible to evaluate the command
        :return str: The server response to the RCON command
        """
        playerinfo = False
        output = self.send('status')
        self.current_map = ''
        self.players = []

        lines = output.splitlines()
        for line in lines:
            #print("line",line)
            if playerinfo and line[0:3].strip(' ') != '':
                self.players.append(
                        {
                            line[0:3].strip():
                            {
                                'score': int(line[5:9]),
                                'ping': line[10:14].strip(),
                                'name': line[15:29].strip(),
                                'lastmsg': int(line[31:38]),
                                'ip_address': line[39:59].strip(),
                                'rate_pps': line[60:69].strip(),
                                'ver': int(line[70:73]),
                            }
                        }
                )

            if line[0:3] == 'map' and self.current_map == '':
                self.current_map = line.split(': ')[1]

            if line == REPORT_LINE:
                playerinfo = True

    def get_map_list(self):
        """
        Get all maps
        :return list: Get all maps
        """
        output = self.send('dir maps/')
        lines = output.splitlines()
        self.maplist = []

        for line in lines:
            sline = line.strip()

            if not (sline == '----' or sline[0:13] == 'Directory of '):
                self.maplist.append(line.split(".")[0])

        self.maplist = list(set(self.maplist))
        self.maplist.sort()
        return self.maplist

    def change_map(self, map_name):
        """
        Request map change by name
        :raise Q2Exception: When it's not possible to evaluate the command
        """
        self.send('map ' + map_name)
        self.get_status()
        if self.current_map != map_name:
            raise Q2Exception('map failed to change')

    def get_serverinfo(self):
        """
        Retrieve serverinfo and parse
        :return dict: serverinfo
        """
        return self._parse_serverinfo(self.send('serverinfo'))

    def _parse_serverinfo(self, data):
        """
        Parse serverinfo response
        :param data: The command to send
        """
        for line in data.splitlines():
            if line[0:21] != 'Server info settings:':
                line = list(filter(lambda x: x != '', line.split(' ')))
                self.serverinfo[line[0]] = line[1]
        return self.serverinfo
