import tkinter as tk
from tkinter import ttk, messagebox, PhotoImage, filedialog
import q2query
import q2rcon
import configparser
import os
import threading
import subprocess
import datetime

CONFIG_FILE = "servers.ini"
APP_CONFIG_FILE = "config.ini"
LOG_FILE = "logs.txt"

def load_config(file_path, default_section=None):
    config = configparser.ConfigParser()
    if os.path.exists(file_path):
        config.read(file_path)
    elif default_section:
        config[default_section] = {}
    return config

def save_config(config, file_path):
    with open(file_path, "w") as f:
        config.write(f)

# Cargar configuraciones
rcon_config = load_config(CONFIG_FILE)
app_config = load_config(APP_CONFIG_FILE, "General")
selected_server_admin = None

# Variable global para el widget de logs (se asigna en create_gui)
log_text_widget = None

# Función para escribir logs con fecha/hora, guardar en archivo y mostrarlos en la pestaña de Logs.
def write_log(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} - {msg}\n"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Error al escribir log: {e}")
    if log_text_widget:
        log_text_widget.insert(tk.END, log_entry)
        log_text_widget.see(tk.END)

# Ventana de Configuraciones de la aplicación
def open_config_window():
    config_win = tk.Toplevel()
    config_win.title("Configuraciones de la aplicación")
    config_win.geometry("400x200")
    
    current_exe = app_config["General"].get("executable", "No configurado")
    
    tk.Label(config_win, text="Ejecutable actual:", font=("Arial", 12, "bold")).pack(pady=(10,5))
    exe_label = tk.Label(config_win, text=current_exe, font=("Arial", 10))
    exe_label.pack(pady=(0,10))
    
    def select_executable():
        exe_path = filedialog.askopenfilename(
            title="Seleccionar ejecutable", 
            filetypes=[("Executable files", "*.exe;*.bat;*.cmd;*.*")]
        )
        if exe_path:
            app_config["General"]["executable"] = exe_path
            save_config(app_config, APP_CONFIG_FILE)
            exe_label.config(text=exe_path)
            messagebox.showinfo("Información", f"Ejecutable guardado:\n{exe_path}")
    
    tk.Button(config_win, text="Seleccionar ejecutable", command=select_executable).pack(pady=10)

# Ventana Administrador de Servidores
def open_admin_window():
    global rcon_config
    admin_win = tk.Toplevel()
    admin_win.title("Administrador de Servidores")
    admin_win.geometry("600x400")
    
    # Iconos 32x32
    add_icon = PhotoImage(file="iconos/icons8-add-server-32.png").subsample(2,2)
    edit_icon = PhotoImage(file="iconos/icons8-edit-server-32.png").subsample(2,2)
    delete_icon = PhotoImage(file="iconos/icons8-delete-server-32.png").subsample(2,2)
    
    top_frame = tk.Frame(admin_win)
    top_frame.pack(fill="x", padx=5, pady=5)
    tk.Button(top_frame, text="Agregar Servidor", image=add_icon, compound='left',
              command=lambda: server_dialog(admin_win, None, add=True)).pack(side="left", padx=5)
    tk.Button(top_frame, text="Editar Servidor", image=edit_icon, compound='left',
              command=lambda: server_dialog(admin_win, tree.focus(), add=False)).pack(side="left", padx=5)
    tk.Button(top_frame, text="Eliminar Servidor", image=delete_icon, compound='left',
              command=lambda: delete_server(tree)).pack(side="left", padx=5)
    # Conservar referencias
    for btn in top_frame.winfo_children():
        btn.image = btn.cget("image")
    
    tree_frame = tk.Frame(admin_win)
    tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
    cols = ("IP", "Port", "RCON Password")
    tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
    for col in cols:
        tree.heading(col, text=col)
        tree.column(col, width=150)
    tree.pack(expand=True, fill="both")
    
    def update_admin_tree():
        tree.delete(*tree.get_children())
        for sec in rcon_config.sections():
            try:
                ip, port = sec.split(":")
            except ValueError:
                ip, port = sec, ""
            tree.insert("", "end", iid=sec, values=(ip, port, rcon_config[sec].get("rcon_password", "")))
    
    def delete_server(tree_obj):
        sec = tree_obj.focus()
        if not sec:
            messagebox.showwarning("Advertencia", "Selecciona un servidor para eliminar.")
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar este servidor?"):
            rcon_config.remove_section(sec)
            save_config(rcon_config, CONFIG_FILE)
            update_admin_tree()
    
    def server_dialog(parent, sec, add=False):
        dlg = tk.Toplevel(parent)
        dlg.title("Agregar Servidor" if add else "Editar Servidor")
        for i, txt in enumerate(["IP", "Port", "RCON Password"]):
            tk.Label(dlg, text=txt).grid(row=i, column=0, padx=5, pady=5)
        e_ip = tk.Entry(dlg)
        e_port = tk.Entry(dlg)
        e_pass = tk.Entry(dlg, show="*")
        e_ip.grid(row=0, column=1, padx=5, pady=5)
        e_port.grid(row=1, column=1, padx=5, pady=5)
        e_pass.grid(row=2, column=1, padx=5, pady=5)
        if sec and not add:
            ip_val, port_val = sec.split(":")
            e_ip.insert(0, ip_val)
            e_port.insert(0, port_val)
            e_pass.insert(0, rcon_config[sec].get("rcon_password", ""))
        def save_data():
            ip = e_ip.get().strip()
            try:
                port = int(e_port.get().strip())
            except ValueError:
                messagebox.showerror("Error", "El puerto debe ser numérico.")
                return
            password = e_pass.get().strip()
            new_sec = f"{ip}:{port}"
            if add:
                if new_sec in rcon_config:
                    messagebox.showerror("Error", "Configuración ya existente.")
                    return
                rcon_config.add_section(new_sec)
            else:
                if new_sec != sec and new_sec in rcon_config:
                    messagebox.showerror("Error", "Configuración ya existente.")
                    return
                if new_sec != sec:
                    rcon_config.remove_section(sec)
                    rcon_config.add_section(new_sec)
            rcon_config.set(new_sec, "rcon_password", password)
            save_config(rcon_config, CONFIG_FILE)
            update_admin_tree()
            dlg.destroy()
        tk.Button(dlg, text="Guardar", command=save_data).grid(row=3, column=0, columnspan=2, pady=10)
    
    update_admin_tree()
    admin_win.mainloop()

# Función para enviar el comando RCON "status"
def send_command():
    global selected_server_admin
    if not selected_server_admin:
        messagebox.showwarning("Advertencia", "Selecciona un servidor con configuración RCON.")
        return
    try:
        conn = q2rcon.Q2RConnection(
            host=selected_server_admin["ip"],
            port=selected_server_admin["port"],
            password=selected_server_admin["password"]
        )
        resp = conn.send("status")
        messagebox.showinfo("Respuesta RCON", resp)
        write_log(f"Comando 'status' enviado al servidor {selected_server_admin['ip']}:{selected_server_admin['port']}")
    except Exception as e:
        messagebox.showerror("Error", f"Error al enviar comando: {e}")
        write_log(f"Error al enviar 'status': {e}")

# Función principal: GUI
def create_gui(servers):
    global selected_server_admin, rcon_config, app_config, server_tree, log_text_widget
    root = tk.Tk()
    root.geometry("1200x600")
    root.title("RCON tool para ddaychile")
    root.iconphoto(False, tk.PhotoImage(file="iconos/icono_app.png"))
    
    # Menú superior
    menu_bar = tk.Menu(root)
    root.config(menu=menu_bar)
    
    app_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="Aplicacion", menu=app_menu)
    app_menu.add_command(label="Salir", command=root.quit)
    app_menu.add_separator()
    def refresh_server_list():
        nonlocal servers
        servers = q2query.get_server_data()
        update_server_tree(servers)
        write_log("Lista de servidores refrescada")
    app_menu.add_command(label="Refrescar lista", command=refresh_server_list)
    
    config_icon = PhotoImage(file="iconos/icons8-ajustes-32.png").subsample(2,2)
    config_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="Configuracion", menu=config_menu)
    config_menu.add_command(label="Configuraciones de la aplicación", command=open_config_window, image=config_icon, compound='left')
    
    server_icon = PhotoImage(file="iconos/icons8-servidor-30.png").subsample(2,2)
    admin_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="Administrador de servidores", menu=admin_menu)
    admin_menu.add_command(label="Abrir Administrador", command=open_admin_window, image=server_icon, compound='left')
    
    # PanedWindow principal
    paned = ttk.PanedWindow(root, orient="vertical")
    paned.pack(fill="both", expand=True)
    server_frame = ttk.Frame(paned)
    bottom_frame = ttk.Frame(paned)
    paned.add(server_frame, weight=1)
    paned.add(bottom_frame, weight=1)
    
    # --- Treeview de Servidores ---
    green_icon = PhotoImage(file="iconos/green_ticket.png").subsample(2,2)
    server_tree = ttk.Treeview(server_frame, columns=("Hostname", "IP", "Game", "Map", "Players"), show="tree headings")
    server_tree.heading("#0", text="RCON")
    server_tree.column("#0", width=50)
    for col in ("Hostname", "IP", "Game", "Map", "Players"):
        server_tree.heading(col, text=col)
        server_tree.column(col, width=250 if col=="Hostname" else 100)
    
    def update_server_tree(srv_list):
        server_tree.delete(*server_tree.get_children())
        for i, srv in enumerate(srv_list):
            try:
                ip, port = q2query.parse_quake2_url(srv["IP"])
                sec = f"{ip}:{port}"
                img = green_icon if sec in rcon_config else ""
            except Exception:
                img = ""
            server_tree.insert("", "end", iid=str(i), text="", image=img,
                               values=(srv["Hostname"], srv["IP"], srv["Game"], srv["Map"], srv["Players"]))
    
    update_server_tree(servers)
    scrollbar = ttk.Scrollbar(server_frame, orient="vertical", command=server_tree.yview)
    server_tree.configure(yscroll=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    server_tree.pack(expand=True, fill="both")
    
    # --- Sección inferior: Jugadores y Notebook ---
    players_frame = ttk.Frame(bottom_frame, width=400, height=200)
    players_frame.pack_propagate(False)
    tabs_frame = ttk.Frame(bottom_frame)
    players_frame.pack(side="left", fill="both", expand=True)
    tabs_frame.pack(side="right", fill="both", expand=True)
    
    # Treeview de Jugadores
    player_cols = ("Name", "Frags", "Ping", "Address")
    player_tree = ttk.Treeview(players_frame, columns=player_cols, show="headings")
    for col in player_cols:
        player_tree.heading(col, text=col)
    player_tree.column("Name", width=200)
    player_tree.column("Frags", width=80)
    player_tree.column("Ping", width=80)
    player_tree.column("Address", width=150)
    player_tree.pack(expand=True, fill="both", side="left")
    p_scroll = ttk.Scrollbar(players_frame, orient="vertical", command=player_tree.yview)
    player_tree.configure(yscroll=p_scroll.set)
    p_scroll.pack(side="right", fill="y")
    
    # Notebook: Acciones, Consola y Logs
    icon_acciones = PhotoImage(file="iconos/icons8-server-upload-32.png").subsample(2,2)
    icon_consola = PhotoImage(file="iconos/icons8-consola-32.png").subsample(2,2)
    icon_logs = PhotoImage(file="iconos/icons8-editar-propiedad-32.png").subsample(2,2)
    notebook = ttk.Notebook(tabs_frame)
    tab_acciones = ttk.Frame(notebook)
    tab_consola = ttk.Frame(notebook)
    tab_logs = ttk.Frame(notebook)
    notebook.add(tab_acciones, text="Acciones del servidor", image=icon_acciones, compound='left')
    notebook.add(tab_consola, text="Consola", image=icon_consola, compound='left')
    notebook.add(tab_logs, text="Logs", image=icon_logs, compound='left')
    notebook.pack(expand=True, fill="both")
    
    # --- Pestaña Acciones ---
    act_frame = ttk.LabelFrame(tab_acciones, text="Enviar Comando RCON")
    act_frame.pack(padx=10, pady=10, fill="x")
    icon_send = PhotoImage(file="iconos/icons8-lleno-enviado-30.png").subsample(2,2)
    tk.Button(act_frame, text="Enviar 'status'", image=icon_send, compound='left', command=send_command).pack(padx=5, pady=5)
    
    # --- Pestaña Consola ---
    cons_frame = tk.Frame(tab_consola, width=800, height=200, bg="black")
    cons_frame.pack(padx=5, pady=5)
    cons_frame.pack_propagate(False)
    cons_text = tk.Text(cons_frame, bg="black", fg="lime", insertbackground="white", font=("Courier New", 10), state=tk.DISABLED)
    cons_scroll = ttk.Scrollbar(cons_frame, orient='vertical', command=cons_text.yview)
    cons_text.configure(yscrollcommand=cons_scroll.set)
    cons_scroll.pack(side='right', fill='y')
    cons_text.pack(expand=True, fill="both", padx=5, pady=5)
    cons_input = tk.Frame(tab_consola, bg="black")
    cons_input.pack(fill="x", padx=5, pady=5)
    cons_entry = tk.Entry(cons_input, bg="black", fg="lime", insertbackground="white", font=("Courier New", 10))
    cons_entry.bind("<Return>", lambda event: send_console_command())
    cons_entry.pack(side="left", fill="x", expand=True, padx=(0,5))
    
    def append_to_console(text):
        cons_text.config(state=tk.NORMAL)
        cons_text.insert(tk.END, f"{text}\n")
        cons_text.see(tk.END)
        cons_text.config(state=tk.DISABLED)
    
    def run_console_command(cmd):
        try:
            conn = q2rcon.Q2RConnection(
                host=selected_server_admin["ip"],
                port=selected_server_admin["port"],
                password=selected_server_admin["password"]
            )
            out = conn.send(cmd)
            root.after(0, lambda: append_to_console(out))
            write_log(f"Consola: comando '{cmd}' ejecutado")
        except Exception as e:
            root.after(0, lambda: append_to_console(f"Error: {e}"))
            write_log(f"Consola: error al ejecutar '{cmd}': {e}")
    
    def send_console_command():
        cmd = cons_entry.get().strip()
        if not cmd:
            return
        if not selected_server_admin:
            messagebox.showwarning("Advertencia", "No hay datos RCON configurados para el servidor seleccionado.")
            return
        append_to_console(f"> {cmd}")
        cons_entry.delete(0, tk.END)
        threading.Thread(target=run_console_command, args=(cmd,)).start()
    
    tk.Button(cons_input, text="Enviar", command=send_console_command, bg="black", fg="lime", font=("Courier New", 10)).pack(side="left")
    
    # --- Pestaña Logs ---
    log_frame = tk.Frame(tab_logs, bg="#333")
    log_frame.pack(expand=True, fill="both", padx=5, pady=5)
    log_text = tk.Text(log_frame, bg="#333", fg="white", font=("Arial", 10), wrap="word")
    log_text.pack(expand=True, fill="both", padx=5, pady=5)
    tk.Button(tab_logs, text="Limpiar Logs", command=lambda: log_text.delete("1.0", tk.END)).pack(pady=5)
    
    # Asignar el widget de logs a la variable global para usarlo en write_log
    global log_text_widget
    log_text_widget = log_text
    # Cargar contenido previo de logs.txt, si existe
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                content = f.read()
            log_text.insert(tk.END, content)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar los logs: {e}")
    
    # --- Eventos en el Treeview de Servidores ---
    def on_select(event):
        global selected_server_admin
        sel = server_tree.selection()
        if sel:
            idx = int(sel[0])
            srv = servers[idx]
            q2query.update_players(srv, player_tree)
            try:
                ip, port = q2query.parse_quake2_url(srv["IP"])
                sec = f"{ip}:{port}"
                if sec in rcon_config:
                    selected_server_admin = {"ip": ip, "port": int(port), "password": rcon_config[sec].get("rcon_password", "")}
                else:
                    selected_server_admin = None
            except Exception:
                selected_server_admin = None
            write_log(f"Seleccionado servidor: {srv['Hostname']} ({srv['IP']})")
    
    server_tree.bind("<<TreeviewSelect>>", on_select)
    
    def on_double_click(event):
        sel = server_tree.selection()
        if sel:
            idx = int(sel[0])
            srv = servers[idx]
            try:
                ip, port = q2query.parse_quake2_url(srv["IP"])
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo parsear la IP y puerto: {e}")
                return
            exe_path = app_config["General"].get("executable", "")
            if not exe_path:
                messagebox.showwarning("Advertencia", "No se ha configurado un ejecutable en Configuración.")
                return
            try:
                subprocess.Popen([exe_path, "+game", "dday", "+connect", f"{ip}:{port}"])
                write_log(f"Ejecución: {exe_path} +game dday +connect {ip}:{port}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo ejecutar el ejecutable: {e}")
    
    server_tree.bind("<Double-1>", on_double_click)
    
    root.mainloop()

if __name__ == "__main__":
    server_list = q2query.get_server_data()
    create_gui(server_list)
