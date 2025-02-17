###############################################
# Clase que implementa el protocolo de Quake II #
###############################################
import socket
from bs4 import BeautifulSoup
import requests
from tkinter import messagebox

###############################################################
# Función para obtener la lista de servidores (web scraping)  #
###############################################################

def get_server_data():
    url = "http://q2servers.com/?mod=*&g=dday&m=*&c=*&ac=*&s=&player="
    response = requests.get(url)
    servers = []
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        server_blocks = soup.find_all(class_="server")
        for server in server_blocks:
            tds = server.find_all("td")
            if len(tds) >= 7:
                hostname = tds[1].get_text(strip=True)
                ip = tds[3].get_text(strip=True)
                game = tds[4].get_text(strip=True)
                map_name = tds[5].get_text(strip=True)
                players = tds[6].get_text(strip=True)
                servers.append({
                    "Hostname": hostname,
                    "IP": ip,
                    "Game": game,
                    "Map": map_name,
                    "Players": players
                })
    else:
        print("Error al acceder a la página:", response.status_code)
    return servers

###############################################################
# Función auxiliar para parsear la URL del servidor (quake2://) #
###############################################################

def parse_quake2_url(url):
    # Se espera un string del tipo "quake2://38.7.201.149:27910"
    if url.startswith("quake2://"):
        url = url[len("quake2://"):]
    parts = url.split(":")
    if len(parts) != 2:
        raise ValueError("Formato de URL incorrecto")
    ip = parts[0]
    try:
        port = int(parts[1])
    except ValueError:
        raise ValueError("Puerto inválido en URL")
    return ip, port

###############################################################
# Función para actualizar la lista de jugadores en el mismo #
# ventana (en el treeview de la sección inferior)           #
###############################################################

def update_players(server, players_tree):
    try:
        ip, port = parse_quake2_url(server["IP"])
    except Exception as e:
        messagebox.showerror("Error", f"Error al parsear IP:\n{e}")
        return

    query = Quake2Query(is_quake1=False)
    try:
        state = query.query(ip, port)
    except Exception as e:
        messagebox.showerror("Error", f"Error al consultar el servidor:\n{e}")
        return

    players = state.get("players", [])
    # Limpiar la tabla de jugadores
    for item in players_tree.get_children():
        players_tree.delete(item)
    # Insertar cada jugador en la tabla
    for player in players:
        name = player.get("name", "N/A")
        frags = player.get("frags", "N/A")
        ping = player.get("ping", "N/A")
        address = player.get("address", "N/A")
        players_tree.insert("", "end", values=(name, frags, ping, address))

class Quake2Query:
    def __init__(self, is_quake1=False):
        self.encoding = 'latin1'
        self.delimiter = '\n'
        self.send_header = 'status'
        self.response_header = 'print'
        self.is_quake1 = is_quake1

    def query(self, ip, port=27960, timeout=3.0):
        """Realiza la query al servidor de Quake II y devuelve un diccionario con la info."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        server_address = (ip, port)

        # Construir el paquete: 4 bytes 0xff, luego "status" y un byte nulo
        packet = b'\xff\xff\xff\xff' + self.send_header.encode(self.encoding) + b'\x00'
        try:
            sock.sendto(packet, server_address)
            data, _ = sock.recvfrom(4096)
        except socket.timeout:
            raise Exception("Tiempo de espera agotado al conectarse al servidor")
        finally:
            sock.close()

        if len(data) < 4:
            raise Exception("Respuesta demasiado corta")

        # Verificar la cabecera
        header = data[0:4]
        if header != b'\xff\xff\xff\xff':
            raise Exception("Respuesta inválida (cabecera incorrecta)")

        rest = data[4:]
        s = rest.decode(self.encoding, errors='replace')
        parts = s.split(None, 1)
        if not parts:
            raise Exception("No se encontró el response header")
        resp_type = parts[0]
        if resp_type != self.response_header:
            raise Exception(f"Response header inesperado: {resp_type}")
        body = parts[1] if len(parts) > 1 else ""

        lines = body.splitlines()
        state = {
            "raw": {},
            "players": [],
            "bots": [],
            "password": None,
            "map": None,
            "maxplayers": None,
            "name": None,
            "numplayers": 0,
            "version": None
        }
        if not lines:
            return state

        # La primera línea contiene la información del servidor en pares clave/valor
        info_line = lines[0]
        info_parts = info_line.split('\\')
        if info_parts and info_parts[0] == '':
            info_parts = info_parts[1:]
        for i in range(0, len(info_parts) - 1, 2):
            key = info_parts[i]
            value = info_parts[i + 1]
            state["raw"][key] = value

        # Las siguientes líneas contienen la información de los jugadores
        for line in lines[1:]:
            line = line.strip()
            if not line or line[0] == '\0':
                break
            args = self.parse_line_args(line)
            if not args:
                continue
            player = {}
            if self.is_quake1:
                try:
                    player["id"] = int(args[0])
                    player["score"] = int(args[1])
                    player["time"] = int(args[2])
                    player["ping"] = int(args[3])
                    player["name"] = args[4]
                    player["skin"] = args[5]
                    player["color1"] = int(args[6])
                    player["color2"] = int(args[7])
                except Exception as e:
                    print("Error parseando jugador (Quake1):", e)
            else:
                try:
                    player["frags"] = int(args[0])
                except:
                    player["frags"] = 0
                try:
                    player["ping"] = int(args[1])
                except:
                    player["ping"] = 0
                player["name"] = args[2] if len(args) > 2 and args[2] else ""
                if not player["name"]:
                    player.pop("name", None)
                player["address"] = args[3] if len(args) > 3 and args[3] else ""
                if not player["address"]:
                    player.pop("address", None)
            # Según la lógica original, si el ping es 0 se considera bot
            if player.get("ping", 0):
                state["players"].append(player)
            else:
                state["bots"].append(player)

        if "g_needpass" in state["raw"]:
            state["password"] = state["raw"]["g_needpass"]
        if "mapname" in state["raw"]:
            state["map"] = state["raw"]["mapname"]
        if "sv_maxclients" in state["raw"]:
            state["maxplayers"] = state["raw"]["sv_maxclients"]
        if "maxclients" in state["raw"]:
            state["maxplayers"] = state["raw"]["maxclients"]
        if "sv_hostname" in state["raw"]:
            state["name"] = state["raw"]["sv_hostname"]
        if "hostname" in state["raw"]:
            state["name"] = state["raw"]["hostname"]
        if "clients" in state["raw"]:
            state["numplayers"] = state["raw"]["clients"]
        if "version" in state["raw"]:
            state["version"] = state["raw"]["version"]
        elif "iv" in state["raw"]:
            state["version"] = state["raw"]["iv"]
        else:
            state["numplayers"] = len(state["players"]) + len(state["bots"])

        return state

    def parse_line_args(self, line):
        """Parsea la línea de jugadores respetando las comillas."""
        args = []
        in_quote = False
        current = ""
        i = 0
        while i < len(line):
            c = line[i]
            if c == '"':
                in_quote = not in_quote
                if not in_quote and current:
                    args.append(current)
                    current = ""
                i += 1
                continue
            if c.isspace() and not in_quote:
                if current:
                    args.append(current)
                    current = ""
                i += 1
            else:
                current += c
                i += 1
        if current:
            args.append(current)
        return args