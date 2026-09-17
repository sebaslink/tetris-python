import sys
import tkinter as tk
from tkinter import simpledialog, messagebox
import random
import json
import winsound
import threading
import os
import ctypes
import glob
import wave
import io
import math
import struct
import time

def obtener_ruta_recurso(ruta_relativa):
    """ Obtiene la ruta absoluta para un recurso, compatible con desarrollo y PyInstaller (onedir/onefile) """
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        ruta = os.path.join(meipass, ruta_relativa)
        if os.path.exists(ruta):
            return ruta

    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    ruta = os.path.join(base_dir, ruta_relativa)
    if os.path.exists(ruta):
        return ruta

    ruta_cwd = os.path.join(os.getcwd(), ruta_relativa)
    if os.path.exists(ruta_cwd):
        return ruta_cwd

    return os.path.join(base_dir, ruta_relativa)


windll = getattr(ctypes, "windll", None)
winmm = getattr(windll, "winmm", None) if windll else None

pygame_audio_disponible = False
try:
    import pygame
    pygame.mixer.init()
    pygame_audio_disponible = True
except Exception:
    pygame_audio_disponible = False


"""
Conexion y estado de Firebase Firestore
"""
db_firebase = None
firebase_conectado = False
info_conexion_firebase = "Buscando archivo de credenciales..."

def conectar_firebase():
    global db_firebase, firebase_conectado, info_conexion_firebase
    if firebase_conectado:
        return True
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        
        directorios_busqueda = []
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            directorios_busqueda.append(meipass)
        if getattr(sys, 'frozen', False):
            directorios_busqueda.append(os.path.dirname(sys.executable))
        else:
            directorios_busqueda.append(os.path.dirname(os.path.abspath(__file__)))
        directorios_busqueda.append(os.getcwd())

        archivos_json = []
        for d in directorios_busqueda:
            if os.path.exists(d):
                archivos_json.extend(glob.glob(os.path.join(d, "*.json")))

        archivo_credencial = None
        for f in archivos_json:
            if "firebase" in f.lower() or "service" in f.lower() or f.lower().endswith("firebase_key.json"):
                archivo_credencial = f
                break
        if not archivo_credencial:
            archivos_validos = [f for f in archivos_json if "pyright" not in f.lower()]
            if archivos_validos:
                archivo_credencial = archivos_validos[0]
            
        if archivo_credencial and os.path.exists(archivo_credencial):
            if not firebase_admin._apps:
                cred = credentials.Certificate(archivo_credencial)
                firebase_admin.initialize_app(cred)
            db_firebase = firestore.client()
            firebase_conectado = True
            info_conexion_firebase = f"Conectado: {os.path.basename(archivo_credencial)}"
            return True
        else:
            info_conexion_firebase = "Falta archivo firebase_key.json"
    except Exception as err:
        info_conexion_firebase = f"Error: {str(err)[:25]}"
    firebase_conectado = False
    return False

URL_RENDER_SERVER = "https://tetris-python.onrender.com"

def guardar_puntaje_firebase(nombre_jugador, puntaje):
    if conectar_firebase() and db_firebase is not None:
        try:
            from firebase_admin import firestore
            ts = getattr(firestore, "SERVER_TIMESTAMP", None)
            db_firebase.collection("puntuaciones").add({
                "jugador": nombre_jugador,
                "puntuacion": int(puntaje),
                "fecha": ts
            })
            return True
        except Exception:
            pass

    try:
        import urllib.request
        req = urllib.request.Request(
            f"{URL_RENDER_SERVER}/api/scores",
            data=json.dumps({"jugador": nombre_jugador, "puntuacion": int(puntaje)}).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False

def obtener_ranking_firebase():
    if conectar_firebase() and db_firebase is not None:
        try:
            from firebase_admin import firestore
            q_class = getattr(firestore, "Query", None)
            desc_dir = getattr(q_class, "DESCENDING", "DESCENDING") if q_class else "DESCENDING"
            query = db_firebase.collection("puntuaciones").order_by("puntuacion", direction=desc_dir).limit(5)
            docs = query.stream()
            ranking = []
            for doc in docs:
                data = doc.to_dict() if hasattr(doc, "to_dict") else {}
                if isinstance(data, dict):
                    ranking.append((str(data.get("jugador", "Jugador")), int(data.get("puntuacion", 0))))
            if ranking:
                return ranking
        except Exception:
            pass

    try:
        import urllib.request
        with urllib.request.urlopen(f"{URL_RENDER_SERVER}/api/scores", timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            ranking = []
            for item in data.get("scores", []):
                ranking.append((item.get("jugador", "Jugador"), item.get("puntuacion", 0)))
            return ranking
    except Exception:
        return []

def crear_sala_firebase(nombre_sala="Sala Tetris"):
    if not conectar_firebase() or db_firebase is None:
        return None
    try:
        from firebase_admin import firestore
        ts = getattr(firestore, "SERVER_TIMESTAMP", None)
        doc_ref = db_firebase.collection("salas").add({
            "nombre": nombre_sala,
            "estado": "esperando",
            "creado": ts
        })
        return doc_ref[1].id
    except Exception:
        return None

COLUMNAS = 10
FILAS = 20
TAMANO_BLOQUE = 30

tablero: list[list[int | str]] = [[0 for _ in
range(COLUMNAS)] for _ in
range(FILAS)]

try:
    myappid = 'zodiacosoftware.casualblocks.game.0.1'
    if windll and hasattr(windll, "shell32"):
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

root = tk.Tk()
root.title("Casual Blocks 2026 - Versión 0.1")
root.configure(bg="#121218")

ruta_icono_png = obtener_ruta_recurso(os.path.join("img", "icons8-tetris-64.png"))
ruta_icono_ico = obtener_ruta_recurso(os.path.join("img", "icons8-tetris-64.ico"))

if os.path.exists(ruta_icono_png):
    try:
        icono_tk = tk.PhotoImage(file=ruta_icono_png)
        root.iconphoto(True, icono_tk)
    except Exception:
        try:
            from PIL import Image, ImageTk
            img_ico = Image.open(ruta_icono_png)
            icono_tk = ImageTk.PhotoImage(img_ico)
            root.iconphoto(True, icono_tk)  # type: ignore
        except Exception:
            pass

if os.path.exists(ruta_icono_ico):
    try:
        root.iconbitmap(ruta_icono_ico)
    except Exception:
        pass


ancho = COLUMNAS * TAMANO_BLOQUE
alto = FILAS * TAMANO_BLOQUE

canvas = tk.Canvas(root, width=ancho + 180, height=alto, bg="#121218", highlightthickness=0)
canvas.pack(fill="both", expand=True)

"""
Calculo dinamico de offset de centrado de ventana (Pantalla fija y estable)
"""
def activar_screen_shake(fuerza=4, duracion=0.12):
    pass

def obtener_offset_pantalla():
    cw = canvas.winfo_width()
    ch = canvas.winfo_height()
    ancho_requerido = (ancho * 2 + 320) if modo_juego == "VERSUS" else (ancho + 180)
    if cw < 10:
        cw = ancho_requerido
    if ch < 10:
        ch = alto
    off_x = max(0, (cw - ancho_requerido) // 2)
    off_y = max(0, (ch - alto) // 2)
    return off_x, off_y, cw, ch

def ajustar_tamano_ventana():
    try:
        if root.attributes("-fullscreen"):
            return
        ancho_req = (ancho * 2 + 320) if modo_juego == "VERSUS" else (ancho + 180)
        root.geometry(f"{ancho_req}x{alto}")
    except Exception:
        pass

"""
Paleta de colores estilizada y renderizado de bloques con relieve/bisel 3D
"""
PALETA_BLOQUES = {
    # Paleta Synthwave / Cyberpunk exclusiva de Casual Blocks
    'neon_cyan':      {'base': '#00f5d4', 'luz': '#70fff0', 'sombra': '#009999'},
    'solar_amber':    {'base': '#ffbe0b', 'luz': '#ffe580', 'sombra': '#d48800'},
    'synth_violet':   {'base': '#8338ec', 'luz': '#b37aff', 'sombra': '#5210ba'},
    'cyber_mint':     {'base': '#06d6a0', 'luz': '#70ffcf', 'sombra': '#028564'},
    'hot_pink':       {'base': '#ff007f', 'luz': '#ff66b2', 'sombra': '#b30059'},
    'laser_blue':     {'base': '#3a86ff', 'luz': '#85b6ff', 'sombra': '#0051cc'},
    'sunset_orange':  {'base': '#ff7b00', 'luz': '#ffaa55', 'sombra': '#b34700'},
    'gray':           {'base': '#576574', 'luz': '#8395a7', 'sombra': '#222f3e'},
    # Aliases retro para compatibilidad total
    'cyan':           {'base': '#00f5d4', 'luz': '#70fff0', 'sombra': '#009999'},
    'yellow':         {'base': '#ffbe0b', 'luz': '#ffe580', 'sombra': '#d48800'},
    'purple':         {'base': '#8338ec', 'luz': '#b37aff', 'sombra': '#5210ba'},
    'green':          {'base': '#06d6a0', 'luz': '#70ffcf', 'sombra': '#028564'},
    'red':            {'base': '#ff007f', 'luz': '#ff66b2', 'sombra': '#b30059'},
    'blue':           {'base': '#3a86ff', 'luz': '#85b6ff', 'sombra': '#0051cc'},
    'orange':         {'base': '#ff7b00', 'luz': '#ffaa55', 'sombra': '#b34700'},
    # Colores para piezas trampa y especiales (Modo Caos / Casual Blocks)
    'gold':           {'base': '#ffd700', 'luz': '#fff48f', 'sombra': '#b89600'},
    'lime':           {'base': '#00e676', 'luz': '#69f0ae', 'sombra': '#00a152'},
    'magenta':        {'base': '#e056fd', 'luz': '#f39cff', 'sombra': '#a21caf'},
    'crimson':        {'base': '#ff2a2a', 'luz': '#ff7070', 'sombra': '#b30000'},
    'neon_blue':      {'base': '#00b4d8', 'luz': '#90e0ef', 'sombra': '#0077b6'},
    'bomb_red':       {'base': '#ff1744', 'luz': '#ff8a80', 'sombra': '#b71c1c'},
}

def dibujar_bloque_3d(x1, y1, x2, y2, color_nombre, bevel=3):
    if color_nombre in PALETA_BLOQUES:
        pal = PALETA_BLOQUES[color_nombre]
        c_base = pal['base']
        c_luz = pal['luz']
        c_som = pal['sombra']
    else:
        c_base = color_nombre
        c_luz = "#ffffff"
        c_som = "#111111"

    # Base del bloque
    canvas.create_rectangle(x1, y1, x2, y2, fill=c_base, outline="")
    # Bisel superior e izquierdo (luz brillante)
    canvas.create_polygon(x1, y1, x2, y1, x2 - bevel, y1 + bevel, x1 + bevel, y1 + bevel, fill=c_luz, outline="")
    canvas.create_polygon(x1, y1, x1 + bevel, y1 + bevel, x1 + bevel, y2 - bevel, x1, y2, fill=c_luz, outline="")
    # Bisel inferior y derecho (sombra)
    canvas.create_polygon(x1, y2, x1 + bevel, y2 - bevel, x2 - bevel, y2 - bevel, x2, y2, fill=c_som, outline="")
    canvas.create_polygon(x2, y1, x2, y2, x2 - bevel, y2 - bevel, x2 - bevel, y1 + bevel, fill=c_som, outline="")
    # Cara interior
    canvas.create_rectangle(x1 + bevel, y1 + bevel, x2 - bevel, y2 - bevel, fill=c_base, outline="")
    # Reflejo especular brillante en la esquina
    canvas.create_rectangle(x1 + bevel + 1, y1 + bevel + 1, x1 + bevel + 4, y1 + bevel + 4, fill="#ffffff", outline="")

    # Decorador especial si es la pieza Bomba
    if color_nombre == 'bomb_red':
        canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, text="💣", font=("Arial", 11, "bold"))

def dibujar_tablero():
    off_x, off_y, _, _ = obtener_offset_pantalla()
    # Dibujar tablero Jugador 1 con bloques 3D y rejilla elegante
    for f in range(FILAS):
        for c in range(COLUMNAS):
            x1 = off_x + c * TAMANO_BLOQUE
            y1 = off_y + f * TAMANO_BLOQUE
            x2 = x1 + TAMANO_BLOQUE
            y2 = y1 + TAMANO_BLOQUE
            valor = tablero[f][c]
            if valor != 0 and isinstance(valor, str):
                dibujar_bloque_3d(x1, y1, x2, y2, valor)
            else:
                # Rejilla translúcida: permite ver claramente el fondo
                canvas.create_rectangle(x1, y1, x2, y2, outline="#1a2538", fill="")

    if modo_individual == "POWERUPS" and time.time() < tiempo_congelado_hasta:
        seg = max(1, int(tiempo_congelado_hasta - time.time()) + 1)
        canvas.create_rectangle(off_x, off_y, off_x + ancho, off_y + alto, outline="#00ffff", width=3)
        canvas.create_text(off_x + ancho // 2, off_y + 16, text=f"❄️ ¡TIEMPO CONGELADO: {seg}s! ❄️", fill="#00ffff", font=("Arial", 10, "bold"))

    # Dibujar tablero Rival en Modo Versus
    if modo_juego == "VERSUS":
        off_rival_x = off_x + ancho + 200
        for f in range(FILAS):
            for c in range(COLUMNAS):
                x1 = off_rival_x + c * TAMANO_BLOQUE
                y1 = off_y + f * TAMANO_BLOQUE
                x2 = x1 + TAMANO_BLOQUE
                y2 = y1 + TAMANO_BLOQUE
                valor = tablero_rival[f][c]
                if valor != 0 and isinstance(valor, str):
                    dibujar_bloque_3d(x1, y1, x2, y2, valor)
                else:
                    canvas.create_rectangle(x1, y1, x2, y2, outline="#2c1a2c", fill="")

PIEZAS_ESTANDAR = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']
PIEZAS_TRAMPA = ['DOT', 'BAR5', 'CROSS', 'CORNER', 'U', 'BOMB']

PIEZAS = {
    # 7 Tetrominoes oficiales
    'I': [[1, 1, 1, 1]],
    'O': [[1, 1], [1, 1]],
    'T': [[0, 1, 0], [1, 1, 1]],
    'S': [[0, 1, 1], [1, 1, 0]],
    'Z': [[1, 1, 0], [0, 1, 1]],
    'J': [[1, 0, 0], [1, 1, 1]],
    'L': [[0, 0, 1], [1, 1, 1]],
    # Piezas especiales y trampas (Modo Caos / Blocks Boom)
    'DOT': [[1]],
    'BAR5': [[1, 1, 1, 1, 1]],
    'CROSS': [[0, 1, 0], [1, 1, 1], [0, 1, 0]],
    'CORNER': [[1, 1, 1], [1, 0, 0], [1, 0, 0]],
    'U': [[1, 0, 1], [1, 1, 1]],
    'BOMB': [[1]],
}

COLORES = {
    # 7 Piezas estándar con estética neón Casual Blocks
    'I': 'neon_cyan',
    'O': 'solar_amber',
    'T': 'synth_violet',
    'S': 'cyber_mint',
    'Z': 'hot_pink',
    'J': 'laser_blue',
    'L': 'sunset_orange',
    # Piezas especiales y trampas (Modo Caos / Casual Blocks)
    'DOT': 'gold',
    'BAR5': 'lime',
    'CROSS': 'magenta',
    'CORNER': 'crimson',
    'U': 'neon_blue',
    'BOMB': 'bomb_red',
}

"""
Generador de piezas 7-Bag oficial (Tetris Guideline) y Modo Caos Impredecible
"""
modo_individual = "CLASICO"  # "CLASICO", "SPRINT", "BLITZ", "SURVIVAL", "CAOS"
bolsa_piezas_p1 = []
bolsa_piezas_rival = []

def rellenar_bolsa_7():
    p = list(PIEZAS_ESTANDAR)
    random.shuffle(p)
    return p

def obtener_siguiente_de_bolsa(es_rival=False):
    global bolsa_piezas_p1, bolsa_piezas_rival
    if not es_rival and modo_individual == "CAOS":
        # Modo Caos: 100% aleatorio e impredecible con piezas trampa y bombas
        if random.random() < 0.32:
            return random.choice(PIEZAS_TRAMPA)
        return random.choice(PIEZAS_ESTANDAR)

    if es_rival:
        if len(bolsa_piezas_rival) < 4:
            bolsa_piezas_rival.extend(rellenar_bolsa_7())
        return bolsa_piezas_rival.pop(0)
    else:
        if len(bolsa_piezas_p1) < 4:
            bolsa_piezas_p1.extend(rellenar_bolsa_7())
        return bolsa_piezas_p1.pop(0)

bolsa_piezas_p1 = rellenar_bolsa_7() + rellenar_bolsa_7()
bolsa_piezas_rival = rellenar_bolsa_7() + rellenar_bolsa_7()

nombre_pieza = obtener_siguiente_de_bolsa(es_rival=False)
nombre_siguiente_pieza = obtener_siguiente_de_bolsa(es_rival=False)
pieza_actual = PIEZAS[nombre_pieza]
colores_actual = COLORES[nombre_pieza]
pos_x = COLUMNAS // 2 - 1
pos_y = 0
puntuacion = 0
maximo_puntaje = 0
es_nuevo_record = False
nombre_pieza_guardada = None
puede_guardar = True
juego_terminado = False

"""
Estado general de la interfaz y configuracion
"""
estado_pantalla = "INTRO"
sonido_activado = True
musica_activada = True
juego_en_pausa = False
opcion_menu_seleccionada = 0
opcion_modos_seleccionada = 0
opcion_online_seleccionada = 0
opcion_ajustes_seleccionada = 0

modo_individual = "CLASICO"  # "CLASICO", "SPRINT", "BLITZ", "SURVIVAL", "CAOS", "POWERUPS"
tiempo_inicio_modo = 0.0
tiempo_inicio_pausa = 0.0
tiempo_pausado_total = 0.0
lineas_objetivo_sprint = 40
duracion_blitz_seg = 120
timer_modo_tick = None
timer_survival = None
intervalo_survival_seg = 12
oleada_survival = 0
es_victoria_modo = False
tiempo_final_sprint = 0.0

# Variables del Modo Power-Ups
energia_powerups = 0  # 0 a 100
slots_powerups = ["BOMBA"]  # Comienza con una bomba de regalo
tiempo_congelado_hasta = 0.0
coords_btn_powerups = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]

coords_btn_modos = [[0, 0, 0, 0] for _ in range(7)]
coords_btn_gameover_restart = [0, 0, 0, 0]
coords_btn_gameover_menu = [0, 0, 0, 0]

timer_caer = None
timer_caer_rival = None

cap_intro = None
video_reproduciendose = False
imagen_intro_tk = None
tiempo_inicio_intro = 0.0
num_frame_actual = 0
imagen_menu_tk = None
imagenes_juego_tk = []
fondo_juego_actual = 0
lineas_totales = 0
combo_actual = 0
texto_flotante_msg = ""
texto_flotante_color = "#00ffff"
texto_flotante_tiempo = 0.0
conteo_piezas = {k: 0 for k in PIEZAS}
conteo_piezas[nombre_pieza] = 1

# Sistema de particulas optimizado de alta velocidad para Hard Drop y Explosiones
particulas = []
_animando_particulas = False

def animar_bucle_particulas():
    global _animando_particulas
    if not particulas:
        _animando_particulas = False
        return
    if estado_pantalla == "JUEGO" and not juego_en_pausa and not juego_terminado:
        redibujar()
    if particulas:
        root.after(25, animar_bucle_particulas)
    else:
        _animando_particulas = False

def agregar_particulas_impacto(cx, cy, color="#00ffff", cantidad=10, velocidad=5.0):
    global particulas, _animando_particulas
    # Limitar el total de particulas para mantener maximo rendimiento a 60 FPS
    if len(particulas) > 50:
        particulas = particulas[-25:]
    for _ in range(cantidad):
        ang = random.uniform(0, 2 * math.pi)
        spd = random.uniform(velocidad * 0.6, velocidad * 1.3)
        particulas.append({
            'x': float(cx),
            'y': float(cy),
            'vx': math.cos(ang) * spd,
            'vy': math.sin(ang) * spd - random.uniform(1.0, 3.5),
            'color': color,
            'vida': 1.0,
            'vida_decay': random.uniform(0.08, 0.16),  # Vida agil y rapida (~0.25s)
            'tam': random.randint(2, 3)
        })
    if not _animando_particulas:
        _animando_particulas = True
        root.after(25, animar_bucle_particulas)

def actualizar_y_dibujar_particulas():
    global particulas
    if not particulas:
        return
    particulas_vivas = []
    for p in particulas:
        p['x'] += p['vx']
        p['y'] += p['vy']
        p['vy'] += 0.35  # Gravedad dinamica veloz
        p['vx'] *= 0.93  # Friccion aerea para frenado organico
        p['vida'] -= p['vida_decay']
        if p['vida'] > 0:
            rad = max(1, int(p['tam'] * p['vida']))
            canvas.create_oval(p['x'] - rad, p['y'] - rad, p['x'] + rad, p['y'] + rad, fill=p['color'], outline="")
            particulas_vivas.append(p)
    particulas = particulas_vivas

"""
Estado y variables para Modo Versus (Doble Pantalla / Tetris 99)
"""
modo_juego = "SOLO"

tablero_rival: list[list[int | str]] = [[0 for _ in range(COLUMNAS)] for _ in range(FILAS)]
nombre_pieza_rival = obtener_siguiente_de_bolsa(es_rival=True)
nombre_siguiente_rival = obtener_siguiente_de_bolsa(es_rival=True)
pieza_actual_rival = PIEZAS[nombre_pieza_rival]
colores_actual_rival = COLORES[nombre_pieza_rival]
pos_x_rival = COLUMNAS // 2 - 1
pos_y_rival = 0
puntuacion_rival = 0
lineas_rival = 0
juego_terminado_rival = False

msg_ataque_p1 = ""
msg_ataque_p1_tiempo = 0.0
msg_ataque_rival = ""
msg_ataque_rival_tiempo = 0.0

codigo_sala_actual = ""
es_anfitrion_sala = True
estado_sala_online = "DESCONECTADO"
basura_pendiente_enviar = 0
hilo_sync_online = None
stop_sync_online = False

_cache_img_menu = None
_cache_menu_size = (0, 0)

"""
Escalado dinamico con cache para imagen de fondo del menu
"""
def obtener_imagen_menu_escalada(cw, ch):
    global _cache_img_menu, _cache_menu_size
    if _cache_img_menu is not None and _cache_menu_size == (cw, ch):
        return _cache_img_menu
    for nombre in ["casual blocks menu.png", "tetris menu.png"]:
        ruta_menu = obtener_ruta_recurso(os.path.join("img", nombre))
        if os.path.exists(ruta_menu):
            try:
                from PIL import Image, ImageTk
                img = Image.open(ruta_menu).resize((cw, ch), Image.Resampling.LANCZOS)
                _cache_img_menu = ImageTk.PhotoImage(img)
                _cache_menu_size = (cw, ch)
                return _cache_img_menu
            except Exception:
                pass
    return None

_cache_img_juego = None
_cache_juego_key = (-1, 0, 0, "")

def obtener_rutas_fondos_juego():
    nombres = ["game.png", "game2.png", "game 3.png", "game 4.png"]
    rutas = []
    for n in nombres:
        r = obtener_ruta_recurso(os.path.join("img", n))
        if os.path.exists(r):
            rutas.append(r)
    return rutas

def obtener_imagen_juego_escalada(idx, cw, ch):
    global _cache_img_juego, _cache_juego_key
    key = (idx, cw, ch, modo_juego)
    if _cache_img_juego is not None and _cache_juego_key == key:
        return _cache_img_juego
    rutas = obtener_rutas_fondos_juego()
    if not rutas:
        return None
    idx_real = idx % len(rutas)
    ruta_fondo = rutas[idx_real]
    if os.path.exists(ruta_fondo):
        try:
            from PIL import Image, ImageTk, ImageDraw
            img = Image.open(ruta_fondo).resize((cw, ch), Image.Resampling.LANCZOS).convert('RGBA')
            
            # Capa de cristal translúcido (Glassmorphism) para que el fondo se aprecie claramente con excelente contraste
            overlay = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            ancho_req = (ancho * 2 + 320) if modo_juego == "VERSUS" else (ancho + 180)
            off_x = max(0, (cw - ancho_req) // 2)
            off_y = max(0, (ch - alto) // 2)
            
            # Tinte suave detrás del tablero (deja ver el fondo nítidamente a través de la cuadrícula)
            draw.rectangle([off_x, off_y, off_x + ancho, off_y + alto], fill=(8, 8, 18, 120), outline=(0, 240, 255, 90), width=2)
            
            # Tinte suave detrás del panel lateral
            draw.rectangle([off_x + ancho + 6, off_y, off_x + ancho + 174, off_y + alto], fill=(12, 10, 24, 140), outline=(255, 0, 127, 80), width=2)
            
            if modo_juego == "VERSUS":
                off_r = off_x + ancho + 200
                draw.rectangle([off_r, off_y, off_r + ancho, off_y + alto], fill=(16, 8, 18, 120), outline=(255, 60, 60, 90), width=2)
            
            img = Image.alpha_composite(img, overlay)
            _cache_img_juego = ImageTk.PhotoImage(img)
            _cache_juego_key = key
            return _cache_img_juego
        except Exception:
            pass
    return None

def cambiar_fondo():
    global fondo_juego_actual
    rutas = obtener_rutas_fondos_juego()
    if rutas:
        fondo_juego_actual = (fondo_juego_actual + 1) % len(rutas)
    redibujar()

def seleccionar_fondo_aleatorio_juego(forzar_diferente=True):
    global fondo_juego_actual
    rutas = obtener_rutas_fondos_juego()
    if not rutas:
        return 0
    if len(rutas) > 1 and forzar_diferente:
        opciones = [i for i in range(len(rutas)) if i != (fondo_juego_actual % len(rutas))]
        fondo_juego_actual = random.choice(opciones)
    else:
        fondo_juego_actual = random.randrange(len(rutas))
    return fondo_juego_actual

# Inicializar con un fondo de juego aleatorio al arrancar
seleccionar_fondo_aleatorio_juego(forzar_diferente=False)

"""
Carga de canciones de fondo
"""
directorio_musica = obtener_ruta_recurso("music")
if os.path.exists(directorio_musica):
    lista_canciones = [f for f in os.listdir(directorio_musica) if f.lower().endswith(('.mp3', '.wav'))]
else:
    lista_canciones = []

cancion_actual_idx = 0
cancion_reproduciendose = None

"""
Reproductor de musica de fondo con Windows MCI
"""
def detener_musica():
    global cancion_reproduciendose
    try:
        if pygame_audio_disponible:
            import pygame
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        elif winmm and hasattr(winmm, 'mciSendStringW'):
            winmm.mciSendStringW('close bgm', None, 0, 0)
            winmm.mciSendStringW('close sfx_audio', None, 0, 0)
        cancion_reproduciendose = None
    except Exception:
        pass

def reproducir_audio_efecto(nombre_archivo):
    if not sonido_activado or not nombre_archivo:
        return
    ruta = os.path.abspath(os.path.join(directorio_musica, nombre_archivo))
    if os.path.exists(ruta):
        try:
            if pygame_audio_disponible:
                import pygame
                snd = pygame.mixer.Sound(ruta)
                snd.play()
            elif winmm and hasattr(winmm, 'mciSendStringW'):
                winmm.mciSendStringW('close sfx_audio', None, 0, 0)
                winmm.mciSendStringW(f'open "{ruta}" type mpegvideo alias sfx_audio', None, 0, 0)
                winmm.mciSendStringW('play sfx_audio', None, 0, 0)
        except Exception:
            pass

canciones_playlist_juego = []
cancion_actual_idx = 0

def obtener_canciones_juego():
    global canciones_playlist_juego
    canciones_especiales = ["menu.mp3", "pausa.mp3", "game over.mp3", "victoria.mp3"]
    cj = [f for f in lista_canciones if f.lower() not in canciones_especiales]
    canciones_playlist_juego = sorted(cj) if cj else list(lista_canciones)
    return canciones_playlist_juego

def seleccionar_cancion_aleatoria_juego(forzar_diferente=True):
    global cancion_actual_idx
    canciones = obtener_canciones_juego()
    if not canciones:
        return ""
    if len(canciones) > 1 and forzar_diferente:
        opciones = [i for i in range(len(canciones)) if i != (cancion_actual_idx % len(canciones))]
        cancion_actual_idx = random.choice(opciones)
    else:
        cancion_actual_idx = random.randrange(len(canciones))
    return canciones[cancion_actual_idx]

# Inicializar con una pista aleatoria para que no comience siempre en la misma
if lista_canciones:
    seleccionar_cancion_aleatoria_juego(forzar_diferente=False)

def esta_musica_sonando():
    if pygame_audio_disponible:
        try:
            import pygame
            return pygame.mixer.music.get_busy()
        except Exception:
            return False
    elif winmm and hasattr(winmm, 'mciSendStringW'):
        try:
            buf = ctypes.create_unicode_buffer(128)
            winmm.mciSendStringW('status bgm mode', buf, 128, 0)
            return buf.value.lower() == 'playing'
        except Exception:
            return False
    return False

def reproducir_musica_por_nombre(nombre_cancion, en_bucle=True, forzar=False):
    global cancion_reproduciendose
    if not musica_activada or not nombre_cancion:
        detener_musica()
        return
    if cancion_reproduciendose == nombre_cancion and not forzar and esta_musica_sonando():
        return
    try:
        detener_musica()
        ruta_cancion = os.path.abspath(os.path.join(directorio_musica, nombre_cancion))
        if pygame_audio_disponible:
            import pygame
            pygame.mixer.music.load(ruta_cancion)
            pygame.mixer.music.play(-1 if en_bucle else 0)
        elif winmm and hasattr(winmm, 'mciSendStringW'):
            repeat_flag = " repeat" if en_bucle else ""
            winmm.mciSendStringW(f'open "{ruta_cancion}" type mpegvideo alias bgm', None, 0, 0)
            winmm.mciSendStringW(f'play bgm{repeat_flag}', None, 0, 0)
        cancion_reproduciendose = nombre_cancion
    except Exception:
        pass

def actualizar_musica_estado(forzar_juego=False):
    if not musica_activada or not lista_canciones:
        detener_musica()
        return

    # Pantallas de menú y submenús: siempre deben sonar con la música del menú
    if estado_pantalla in ["MENU", "MODOS", "ONLINE", "AJUSTES"]:
        cancion_menu = next((f for f in lista_canciones if f.lower() == "menu.mp3"), None)
        if cancion_menu:
            reproducir_musica_por_nombre(cancion_menu, en_bucle=True)
        else:
            detener_musica()
    elif estado_pantalla == "JUEGO":
        if modo_juego == "VERSUS" and juego_terminado_rival and not juego_terminado:
            cancion_vic = next((f for f in lista_canciones if f.lower() == "victoria.mp3"), None)
            if cancion_vic:
                reproducir_musica_por_nombre(cancion_vic, en_bucle=True)
            else:
                detener_musica()
        elif juego_terminado or (modo_juego == "VERSUS" and juego_terminado_rival):
            cancion_go = next((f for f in lista_canciones if f.lower() == "game over.mp3"), None)
            if cancion_go:
                reproducir_musica_por_nombre(cancion_go, en_bucle=False)
            else:
                detener_musica()
        elif juego_en_pausa:
            cancion_pausa = next((f for f in lista_canciones if f.lower() == "pausa.mp3"), None)
            if cancion_pausa:
                reproducir_musica_por_nombre(cancion_pausa, en_bucle=True)
            else:
                detener_musica()
        else:
            canciones = obtener_canciones_juego()
            if canciones:
                # Si ya esta reproduciendose una pista valida de partida, respetarla sin interrumpir (salvo inicio/reinicio de partida)
                if not forzar_juego and cancion_reproduciendose in canciones and esta_musica_sonando():
                    pass
                else:
                    nombre_cancion = canciones[cancion_actual_idx % len(canciones)]
                    reproducir_musica_por_nombre(nombre_cancion, en_bucle=False, forzar=forzar_juego)
            else:
                detener_musica()
    else:
        detener_musica()

def cambiar_cancion():
    global cancion_actual_idx
    canciones = obtener_canciones_juego()
    if not canciones:
        return
    cancion_actual_idx = (cancion_actual_idx + 1) % len(canciones)
    nombre_cancion = canciones[cancion_actual_idx]
    reproducir_musica_por_nombre(nombre_cancion, en_bucle=False, forzar=True)
    redibujar()

def verificar_musica_continua():
    global cancion_actual_idx
    try:
        if musica_activada and estado_pantalla == "JUEGO" and not juego_en_pausa and not juego_terminado and not (modo_juego == "VERSUS" and juego_terminado_rival):
            if not esta_musica_sonando() and cancion_reproduciendose is not None:
                canciones = obtener_canciones_juego()
                if canciones:
                    seleccionar_cancion_aleatoria_juego(forzar_diferente=True)
                    siguiente = canciones[cancion_actual_idx % len(canciones)]
                    reproducir_musica_por_nombre(siguiente, en_bucle=False, forzar=True)
    except Exception:
        pass
    root.after(500, verificar_musica_continua)

"""
Sintetizador avanzado y reproductor multicanal de efectos de sonido
"""
SND_ASYNC = 0x0001
SND_MEMORY = 0x0004

def generar_wav_avanzado(lista_segmentos, sample_rate=44100, volumen=0.35):
    """
    Genera audio WAV en memoria a partir de una lista de segmentos.
    Cada segmento es: (f_inicio, f_fin, duracion_ms, tipo_onda, vol_rel)
    tipo_onda: "sine", "square", "triangle", "noise"
    """
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for seg in lista_segmentos:
            f_start = seg[0]
            f_end = seg[1] if len(seg) > 1 and seg[1] is not None else f_start
            dur_ms = seg[2] if len(seg) > 2 else 50
            onda = seg[3] if len(seg) > 3 else "sine"
            vol_rel = seg[4] if len(seg) > 4 else 1.0

            n_samples = max(1, int(sample_rate * (dur_ms / 1000.0)))
            fase = 0.0
            for i in range(n_samples):
                progreso = i / n_samples
                freq = f_start + (f_end - f_start) * progreso
                fase += 2 * math.pi * freq / sample_rate

                if progreso < 0.05:
                    env = progreso / 0.05
                else:
                    env = max(0.0, 1.0 - (progreso - 0.05) / 0.95)

                if onda == "square":
                    val = 0.55 if math.sin(fase) >= 0 else -0.55
                elif onda == "triangle":
                    val = (2 / math.pi) * math.asin(max(-1.0, min(1.0, math.sin(fase))))
                elif onda == "noise":
                    val = (random.random() * 2.0 - 1.0) * 0.7
                else:
                    val = math.sin(fase)

                sample = int(val * env * volumen * vol_rel * 32767)
                sample = max(-32768, min(32767, sample))
                frames.extend(struct.pack('<h', sample))
        wf.writeframes(frames)
    return buffer.getvalue()

EFECTOS_SONIDO = {
    # Movimiento y rotacion
    "mover": generar_wav_avanzado([(520, 470, 16, "sine", 0.35)]),
    "rotar": generar_wav_avanzado([(600, 850, 26, "triangle", 0.4)]),
    "hold": generar_wav_avanzado([(380, 520, 20, "triangle", 0.45), (520, 720, 24, "sine", 0.5)]),
    
    # Caida y fijacion
    "fijar": generar_wav_avanzado([(240, 120, 28, "triangle", 0.5)]),
    "hard_drop": generar_wav_avanzado([(200, 50, 25, "noise", 0.65), (150, 40, 70, "triangle", 0.7)]),

    # Limpieza de lineas escalonada
    "limpiar": generar_wav_avanzado([(659, 659, 45, "sine", 0.5), (784, 784, 60, "sine", 0.6)]),
    "limpiar_1": generar_wav_avanzado([(659, 659, 45, "sine", 0.5), (784, 784, 60, "sine", 0.6)]),
    "limpiar_2": generar_wav_avanzado([(659, 659, 40, "triangle", 0.5), (784, 784, 40, "triangle", 0.55), (988, 988, 70, "triangle", 0.65)]),
    "limpiar_3": generar_wav_avanzado([(659, 659, 35, "triangle", 0.5), (784, 784, 35, "triangle", 0.55), (988, 988, 35, "triangle", 0.6), (1318, 1318, 80, "triangle", 0.7)]),
    "tetris": generar_wav_avanzado([
        (130, 90, 40, "triangle", 0.7),
        (523, 523, 40, "sine", 0.6),
        (659, 659, 40, "sine", 0.6),
        (784, 784, 40, "sine", 0.65),
        (1046, 1046, 50, "triangle", 0.7),
        (1318, 1318, 50, "triangle", 0.75),
        (1568, 1568, 60, "triangle", 0.8),
        (2093, 2093, 120, "triangle", 0.85)
    ]),

    # Sistema, combos, bombas y UI
    "explosion": generar_wav_avanzado([
        (160, 40, 60, "noise", 0.8),
        (110, 30, 90, "triangle", 0.85),
        (70, 20, 140, "triangle", 0.9),
        (45, 10, 180, "noise", 0.7)
    ]),
    "combo": generar_wav_avanzado([(659, 780, 40, "sine", 0.5), (880, 1046, 60, "triangle", 0.6)]),
    "level_up": generar_wav_avanzado([(523, 523, 35, "triangle", 0.6), (659, 659, 35, "triangle", 0.65), (784, 784, 35, "triangle", 0.7), (1046, 1046, 70, "triangle", 0.75), (1318, 1318, 100, "triangle", 0.8)]),
    "game_over": generar_wav_avanzado([(392, 370, 70, "square", 0.5), (370, 349, 70, "square", 0.5), (349, 330, 80, "square", 0.5), (330, 220, 120, "square", 0.55)]),
    "record": generar_wav_avanzado([(784, 784, 40, "triangle", 0.6), (1046, 1046, 40, "triangle", 0.65), (1318, 1318, 50, "triangle", 0.7), (1568, 1568, 80, "triangle", 0.8)]),
    "menu_move": generar_wav_avanzado([(600, 600, 14, "sine", 0.35)]),
    "menu_select": generar_wav_avanzado([(500, 750, 30, "triangle", 0.45)])
}

SONIDOS_PYGAME = {}
if pygame_audio_disponible:
    try:
        import pygame
        pygame.mixer.set_num_channels(16)
        for k, wav_data in EFECTOS_SONIDO.items():
            SONIDOS_PYGAME[k] = pygame.mixer.Sound(io.BytesIO(wav_data))
    except Exception:
        SONIDOS_PYGAME = {}

def reproducir_sonido(tipo):
    if not sonido_activado:
        return
    if pygame_audio_disponible and tipo in SONIDOS_PYGAME:
        try:
            import pygame
            snd = SONIDOS_PYGAME[tipo]
            if tipo in ["mover", "rotar"]:
                pygame.mixer.Channel(0).play(snd)
            elif tipo in ["fijar", "hard_drop", "hold"]:
                pygame.mixer.Channel(1).play(snd)
            elif tipo.startswith("limpiar") or tipo in ["tetris", "combo", "explosion"]:
                pygame.mixer.Channel(2).play(snd)
            elif tipo in ["level_up", "game_over", "record"]:
                pygame.mixer.Channel(3).play(snd)
            else:
                snd.play()
            return
        except Exception:
            pass
    if tipo in EFECTOS_SONIDO:
        try:
            play_sound = getattr(winsound, "PlaySound", None)
            snd_memory = getattr(winsound, "SND_MEMORY", 4)
            snd_async = getattr(winsound, "SND_ASYNC", 1)
            if play_sound:
                play_sound(EFECTOS_SONIDO[tipo], snd_memory | snd_async)
        except Exception:
            pass

def reproducir_sonido_combo(combo_num):
    if not sonido_activado:
        return
    f = int(520 * (1.11 ** min(10, max(1, combo_num))))
    seg = [
        (f, int(f * 1.15), 45, "sine", 0.55),
        (int(f * 1.25), int(f * 1.35), 65, "triangle", 0.65)
    ]
    wav_data = generar_wav_avanzado(seg, volumen=0.35)
    if pygame_audio_disponible:
        try:
            import pygame
            snd = pygame.mixer.Sound(io.BytesIO(wav_data))
            pygame.mixer.Channel(2).play(snd)
            return
        except Exception:
            pass
    try:
        play_sound = getattr(winsound, "PlaySound", None)
        snd_memory = getattr(winsound, "SND_MEMORY", 4)
        snd_async = getattr(winsound, "SND_ASYNC", 1)
        if play_sound:
            play_sound(wav_data, snd_memory | snd_async)
    except Exception:
        pass

"""
Reproduccion del video de intro
"""
def reproducir_intro_video():
    global cap_intro, video_reproduciendose, estado_pantalla, tiempo_inicio_intro, num_frame_actual
    ruta_video = obtener_ruta_recurso(os.path.join("media", "Rueda_del_zodiaco_girando_202608131229.mp4"))
    ruta_audio = obtener_ruta_recurso(os.path.join("media", "intro.mp3"))
    if not os.path.exists(ruta_video):
        finalizar_intro()
        return
    try:
        import cv2
        cap_intro = cv2.VideoCapture(ruta_video)
        if not cap_intro.isOpened():
            finalizar_intro()
            return
        detener_musica()
        if os.path.exists(ruta_audio):
            ruta_abs = os.path.abspath(ruta_audio)
            if pygame_audio_disponible:
                import pygame
                pygame.mixer.music.load(ruta_abs)
                pygame.mixer.music.play(0)
            elif winmm and hasattr(winmm, 'mciSendStringW'):
                winmm.mciSendStringW('close intro_audio', None, 0, 0)
                winmm.mciSendStringW(f'open "{ruta_abs}" alias intro_audio', None, 0, 0)
                winmm.mciSendStringW('play intro_audio', None, 0, 0)
        video_reproduciendose = True
        tiempo_inicio_intro = time.time()
        num_frame_actual = 0
        actualizar_frame_video()
    except Exception:
        finalizar_intro()

def actualizar_frame_video():
    global cap_intro, video_reproduciendose, imagen_intro_tk, estado_pantalla, num_frame_actual, tiempo_inicio_intro
    if not video_reproduciendose or cap_intro is None or estado_pantalla != "INTRO":
        finalizar_intro()
        return
    try:
        import cv2
        from PIL import Image, ImageTk
        fps = cap_intro.get(cv2.CAP_PROP_FPS)
        fps = fps if fps and fps > 0 else 24.0
        tiempo_transcurrido = time.time() - tiempo_inicio_intro
        target_frame = int(tiempo_transcurrido * fps) + 1
        frame = None
        ret = False
        while num_frame_actual < target_frame:
            ret, frame = cap_intro.read()
            num_frame_actual += 1
            if not ret or frame is None:
                finalizar_intro()
                return
        if frame is not None:
            ancho_total = COLUMNAS * TAMANO_BLOQUE + 180
            alto_total = FILAS * TAMANO_BLOQUE
            frame_resized = cv2.resize(frame, (ancho_total, alto_total), interpolation=cv2.INTER_LINEAR)
            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            imagen_intro_tk = ImageTk.PhotoImage(image=img)
            canvas.delete("all")
            canvas.create_image(0, 0, image=imagen_intro_tk, anchor="nw")
            canvas.create_text(ancho_total // 2, alto_total - 25, text="Haz clic o presiona cualquier tecla para omitir", fill="#ffffff", font=("Arial", 10, "bold"))
        proximo_tiempo_target = (num_frame_actual + 1) / fps
        tiempo_para_esperar = proximo_tiempo_target - (time.time() - tiempo_inicio_intro)
        delay_ms = max(5, int(tiempo_para_esperar * 1000))
        root.after(delay_ms, actualizar_frame_video)
    except Exception:
        finalizar_intro()

def finalizar_intro(event=None):
    global cap_intro, video_reproduciendose, estado_pantalla
    if estado_pantalla != "INTRO" and not video_reproduciendose:
        return
    video_reproduciendose = False
    try:
        if pygame_audio_disponible:
            import pygame
            pygame.mixer.music.stop()
        elif winmm and hasattr(winmm, 'mciSendStringW'):
            winmm.mciSendStringW('close intro_audio', None, 0, 0)
    except Exception:
        pass
    if cap_intro is not None:
        try:
            cap_intro.release()
        except Exception:
            pass
        cap_intro = None
    estado_pantalla = "MENU"
    actualizar_musica_estado()
    redibujar()

def obtener_posicion_sombra():
    g_y = pos_y
    while es_valido(pieza_actual, pos_x, g_y + 1):
        g_y += 1
    return g_y

def dibujar_pieza():
    off_x, off_y, _, _ = obtener_offset_pantalla()
    g_y = obtener_posicion_sombra()
    if g_y != pos_y:
        col_sombra = PALETA_BLOQUES.get(colores_actual, {}).get('luz', '#00e5ff')
        for f_idx, fila in enumerate(pieza_actual):
            for c_idx, valor in enumerate(fila):
                if valor:
                    x1 = off_x + (pos_x + c_idx) * TAMANO_BLOQUE
                    y1 = off_y + (g_y + f_idx) * TAMANO_BLOQUE
                    x2 = x1 + TAMANO_BLOQUE
                    y2 = y1 + TAMANO_BLOQUE
                    canvas.create_rectangle(x1 + 1, y1 + 1, x2 - 1, y2 - 1, outline=col_sombra, fill="", width=2)

    for f_idx, fila in enumerate(pieza_actual):
        for c_idx, valor in enumerate(fila):
            if valor:
                x1 = off_x + (pos_x + c_idx) * TAMANO_BLOQUE
                y1 = off_y + (pos_y + f_idx) * TAMANO_BLOQUE
                x2 = x1 + TAMANO_BLOQUE
                y2 = y1 + TAMANO_BLOQUE
                dibujar_bloque_3d(x1, y1, x2, y2, colores_actual)

    if modo_juego == "VERSUS":
        off_rival_x = off_x + ancho + 200
        for f_idx, fila in enumerate(pieza_actual_rival):
            for c_idx, valor in enumerate(fila):
                if valor:
                    x1 = off_rival_x + (pos_x_rival + c_idx) * TAMANO_BLOQUE
                    y1 = off_y + (pos_y_rival + f_idx) * TAMANO_BLOQUE
                    x2 = x1 + TAMANO_BLOQUE
                    y2 = y1 + TAMANO_BLOQUE
                    dibujar_bloque_3d(x1, y1, x2, y2, colores_actual_rival)

"""
Funciones de Ataque de Basura y Rival IA (Estilo Tetris 99)
"""
def agregar_lineas_basura(tab, cant):
    if cant <= 0:
        return
    for _ in range(cant):
        tab.pop(0)
        hueco = random.randint(0, COLUMNAS - 1)
        nueva_fila = ["#555566" if c != hueco else 0 for c in range(COLUMNAS)]
        tab.append(nueva_fila)

def es_valido_rival(pieza, p_x, p_y):
    for f_idx, fila in enumerate(pieza):
        for c_idx, valor in enumerate(fila):
            if valor:
                x = p_x + c_idx
                y = p_y + f_idx
                if x < 0 or x >= COLUMNAS or y >= FILAS:
                    return False
                if y >= 0 and tablero_rival[y][x] != 0:
                    return False
    return True

def fijar_pieza_rival():
    global pieza_actual_rival, colores_actual_rival, pos_x_rival, pos_y_rival, nombre_pieza_rival, nombre_siguiente_rival, juego_terminado_rival
    for f_idx, fila in enumerate(pieza_actual_rival):
        for c_idx, valor in enumerate(fila):
            if valor:
                if 0 <= pos_y_rival + f_idx < FILAS and 0 <= pos_x_rival + c_idx < COLUMNAS:
                    tablero_rival[pos_y_rival + f_idx][pos_x_rival + c_idx] = colores_actual_rival

    limpiar_filas_rival()
    nombre_pieza_rival = nombre_siguiente_rival
    nombre_siguiente_rival = obtener_siguiente_de_bolsa(es_rival=True)
    pieza_actual_rival = PIEZAS[nombre_pieza_rival]
    colores_actual_rival = COLORES[nombre_pieza_rival]
    pos_x_rival = COLUMNAS // 2 - 1
    pos_y_rival = 0

    if not es_valido_rival(pieza_actual_rival, pos_x_rival, pos_y_rival):
        juego_terminado_rival = True
        detener_timers_juego()
        actualizar_musica_estado()
        redibujar()

def limpiar_filas_rival():
    global tablero_rival, puntuacion_rival, lineas_rival, msg_ataque_p1, msg_ataque_p1_tiempo
    nuevas = [f for f in tablero_rival if any(v == 0 for v in f)]
    eliminadas = FILAS - len(nuevas)
    if eliminadas > 0:
        filas_vacias: list[list[int | str]] = [[0 for _ in range(COLUMNAS)] for _ in range(eliminadas)]
        tablero_rival = filas_vacias + nuevas
        lineas_rival += eliminadas
        puntuacion_rival += eliminadas * 150

        filas_ataque = 0
        if eliminadas == 2: filas_ataque = 1
        elif eliminadas == 3: filas_ataque = 2
        elif eliminadas == 4: filas_ataque = 4

        if modo_juego == "VERSUS" and filas_ataque > 0:
            agregar_lineas_basura(tablero, filas_ataque)
            msg_ataque_p1 = f"⚠️ ¡BASURA RECIBIDA +{filas_ataque}!"
            msg_ataque_p1_tiempo = time.time()

def caer_rival():
    global pos_y_rival, pos_x_rival, timer_caer_rival
    if timer_caer_rival is not None:
        try:
            root.after_cancel(timer_caer_rival)
        except Exception:
            pass
        timer_caer_rival = None

    if estado_pantalla != "JUEGO" or modo_juego != "VERSUS" or juego_terminado_rival or juego_en_pausa or juego_terminado:
        return

    if random.random() < 0.35:
        dx = random.choice([-1, 1])
        if es_valido_rival(pieza_actual_rival, pos_x_rival + dx, pos_y_rival):
            pos_x_rival += dx

    if es_valido_rival(pieza_actual_rival, pos_x_rival, pos_y_rival + 1):
        pos_y_rival += 1
    else:
        fijar_pieza_rival()

    redibujar()
    timer_caer_rival = root.after(350, caer_rival)

def caida_instantanea(event=None):
    global pos_y, puntuacion
    if estado_pantalla != "JUEGO" or juego_terminado or juego_en_pausa or (modo_juego == "VERSUS" and juego_terminado_rival):
        return
    pasos = 0
    while es_valido(pieza_actual, pos_x, pos_y + 1):
        pos_y += 1
        pasos += 1
    puntuacion += pasos * 2

    # Particulas de chispas neón en la base del impacto
    off_x, off_y, _, _ = obtener_offset_pantalla()
    base_x = off_x + (pos_x + len(pieza_actual[0]) / 2.0) * TAMANO_BLOQUE
    base_y = off_y + (pos_y + len(pieza_actual)) * TAMANO_BLOQUE
    col_part = PALETA_BLOQUES.get(colores_actual, {}).get('luz', '#00ffff')
    agregar_particulas_impacto(base_x, base_y, color=col_part, cantidad=14, velocidad=5.0)

    cancelar_lock_delay()
    reproducir_sonido("hard_drop")
    fijar_pieza(es_hard_drop=True)
    if juego_terminado or (modo_juego == "VERSUS" and juego_terminado_rival):
        return
    redibujar()
    reiniciar_timer_caer()

"""
Sistema de controles fluidos DAS / ARR (Eliminacion de Input Lag)
"""
DAS_DELAY_MS = 140   # Retraso inicial antes de repetir desplazamiento
ARR_REPEAT_MS = 35   # Intervalo de desplazamiento continuo fluido
SOFT_DROP_MS = 40    # Intervalo para caida rapida suave

teclas_estado = {
    'left': False,
    'right': False,
    'down': False
}
timer_das_left = None
timer_das_right = None
timer_das_down = None

def cancelar_das_timers():
    global timer_das_left, timer_das_right, timer_das_down
    teclas_estado['left'] = False
    teclas_estado['right'] = False
    teclas_estado['down'] = False
    for t_ref in [timer_das_left, timer_das_right, timer_das_down]:
        if t_ref is not None:
            try:
                root.after_cancel(t_ref)
            except Exception:
                pass
    timer_das_left = None
    timer_das_right = None
    timer_das_down = None

def bucle_das_left():
    global timer_das_left
    if teclas_estado['left'] and estado_pantalla == "JUEGO" and not juego_en_pausa and not juego_terminado and not (modo_juego == "VERSUS" and juego_terminado_rival):
        mover(-1, con_sonido=False)
        timer_das_left = root.after(ARR_REPEAT_MS, bucle_das_left)
    else:
        timer_das_left = None

def iniciar_das_left():
    global timer_das_left
    if timer_das_left is not None:
        try:
            root.after_cancel(timer_das_left)
        except Exception:
            pass
    timer_das_left = root.after(DAS_DELAY_MS, bucle_das_left)

def bucle_das_right():
    global timer_das_right
    if teclas_estado['right'] and estado_pantalla == "JUEGO" and not juego_en_pausa and not juego_terminado and not (modo_juego == "VERSUS" and juego_terminado_rival):
        mover(1, con_sonido=False)
        timer_das_right = root.after(ARR_REPEAT_MS, bucle_das_right)
    else:
        timer_das_right = None

def iniciar_das_right():
    global timer_das_right
    if timer_das_right is not None:
        try:
            root.after_cancel(timer_das_right)
        except Exception:
            pass
    timer_das_right = root.after(DAS_DELAY_MS, bucle_das_right)

def bucle_das_down():
    global timer_das_down
    if teclas_estado['down'] and estado_pantalla == "JUEGO" and not juego_en_pausa and not juego_terminado and not (modo_juego == "VERSUS" and juego_terminado_rival):
        bajar_rapido()
        timer_das_down = root.after(SOFT_DROP_MS, bucle_das_down)
    else:
        timer_das_down = None

def iniciar_das_down():
    global timer_das_down
    if timer_das_down is not None:
        try:
            root.after_cancel(timer_das_down)
        except Exception:
            pass
    timer_das_down = root.after(DAS_DELAY_MS, bucle_das_down)

def on_press_left(event=None):
    if estado_pantalla == "AJUSTES":
        navegar_horizontal_ajustes(-1)
    elif estado_pantalla == "JUEGO":
        if not teclas_estado['left']:
            teclas_estado['left'] = True
            mover(-1, con_sonido=True)
            iniciar_das_left()

def on_release_left(event=None):
    global timer_das_left
    teclas_estado['left'] = False
    if timer_das_left is not None:
        try:
            root.after_cancel(timer_das_left)
        except Exception:
            pass
        timer_das_left = None

def on_press_right(event=None):
    if estado_pantalla == "AJUSTES":
        navegar_horizontal_ajustes(1)
    elif estado_pantalla == "JUEGO":
        if not teclas_estado['right']:
            teclas_estado['right'] = True
            mover(1, con_sonido=True)
            iniciar_das_right()

def on_release_right(event=None):
    global timer_das_right
    teclas_estado['right'] = False
    if timer_das_right is not None:
        try:
            root.after_cancel(timer_das_right)
        except Exception:
            pass
        timer_das_right = None

def on_press_down(event=None):
    if estado_pantalla in ["MENU", "MODOS", "ONLINE", "AJUSTES"]:
        navegar_menu(1)
    elif estado_pantalla == "JUEGO":
        if not teclas_estado['down']:
            teclas_estado['down'] = True
            bajar_rapido()
            iniciar_das_down()

def on_release_down(event=None):
    global timer_das_down
    teclas_estado['down'] = False
    if timer_das_down is not None:
        try:
            root.after_cancel(timer_das_down)
        except Exception:
            pass
        timer_das_down = None

def on_press_up(event=None):
    if estado_pantalla in ["MENU", "MODOS", "ONLINE", "AJUSTES"]:
        navegar_menu(-1)
    elif estado_pantalla == "JUEGO":
        intentar_rotar()

"""
Sistema de Lock Delay oficial (0.5s de margen de maniobra en el suelo)
"""
LOCK_DELAY_MS = 500
MAX_LOCK_RESETS = 15

timer_lock_delay = None
en_lock_delay = False
resets_lock_delay = 0

def cancelar_lock_delay():
    global timer_lock_delay, en_lock_delay, resets_lock_delay
    if timer_lock_delay is not None:
        try:
            root.after_cancel(timer_lock_delay)
        except Exception:
            pass
        timer_lock_delay = None
    en_lock_delay = False
    resets_lock_delay = 0

def ejecutar_fijar_por_lock_delay():
    global timer_lock_delay, en_lock_delay
    timer_lock_delay = None
    en_lock_delay = False
    if estado_pantalla != "JUEGO" or juego_terminado or juego_en_pausa or (modo_juego == "VERSUS" and juego_terminado_rival):
        return
    if es_valido(pieza_actual, pos_x, pos_y + 1):
        caer()
        return
    fijar_pieza(es_hard_drop=False)
    if juego_terminado or (modo_juego == "VERSUS" and juego_terminado_rival):
        return
    redibujar()
    reiniciar_timer_caer()

def iniciar_lock_delay():
    global timer_lock_delay, en_lock_delay
    if timer_lock_delay is not None:
        try:
            root.after_cancel(timer_lock_delay)
        except Exception:
            pass
    en_lock_delay = True
    timer_lock_delay = root.after(LOCK_DELAY_MS, ejecutar_fijar_por_lock_delay)

def refrescar_lock_delay_si_aplica():
    global timer_lock_delay, en_lock_delay, resets_lock_delay
    if not es_valido(pieza_actual, pos_x, pos_y + 1):
        if not en_lock_delay:
            iniciar_lock_delay()
        elif resets_lock_delay < MAX_LOCK_RESETS:
            resets_lock_delay += 1
            if timer_lock_delay is not None:
                try:
                    root.after_cancel(timer_lock_delay)
                except Exception:
                    pass
            timer_lock_delay = root.after(LOCK_DELAY_MS, ejecutar_fijar_por_lock_delay)
    else:
        cancelar_lock_delay()

def mover(dx, con_sonido=True):
    global pos_x
    if estado_pantalla != "JUEGO" or juego_terminado or juego_en_pausa or (modo_juego == "VERSUS" and juego_terminado_rival):
        return False
    if es_valido(pieza_actual, pos_x + dx, pos_y):
        pos_x += dx
        if con_sonido:
            reproducir_sonido("mover")
        refrescar_lock_delay_si_aplica()
        redibujar()
        return True
    return False

def detener_timers_juego():
    global timer_caer, timer_caer_rival, timer_modo_tick, timer_survival
    cancelar_das_timers()
    cancelar_lock_delay()
    if timer_caer is not None:
        try:
            root.after_cancel(timer_caer)
        except Exception:
            pass
        timer_caer = None
    if timer_caer_rival is not None:
        try:
            root.after_cancel(timer_caer_rival)
        except Exception:
            pass
        timer_caer_rival = None
    if timer_modo_tick is not None:
        try:
            root.after_cancel(timer_modo_tick)
        except Exception:
            pass
        timer_modo_tick = None
    if timer_survival is not None:
        try:
            root.after_cancel(timer_survival)
        except Exception:
            pass
        timer_survival = None

def reiniciar_timer_caer():
    global timer_caer
    if timer_caer is not None:
        try:
            root.after_cancel(timer_caer)
        except Exception:
            pass
        timer_caer = None

    if estado_pantalla != "JUEGO" or juego_terminado or juego_en_pausa or (modo_juego == "VERSUS" and juego_terminado_rival):
        return

    if modo_individual == "POWERUPS" and time.time() < tiempo_congelado_hasta:
        velocidad = 2800
    else:
        nivel = min(10, 1 + puntuacion // 1000)
        velocidad = max(80, 500 - (nivel - 1) * 45)
        es_panico = any(any(val != 0 for val in fila) for fila in tablero[:7])
        if es_panico:
            velocidad = max(50, int(velocidad * 0.6))
    timer_caer = root.after(velocidad, caer)

def caer():
    global pos_y, timer_caer
    if timer_caer is not None:
        try:
            root.after_cancel(timer_caer)
        except Exception:
            pass
        timer_caer = None

    if estado_pantalla != "JUEGO" or juego_terminado or juego_en_pausa or (modo_juego == "VERSUS" and juego_terminado_rival):
        return

    if es_valido(pieza_actual, pos_x, pos_y + 1):
        pos_y += 1
        cancelar_lock_delay()
        redibujar()
    else:
        if not en_lock_delay:
            iniciar_lock_delay()
        return

    reiniciar_timer_caer()

def es_valido(pieza, p_x, p_y):
    for f_idx, fila in enumerate(pieza):
        for c_idx, valor in enumerate(fila):
            if valor:
                x = p_x + c_idx
                y = p_y + f_idx
                if x < 0 or x >= COLUMNAS or y >= FILAS:
                    return False
                if y >= 0 and tablero[y][x] != 0:
                    return False
    return True

def rotar(pieza):
    return [list(fila) for fila in zip(*pieza[::-1])]

def intentar_rotar():
    global pieza_actual, pos_x, pos_y
    if estado_pantalla != "JUEGO" or juego_terminado or juego_en_pausa or (modo_juego == "VERSUS" and juego_terminado_rival):
        return
    nueva = rotar(pieza_actual)
    # Wall kicks (SRS): probar desplazamientos si hay colision con paredes o suelo
    desplazamientos = [
        (0, 0),    # Rotacion normal
        (-1, 0),   # 1 casilla izquierda (pegado pared derecha)
        (1, 0),    # 1 casilla derecha (pegado pared izquierda)
        (-2, 0),   # 2 casillas izquierda (para barra 'I')
        (2, 0),    # 2 casillas derecha (para barra 'I')
        (0, -1),   # 1 casilla arriba (floor kick cerca del fondo)
        (-1, -1),  # diagonal izquierda arriba
        (1, -1),   # diagonal derecha arriba
    ]
    for dx, dy in desplazamientos:
        if es_valido(nueva, pos_x + dx, pos_y + dy):
            pos_x += dx
            pos_y += dy
            pieza_actual = nueva
            reproducir_sonido("rotar")
            refrescar_lock_delay_si_aplica()
            redibujar()
            return

def dibujar_miniatura(nombre, offset_x, offset_y):
    if nombre in PIEZAS:
        pieza_m = PIEZAS[nombre]
        color_m = COLORES[nombre]
        for f_idx, fila in enumerate(pieza_m):
            for c_idx, valor in enumerate(fila):
                if valor:
                    x1 = offset_x + c_idx * 18
                    y1 = offset_y + f_idx * 18
                    x2 = x1 + 18
                    y2 = y1 + 18
                    dibujar_bloque_3d(x1, y1, x2, y2, color_m, bevel=2)

def dibujar_panel():
    off_x, off_y, _, _ = obtener_offset_pantalla()
    # Marco lateral translúcido (no tapa el fondo)
    canvas.create_rectangle(off_x + ancho, off_y + 0, off_x + ancho + 180, off_y + alto, fill="", outline="")
    nivel = min(10, 1 + puntuacion // 1000)

    if modo_individual == "SPRINT":
        dt = max(0.0, (time.time() - tiempo_inicio_modo - tiempo_pausado_total)) if not juego_terminado else tiempo_final_sprint
        mins = int(dt // 60)
        segs = int(dt % 60)
        dec = int((dt * 10) % 10)
        str_tiempo = f"{mins:02d}:{segs:02d}.{dec}"

        canvas.create_rectangle(off_x + ancho + 10, off_y + 10, off_x + ancho + 170, off_y + 55, fill="", outline="#00e5ff", width=2)
        canvas.create_text(off_x + ancho + 90, off_y + 22, text="TIEMPO SPRINT", fill="#a0e5ff", font=("Arial", 8, "bold"))
        canvas.create_text(off_x + ancho + 90, off_y + 40, text=str_tiempo, fill="#00ffff", font=("Arial", 12, "bold"))

        lineas_rest = max(0, lineas_objetivo_sprint - lineas_totales)
        canvas.create_rectangle(off_x + ancho + 10, off_y + 65, off_x + ancho + 170, off_y + 110, fill="", outline="#36364d")
        canvas.create_text(off_x + ancho + 90, off_y + 77, text="LÍNEAS RESTANTES", fill="#a0a0c0", font=("Arial", 7, "bold"))
        canvas.create_text(off_x + ancho + 90, off_y + 95, text=f"{lineas_rest} / {lineas_objetivo_sprint}", fill="#ffd700", font=("Arial", 12, "bold"))
    elif modo_individual == "BLITZ":
        dt = max(0.0, (time.time() - tiempo_inicio_modo - tiempo_pausado_total)) if not juego_terminado else duracion_blitz_seg
        rem = max(0, duracion_blitz_seg - int(dt))
        mins = rem // 60
        segs = rem % 60
        str_rem = f"{mins:02d}:{segs:02d}"
        col_t = "#ff4444" if rem <= 20 else ("#ffd700" if rem <= 45 else "#00ff88")

        canvas.create_rectangle(off_x + ancho + 10, off_y + 10, off_x + ancho + 170, off_y + 55, fill="", outline=col_t, width=2)
        canvas.create_text(off_x + ancho + 90, off_y + 22, text="TIEMPO RESTANTE", fill="#ffa0c0", font=("Arial", 8, "bold"))
        canvas.create_text(off_x + ancho + 90, off_y + 40, text=str_rem, fill=col_t, font=("Arial", 13, "bold"))

        canvas.create_rectangle(off_x + ancho + 10, off_y + 65, off_x + ancho + 170, off_y + 110, fill="", outline="#36364d")
        canvas.create_text(off_x + ancho + 90, off_y + 77, text="PUNTOS BLITZ", fill="#a0a0c0", font=("Arial", 8, "bold"))
        canvas.create_text(off_x + ancho + 90, off_y + 95, text=str(puntuacion), fill="#ffd700", font=("Arial", 12, "bold"))
    elif modo_individual == "SURVIVAL":
        canvas.create_rectangle(off_x + ancho + 10, off_y + 10, off_x + ancho + 170, off_y + 55, fill="", outline="#ff5500", width=2)
        canvas.create_text(off_x + ancho + 90, off_y + 22, text="SUPERVIVENCIA", fill="#ffaa80", font=("Arial", 8, "bold"))
        canvas.create_text(off_x + ancho + 90, off_y + 40, text=f"OLEADA {oleada_survival}", fill="#ff5500", font=("Arial", 11, "bold"))

        canvas.create_rectangle(off_x + ancho + 10, off_y + 65, off_x + ancho + 170, off_y + 110, fill="", outline="#36364d")
        canvas.create_text(off_x + ancho + 90, off_y + 77, text="PUNTOS", fill="#a0a0c0", font=("Arial", 8, "bold"))
        canvas.create_text(off_x + ancho + 90, off_y + 95, text=str(puntuacion), fill="#ffd700", font=("Arial", 12, "bold"))
    elif modo_individual == "CAOS":
        canvas.create_rectangle(off_x + ancho + 10, off_y + 10, off_x + ancho + 170, off_y + 55, fill="", outline="#e056fd", width=2)
        canvas.create_text(off_x + ancho + 90, off_y + 22, text="MODO CAOS", fill="#ff77ff", font=("Arial", 8, "bold"))
        canvas.create_text(off_x + ancho + 90, off_y + 40, text="PIEZAS TRAMPA", fill="#ffd700", font=("Arial", 10, "bold"))

        canvas.create_rectangle(off_x + ancho + 10, off_y + 65, off_x + ancho + 170, off_y + 110, fill="", outline="#36364d")
        canvas.create_text(off_x + ancho + 90, off_y + 77, text="PUNTOS", fill="#a0a0c0", font=("Arial", 8, "bold"))
        canvas.create_text(off_x + ancho + 90, off_y + 95, text=str(puntuacion), fill="#e056fd", font=("Arial", 12, "bold"))
    elif modo_individual == "POWERUPS":
        canvas.create_rectangle(off_x + ancho + 10, off_y + 10, off_x + ancho + 170, off_y + 55, fill="", outline="#ff007f", width=2)
        canvas.create_text(off_x + ancho + 90, off_y + 22, text="MODO POWER-UPS", fill="#ff77cc", font=("Arial", 8, "bold"))
        canvas.create_text(off_x + ancho + 90, off_y + 40, text=f"PUNTOS {puntuacion}", fill="#ffd700", font=("Arial", 11, "bold"))

        canvas.create_rectangle(off_x + ancho + 10, off_y + 65, off_x + ancho + 170, off_y + 110, fill="", outline="#36364d")
        canvas.create_text(off_x + ancho + 90, off_y + 77, text=f"ENERGÍA PODER: {energia_powerups}%", fill="#00ff88" if energia_powerups >= 100 else "#00e5ff", font=("Arial", 7, "bold"))
        canvas.create_rectangle(off_x + ancho + 20, off_y + 88, off_x + ancho + 160, off_y + 98, fill="#121218", outline="#00e5ff")
        prog_p = min(1.0, energia_powerups / 100.0)
        if prog_p > 0:
            canvas.create_rectangle(off_x + ancho + 21, off_y + 89, off_x + ancho + 21 + int(138 * prog_p), off_y + 97, fill="#00ff88" if energia_powerups >= 100 else "#ff007f", outline="")
        canvas.create_text(off_x + ancho + 90, off_y + 104, text=f"PODERES: {len(slots_powerups)} / 3 LISTOS", fill="#ffd700" if slots_powerups else "#777790", font=("Arial", 6, "bold"))
    else:
        canvas.create_rectangle(off_x + ancho + 10, off_y + 10, off_x + ancho + 170, off_y + 55, fill="", outline="#00e5ff", width=2)
        canvas.create_text(off_x + ancho + 90, off_y + 22, text="PUNTOS", fill="#a0a0c0", font=("Arial", 8, "bold"))
        canvas.create_text(off_x + ancho + 90, off_y + 40, text=str(puntuacion), fill="#ffd700", font=("Arial", 12, "bold"))

        canvas.create_rectangle(off_x + ancho + 10, off_y + 65, off_x + ancho + 170, off_y + 110, fill="", outline="#ff007f")
        canvas.create_text(off_x + ancho + 90, off_y + 77, text="RÉCORD", fill="#a0a0c0", font=("Arial", 8, "bold"))
        canvas.create_text(off_x + ancho + 90, off_y + 95, text=str(maximo_puntaje), fill="#ff9900", font=("Arial", 12, "bold"))

    canvas.create_rectangle(off_x + ancho + 10, off_y + 120, off_x + ancho + 170, off_y + 165, fill="", outline="#36364d")
    canvas.create_text(off_x + ancho + 90, off_y + 131, text=f"NIVEL {nivel} | LÍNEAS: {lineas_totales}", fill="#a0a0c0", font=("Arial", 7, "bold"))
    progreso = (lineas_totales % 10) / 10.0
    canvas.create_rectangle(off_x + ancho + 20, off_y + 145, off_x + ancho + 160, off_y + 154, fill="#121218", outline="#00e5ff")
    if progreso > 0:
        canvas.create_rectangle(off_x + ancho + 21, off_y + 146, off_x + ancho + 21 + int(138 * progreso), off_y + 153, fill="#00e5ff", outline="")

    canvas.create_rectangle(off_x + ancho + 10, off_y + 175, off_x + ancho + 170, off_y + 260, fill="", outline="#00e5ff")
    canvas.create_text(off_x + ancho + 90, off_y + 187, text="SIGUIENTE", fill="#a0a0c0", font=("Arial", 8, "bold"))
    dibujar_miniatura(nombre_siguiente_pieza, off_x + ancho + 50, off_y + 205)

    canvas.create_rectangle(off_x + ancho + 10, off_y + 270, off_x + ancho + 170, off_y + 355, fill="", outline="#ff007f")
    canvas.create_text(off_x + ancho + 90, off_y + 282, text="GUARDADA", fill="#a0a0c0", font=("Arial", 8, "bold"))
    if nombre_pieza_guardada:
        dibujar_miniatura(nombre_pieza_guardada, off_x + ancho + 50, off_y + 300)
    else:
        canvas.create_text(off_x + ancho + 90, off_y + 315, text="[ C ]", fill="#666680", font=("Arial", 10))

    if modo_individual == "POWERUPS":
        canvas.create_rectangle(off_x + ancho + 10, off_y + 365, off_x + ancho + 170, off_y + 422, fill="#150f22", outline="#ff007f", width=2)
        canvas.create_text(off_x + ancho + 90, off_y + 375, text="⚡ ACTIVAR PODER [1] [2] [3] ⚡", fill="#ff77cc", font=("Arial", 6, "bold"))

        info_iconos = {"BOMBA": ("💣", "#ff4444", "#301010"), "LASER": ("⚡", "#00f0ff", "#102535"), "CONGELAR": ("❄️", "#70fff0", "#103030"), "LIMPIADOR": ("🧹", "#ffd700", "#302510")}

        for s_idx in range(3):
            sx1 = off_x + ancho + 15 + s_idx * 51
            sx2 = sx1 + 47
            sy1 = off_y + 386
            sy2 = off_y + 417
            coords_btn_powerups[s_idx] = [sx1, sy1, sx2, sy2]
            if s_idx < len(slots_powerups):
                pod = slots_powerups[s_idx]
                ic, b_col, bg_col = info_iconos.get(pod, ("✨", "#ffffff", "#1f1f2e"))
                dibujar_boton(sx1, sy1, sx2, sy2, f"{ic}[{s_idx+1}]", b_col, color_fondo=bg_col, font_size=8)
            else:
                dibujar_boton(sx1, sy1, sx2, sy2, f"[{s_idx+1}]", "#404055", color_fondo="#0d091a", color_texto="#555566", font_size=8)

        dibujar_boton(off_x + ancho + 15, off_y + 428, off_x + ancho + 62, off_y + 458, "◀ IZQ", "#00e5ff", font_size=8)
        dibujar_boton(off_x + ancho + 67, off_y + 428, off_x + ancho + 113, off_y + 458, "🔄 ROT", "#ffd700", font_size=8)
        dibujar_boton(off_x + ancho + 118, off_y + 428, off_x + ancho + 165, off_y + 458, "DER ▶", "#00e5ff", font_size=8)

        dibujar_boton(off_x + ancho + 15, off_y + 463, off_x + ancho + 87, off_y + 494, "▼ BAJAR", "#00ff88", font_size=8)
        dibujar_boton(off_x + ancho + 93, off_y + 463, off_x + ancho + 165, off_y + 494, "⏬ CAÍDA", "#ff007f", font_size=8)

        btn_pausa_texto = "▶️ SEGUIR" if juego_en_pausa else "⏸️ PAUSA"
        btn_pausa_color = "#00ff88" if juego_en_pausa else "#ffaa00"
        dibujar_boton(off_x + ancho + 15, off_y + 499, off_x + ancho + 87, off_y + 535, btn_pausa_texto, btn_pausa_color, font_size=8)
        dibujar_boton(off_x + ancho + 93, off_y + 499, off_x + ancho + 165, off_y + 535, "⚙️ OPCIONES", "#ffd700", font_size=8)
    else:
        canvas.create_rectangle(off_x + ancho + 10, off_y + 365, off_x + ancho + 170, off_y + 545, fill="", outline="#36364d")
        canvas.create_text(off_x + ancho + 90, off_y + 378, text="CONTROLES INTERACTIVOS", fill="#a0a0c0", font=("Arial", 7, "bold"))

        dibujar_boton(off_x + ancho + 15, off_y + 390, off_x + ancho + 62, off_y + 422, "◀ IZQ", "#00e5ff", font_size=8)
        dibujar_boton(off_x + ancho + 67, off_y + 390, off_x + ancho + 113, off_y + 422, "🔄 ROT", "#ffd700", font_size=8)
        dibujar_boton(off_x + ancho + 118, off_y + 390, off_x + ancho + 165, off_y + 422, "DER ▶", "#00e5ff", font_size=8)

        dibujar_boton(off_x + ancho + 15, off_y + 427, off_x + ancho + 87, off_y + 459, "▼ BAJAR", "#00ff88", font_size=8)
        dibujar_boton(off_x + ancho + 93, off_y + 427, off_x + ancho + 165, off_y + 459, "⏬ CAÍDA", "#ff007f", font_size=8)

        dibujar_boton(off_x + ancho + 15, off_y + 464, off_x + ancho + 87, off_y + 496, "📦 GUARDAR", "#a0a0c0", font_size=7)
        dibujar_boton(off_x + ancho + 93, off_y + 464, off_x + ancho + 165, off_y + 496, "🔄 REINICIAR", "#ff4444", font_size=7)

        btn_pausa_texto = "▶️ SEGUIR" if juego_en_pausa else "⏸️ PAUSA"
        btn_pausa_color = "#00ff88" if juego_en_pausa else "#ffaa00"
        dibujar_boton(off_x + ancho + 15, off_y + 501, off_x + ancho + 87, off_y + 537, btn_pausa_texto, btn_pausa_color, font_size=8)
        dibujar_boton(off_x + ancho + 93, off_y + 501, off_x + ancho + 165, off_y + 537, "⚙️ OPCIONES", "#ffd700", font_size=8)

    if musica_activada and cancion_reproduciendose:
        nombre_pista = os.path.splitext(cancion_reproduciendose)[0]
        canvas.create_text(off_x + ancho + 90, off_y + 558, text=f"🎵 {nombre_pista[:16]}", fill="#00f0ff", font=("Arial", 7, "bold"))

def dibujar_game_over():
    global coords_btn_gameover_restart, coords_btn_gameover_menu
    off_x, off_y, _, _ = obtener_offset_pantalla()
    box_w = 340
    box_h = 320
    cx = off_x + (ancho // 2)
    cy = off_y + (alto // 2)

    x1, y1 = cx - box_w // 2, cy - box_h // 2
    x2, y2 = cx + box_w // 2, cy + box_h // 2

    es_victoria = False
    if modo_juego == "VERSUS":
        if juego_terminado_rival and not juego_terminado:
            es_victoria = True

    borde_color = "#ffd700" if (es_nuevo_record or es_victoria) else "#ff4444"
    if modo_individual == "SPRINT" and es_victoria_modo:
        borde_color = "#00ffff"
    elif modo_individual == "BLITZ":
        borde_color = "#ffd700"
    elif modo_individual == "SURVIVAL":
        borde_color = "#ff5500"
    elif modo_individual == "CAOS":
        borde_color = "#e056fd"
    elif modo_individual == "POWERUPS":
        borde_color = "#ff007f"

    canvas.create_rectangle(x1, y1, x2, y2, fill="#1c1c28", outline=borde_color, width=3)

    if modo_juego == "VERSUS":
        if es_victoria:
            titulo = "¡VICTORIA!"
            color_tit = "#ffd700"
        elif juego_terminado and juego_terminado_rival:
            titulo = "¡EMPATE!"
            color_tit = "#00e5ff"
        else:
            titulo = "¡DERROTA!"
            color_tit = "#ff4444"
    elif modo_individual == "SPRINT" and es_victoria_modo:
        titulo = "¡SPRINT LOGRADO!"
        color_tit = "#00ffff"
    elif modo_individual == "BLITZ":
        titulo = "¡TIEMPO AGOTADO!"
        color_tit = "#ffd700"
    elif modo_individual == "SURVIVAL":
        titulo = "FIN DE SUPERVIVENCIA"
        color_tit = "#ff5500"
    elif modo_individual == "CAOS":
        titulo = "FIN DEL CAOS"
        color_tit = "#e056fd"
    elif modo_individual == "POWERUPS":
        titulo = "FIN DEL MODO PODERES"
        color_tit = "#ff007f"
    else:
        titulo = "GAME OVER"
        color_tit = "#ff4444"

    canvas.create_text(cx, y1 + 28, text=titulo, fill=color_tit, font=("Arial", 20, "bold"))

    if es_nuevo_record:
        canvas.create_text(cx, y1 + 56, text="🏆 ¡NUEVO RÉCORD! 🏆", fill="#ffd700", font=("Arial", 12, "bold"))
    elif modo_individual == "SPRINT" and es_victoria_modo:
        mins = int(tiempo_final_sprint // 60)
        segs = int(tiempo_final_sprint % 60)
        dec = int((tiempo_final_sprint * 10) % 10)
        canvas.create_text(cx, y1 + 56, text=f"⚡ 40 LÍNEAS EN {mins:02d}:{segs:02d}.{dec} ⚡", fill="#00ff88", font=("Arial", 11, "bold"))
    elif modo_individual == "BLITZ":
        canvas.create_text(cx, y1 + 56, text=f"⏱️ 120 SEGUNDOS BLITZ ⏱️", fill="#ffd700", font=("Arial", 11, "bold"))
    elif modo_individual == "SURVIVAL":
        canvas.create_text(cx, y1 + 56, text=f"🌋 OLEADAS RESISTIDAS: {oleada_survival} 🌋", fill="#ff5500", font=("Arial", 11, "bold"))
    elif modo_individual == "CAOS":
        canvas.create_text(cx, y1 + 56, text="🎲 CAOS & TRAMPAS SUPERADAS 🎲", fill="#e056fd", font=("Arial", 11, "bold"))
    elif modo_individual == "POWERUPS":
        canvas.create_text(cx, y1 + 56, text="💥 ¡PODERES Y BOMBAS DOMINADOS! 💥", fill="#ff77cc", font=("Arial", 11, "bold"))
    elif modo_juego == "VERSUS" and es_victoria:
        canvas.create_text(cx, y1 + 56, text="👑 ¡HAS DERROTADO AL RIVAL! 👑", fill="#00ff88", font=("Arial", 11, "bold"))

    canvas.create_text(cx, y1 + 88, text=f"Puntuación: {puntuacion}", fill="white", font=("Arial", 12, "bold"))
    canvas.create_text(cx, y1 + 116, text=f"Líneas Despejadas: {lineas_totales}", fill="#00ff88", font=("Arial", 11, "bold"))
    canvas.create_text(cx, y1 + 142, text=f"Récord Máximo: {maximo_puntaje}", fill="#00e5ff", font=("Arial", 11))

    stats_str = "Piezas: " + " ".join([f"{k}:{v}" for k, v in conteo_piezas.items() if v > 0])
    canvas.create_text(cx, y1 + 174, text=stats_str[:42], fill="#a0a0c0", font=("Arial", 8))

    # Botones interactivos de fin de juego (Reintentar y Volver al Menú)
    btn_w = 260
    btn_h = 36
    r_x1, r_y1 = cx - btn_w // 2, y1 + 202
    r_x2, r_y2 = cx + btn_w // 2, r_y1 + btn_h
    coords_btn_gameover_restart = [r_x1, r_y1, r_x2, r_y2]
    dibujar_boton(r_x1, r_y1, r_x2, r_y2, "🔄 JUGAR DE NUEVO  [ R ]", "#00ff88", color_fondo="#103525", font_size=9)

    m_x1, m_y1 = cx - btn_w // 2, y1 + 248
    m_x2, m_y2 = cx + btn_w // 2, m_y1 + btn_h
    coords_btn_gameover_menu = [m_x1, m_y1, m_x2, m_y2]
    dibujar_boton(m_x1, m_y1, m_x2, m_y2, "🏠 VOLVER AL MENÚ  [ M / ESC ]", "#00e5ff", color_fondo="#102535", font_size=9)

    canvas.create_text(cx, y1 + 302, text="Selecciona con el ratón o pulsa [ R ] / [ M ] / [ ESC ]", fill="#7a7a9a", font=("Arial", 8))

def dibujar_modal_pausa():
    off_x, off_y, _, _ = obtener_offset_pantalla()
    box_w = 300
    box_h = 240
    cx = off_x + (ancho // 2)
    cy = off_y + (alto // 2)

    x1, y1 = cx - box_w // 2, cy - box_h // 2
    x2, y2 = cx + box_w // 2, cy + box_h // 2

    canvas.create_rectangle(x1, y1, x2, y2, fill="#1c1c28", outline="#ffaa00", width=3)
    canvas.create_text(cx, y1 + 35, text="⏸️ JUEGO EN PAUSA", fill="#ffaa00", font=("Arial", 16, "bold"))

    dibujar_boton(cx - 110, y1 + 75, cx + 110, y1 + 115, "▶️ REANUDAR JUEGO", "#00ff88", font_size=10)
    dibujar_boton(cx - 110, y1 + 125, cx + 110, y1 + 165, "⚙️ AJUSTES Y OPCIONES", "#ffd700", font_size=10)
    dibujar_boton(cx - 110, y1 + 175, cx + 110, y1 + 215, "🏠 MENÚ PRINCIPAL", "#a0a0c0", font_size=10)

def dibujar_panel_rival():
    if modo_juego != "VERSUS":
        return
    off_x, off_y, _, _ = obtener_offset_pantalla()
    px = off_x + ancho + 200 + ancho  # off_rival_x + ancho = off_x + 500 + 300 = off_x + 800

    canvas.create_rectangle(px, off_y + 0, px + 120, off_y + alto, fill="", outline="")

    canvas.create_rectangle(px + 5, off_y + 10, px + 115, off_y + 55, fill="", outline="#ff007f", width=2)
    tit_text = "P2 ONLINE" if codigo_sala_actual else "RIVAL (IA)"
    canvas.create_text(px + 60, off_y + 22, text=tit_text, fill="#ff88aa", font=("Arial", 8, "bold"))
    canvas.create_text(px + 60, off_y + 40, text="VERSUS", fill="#ffd700", font=("Arial", 9, "bold"))

    canvas.create_rectangle(px + 5, off_y + 65, px + 115, off_y + 110, fill="", outline="#36364d")
    canvas.create_text(px + 60, off_y + 77, text="PUNTOS", fill="#a0a0c0", font=("Arial", 8, "bold"))
    canvas.create_text(px + 60, off_y + 95, text=str(puntuacion_rival), fill="#ffd700", font=("Arial", 11, "bold"))

    canvas.create_rectangle(px + 5, off_y + 120, px + 115, off_y + 165, fill="", outline="#36364d")
    canvas.create_text(px + 60, off_y + 133, text="LÍNEAS", fill="#a0a0c0", font=("Arial", 8, "bold"))
    canvas.create_text(px + 60, off_y + 150, text=str(lineas_rival), fill="#00e5ff", font=("Arial", 11, "bold"))

    canvas.create_rectangle(px + 5, off_y + 175, px + 115, off_y + 260, fill="", outline="#ff007f")
    canvas.create_text(px + 60, off_y + 187, text="SIGUIENTE", fill="#a0a0c0", font=("Arial", 8, "bold"))
    dibujar_miniatura(nombre_siguiente_rival, px + 25, off_y + 205)

"""
Interfaz del menu principal, modo online y ajustes
"""
def dibujar_boton(x1, y1, x2, y2, texto, color_borde, color_fondo="#0d091a", color_texto="#ffffff", font_size=11):
    canvas.create_rectangle(x1 + 3, y1 + 3, x2 + 3, y2 + 3, fill="#000000", outline="")
    canvas.create_rectangle(x1, y1, x2, y2, fill=color_fondo, outline=color_borde, width=2)
    canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=texto, fill=color_texto, font=("Arial", font_size, "bold"))

coords_btn_solo = [90, 190, 390, 250]
coords_btn_online = [90, 270, 390, 330]
coords_btn_ajustes = [90, 350, 390, 410]

def dibujar_menu_principal():
    off_x, off_y, cw, ch = obtener_offset_pantalla()
    img_bg = obtener_imagen_menu_escalada(cw, ch)
    if img_bg is not None:
        canvas.create_image(0, 0, image=img_bg, anchor="nw")
    else:
        canvas.create_rectangle(0, 0, cw, ch, fill="#121218", outline="")
        canvas.create_text(cw // 2, off_y + 90, text="C A S U A L   B L O C K S", fill="#00e5ff", font=("Arial", 28, "bold"))

    if ch > 600:
        bw = min(420, max(280, int(cw * 0.42)))
        bh = max(46, min(65, int(ch * 0.075)))
        gap = max(12, int(ch * 0.018))
        target_y1 = int(ch * 0.48)
        max_menu_y = ch - 50 - (3 * bh + 2 * gap)
        y1 = min(target_y1, max_menu_y)
        y_sub = y1 - 28
    else:
        bw = min(360, max(260, int(cw * 0.65)))
        bh = 44
        gap = 12
        y1 = 315
        y_sub = y1 - 26

    y2 = y1 + bh + gap
    y3 = y2 + bh + gap
    cx = cw // 2

    coords_btn_solo[0], coords_btn_solo[1], coords_btn_solo[2], coords_btn_solo[3] = cx - bw // 2, y1, cx + bw // 2, y1 + bh
    coords_btn_online[0], coords_btn_online[1], coords_btn_online[2], coords_btn_online[3] = cx - bw // 2, y2, cx + bw // 2, y2 + bh
    coords_btn_ajustes[0], coords_btn_ajustes[1], coords_btn_ajustes[2], coords_btn_ajustes[3] = cx - bw // 2, y3, cx + bw // 2, y3 + bh

    font_sub = max(9, int(min(cw, ch) * 0.022))
    font_btn = max(10, int(min(cw, ch) * 0.024))

    canvas.create_text(cx + 1, y_sub + 1, text="SELECCIONA UN MODO DE JUEGO", fill="#000000", font=("Arial", font_sub, "bold"))
    canvas.create_text(cx, y_sub, text="SELECCIONA UN MODO DE JUEGO", fill="#00f0ff", font=("Arial", font_sub, "bold"))

    texto_solo = "▶  UN SOLO JUGADOR  ◀" if opcion_menu_seleccionada == 0 else "UN SOLO JUGADOR"
    texto_online = "▶  MODO ONLINE  ◀" if opcion_menu_seleccionada == 1 else "MODO ONLINE"
    texto_ajustes = "▶  AJUSTES  ◀" if opcion_menu_seleccionada == 2 else "AJUSTES"

    fondo_solo = "#25123d" if opcion_menu_seleccionada == 0 else "#0d091a"
    fondo_online = "#3d0b28" if opcion_menu_seleccionada == 1 else "#0d091a"
    fondo_ajustes = "#3d300b" if opcion_menu_seleccionada == 2 else "#0d091a"

    borde_solo = "#ffffff" if opcion_menu_seleccionada == 0 else "#00f0ff"
    borde_online = "#ffffff" if opcion_menu_seleccionada == 1 else "#ff007f"
    borde_ajustes = "#ffffff" if opcion_menu_seleccionada == 2 else "#ffd700"

    dibujar_boton(coords_btn_solo[0], coords_btn_solo[1], coords_btn_solo[2], coords_btn_solo[3], texto_solo, borde_solo, color_fondo=fondo_solo, font_size=font_btn)
    dibujar_boton(coords_btn_online[0], coords_btn_online[1], coords_btn_online[2], coords_btn_online[3], texto_online, borde_online, color_fondo=fondo_online, font_size=font_btn)
    dibujar_boton(coords_btn_ajustes[0], coords_btn_ajustes[1], coords_btn_ajustes[2], coords_btn_ajustes[3], texto_ajustes, borde_ajustes, color_fondo=fondo_ajustes, font_size=font_btn)

    canvas.create_text(cx, ch - 20, text="Casual Blocks 2026 - Versión 0.1", fill="#a0a0c0", font=("Arial", 9, "bold"))

"""
Funciones y Logica de Salas Online
"""
def generar_codigo_sala():
    return str(random.randint(1000, 9999))

def crear_sala_online():
    global codigo_sala_actual, es_anfitrion_sala, estado_sala_online, stop_sync_online, hilo_sync_online
    codigo = generar_codigo_sala()
    codigo_sala_actual = codigo
    es_anfitrion_sala = True
    estado_sala_online = "ESPERANDO"
    stop_sync_online = False

    conectar_firebase()
    if firebase_conectado and db_firebase is not None:
        try:
            tab_init = json.dumps([[0]*COLUMNAS for _ in range(FILAS)])
            db_firebase.collection("salas").document(codigo).set({
                "codigo": codigo,
                "estado": "ESPERANDO",
                "p1_tablero": tab_init,
                "p1_puntuacion": 0,
                "p1_basura": 0,
                "p1_terminado": False,
                "p2_tablero": tab_init,
                "p2_puntuacion": 0,
                "p2_basura": 0,
                "p2_terminado": False,
                "fecha": time.time()
            })
        except Exception:
            pass
    else:
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{URL_RENDER_SERVER}/api/salas/crear",
                data=json.dumps({"codigo": codigo}).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass

    hilo_sync_online = threading.Thread(target=bucle_espera_y_sync, daemon=True)
    hilo_sync_online.start()
    redibujar()

def vincular_sala_online():
    global codigo_sala_actual, es_anfitrion_sala, estado_sala_online, stop_sync_online, hilo_sync_online
    codigo = simpledialog.askstring("Vincular Sala Online", "Ingresa el Código de Sala (4 dígitos):")
    if not codigo:
        return
    codigo = codigo.strip()

    conectar_firebase()
    exito = False
    if firebase_conectado and db_firebase is not None:
        try:
            doc_ref = db_firebase.collection("salas").document(codigo)
            doc = doc_ref.get()
            if doc.exists:
                doc_ref.update({"estado": "JUGANDO"})
                exito = True
        except Exception:
            pass
    else:
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{URL_RENDER_SERVER}/api/salas/unirse",
                data=json.dumps({"codigo": codigo}).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    exito = True
        except Exception:
            pass

    if exito:
        codigo_sala_actual = codigo
        es_anfitrion_sala = False
        estado_sala_online = "JUGANDO"
        stop_sync_online = False
        iniciar_modo_versus_online()
        hilo_sync_online = threading.Thread(target=bucle_espera_y_sync, daemon=True)
        hilo_sync_online.start()
    else:
        messagebox.showerror("Error de Vinculación", f"No se pudo encontrar o vincular a la sala {codigo}.")

def cancelar_sala_online():
    global estado_sala_online, codigo_sala_actual, stop_sync_online
    stop_sync_online = True
    estado_sala_online = "DESCONECTADO"
    codigo_sala_actual = ""
    redibujar()

def iniciar_modo_versus_online():
    global modo_juego, estado_pantalla, juego_en_pausa, tablero_rival, puntuacion_rival, lineas_rival, juego_terminado_rival
    modo_juego = "VERSUS"
    estado_pantalla = "JUEGO"
    juego_en_pausa = False
    reiniciar_juego()

    tablero_rival = [[0 for _ in range(COLUMNAS)] for _ in range(FILAS)]
    puntuacion_rival = 0
    lineas_rival = 0
    juego_terminado_rival = False

    actualizar_musica_estado()
    caer()

def enviar_basura_online(cant):
    global basura_pendiente_enviar
    basura_pendiente_enviar += cant

def bucle_espera_y_sync():
    global estado_sala_online, tablero_rival, puntuacion_rival, juego_terminado_rival, stop_sync_online, basura_pendiente_enviar
    rol = "p1" if es_anfitrion_sala else "p2"
    rol_rival = "p2" if es_anfitrion_sala else "p1"

    while not stop_sync_online:
        time.sleep(0.25)
        if not codigo_sala_actual:
            break

        if firebase_conectado and db_firebase is not None:
            try:
                doc_ref = db_firebase.collection("salas").document(codigo_sala_actual)
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict() or {}
                    st = data.get("estado", "ESPERANDO")
                    if estado_sala_online == "ESPERANDO" and st == "JUGANDO":
                        estado_sala_online = "JUGANDO"
                        root.after(0, iniciar_modo_versus_online)

                    if estado_pantalla == "JUEGO":
                        upd = {
                            f"{rol}_tablero": json.dumps(tablero),
                            f"{rol}_puntuacion": puntuacion,
                            f"{rol}_terminado": juego_terminado
                        }
                        if basura_pendiente_enviar > 0:
                            upd[f"{rol_rival}_basura"] = data.get(f"{rol_rival}_basura", 0) + basura_pendiente_enviar
                            basura_pendiente_enviar = 0
                        doc_ref.update(upd)

                        riv_tab_raw = data.get(f"{rol_rival}_tablero")
                        if riv_tab_raw:
                            if isinstance(riv_tab_raw, str):
                                tablero_rival = json.loads(riv_tab_raw)
                            elif isinstance(riv_tab_raw, list):
                                tablero_rival = riv_tab_raw
                        puntuacion_rival = data.get(f"{rol_rival}_puntuacion", puntuacion_rival)

                        riv_term = data.get(f"{rol_rival}_terminado", False)
                        if riv_term and not juego_terminado_rival:
                            juego_terminado_rival = True
                            root.after(0, detener_timers_juego)
                            root.after(0, actualizar_musica_estado)

                        basura_recibida = data.get(f"{rol}_basura", 0)
                        if basura_recibida > 0:
                            doc_ref.update({f"{rol}_basura": 0})
                            root.after(0, lambda b=basura_recibida: agregar_lineas_basura(tablero, b))
                        root.after(0, redibujar)
            except Exception:
                pass
        else:
            try:
                import urllib.request
                if estado_sala_online == "ESPERANDO":
                    req = urllib.request.Request(f"{URL_RENDER_SERVER}/api/salas/{codigo_sala_actual}")
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        res = json.loads(resp.read().decode('utf-8'))
                        if res.get("sala", {}).get("estado") == "JUGANDO":
                            estado_sala_online = "JUGANDO"
                            root.after(0, iniciar_modo_versus_online)
                elif estado_pantalla == "JUEGO":
                    payload_dict = {
                        "codigo": codigo_sala_actual,
                        "rol": rol,
                        "tablero": tablero,
                        "puntuacion": puntuacion,
                        "terminado": juego_terminado
                    }
                    if basura_pendiente_enviar > 0:
                        payload_dict["basura"] = basura_pendiente_enviar
                        basura_pendiente_enviar = 0

                    req = urllib.request.Request(
                        f"{URL_RENDER_SERVER}/api/salas/actualizar",
                        data=json.dumps(payload_dict).encode('utf-8'),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        res = json.loads(resp.read().decode('utf-8'))
                        datos = res.get("datos", {})
                        riv_tab = datos.get("tablero_rival")
                        if riv_tab and isinstance(riv_tab, list):
                            tablero_rival = riv_tab
                        puntuacion_rival = datos.get("puntuacion_rival", puntuacion_rival)
                        bas = datos.get("basura", 0)
                        if bas > 0:
                            root.after(0, lambda b=bas: agregar_lineas_basura(tablero, b))
                        root.after(0, redibujar)
            except Exception:
                pass

def bucle_tick_modo():
    global timer_modo_tick
    if timer_modo_tick is not None:
        try:
            root.after_cancel(timer_modo_tick)
        except Exception:
            pass
        timer_modo_tick = None

    if estado_pantalla != "JUEGO" or juego_terminado or juego_en_pausa:
        return

    if modo_individual == "BLITZ":
        dt = max(0.0, time.time() - tiempo_inicio_modo - tiempo_pausado_total)
        rem = duracion_blitz_seg - dt
        if rem <= 0:
            finalizar_partida_blitz()
            return
        redibujar()
    elif modo_individual == "SPRINT":
        redibujar()
    elif modo_individual == "SURVIVAL":
        redibujar()

    timer_modo_tick = root.after(200, bucle_tick_modo)

def bucle_survival():
    global timer_survival, oleada_survival, texto_flotante_msg, texto_flotante_color, texto_flotante_tiempo
    if timer_survival is not None:
        try:
            root.after_cancel(timer_survival)
        except Exception:
            pass
        timer_survival = None

    if estado_pantalla != "JUEGO" or modo_individual != "SURVIVAL" or juego_terminado or juego_en_pausa:
        return

    oleada_survival += 1
    agregar_lineas_basura(tablero, 1)
    texto_flotante_msg = f"🌋 ¡OLEADA {oleada_survival}! +1 BASURA"
    texto_flotante_color = "#ff5500"
    texto_flotante_tiempo = time.time()
    reproducir_sonido("limpiar_1")
    redibujar()

    timer_survival = root.after(intervalo_survival_seg * 1000, bucle_survival)

def iniciar_bucle_survival():
    global timer_survival
    if timer_survival is not None:
        try:
            root.after_cancel(timer_survival)
        except Exception:
            pass
    timer_survival = root.after(intervalo_survival_seg * 1000, bucle_survival)

def finalizar_partida_blitz():
    global juego_terminado, es_victoria_modo
    if juego_terminado:
        return
    juego_terminado = True
    es_victoria_modo = False
    detener_timers_juego()
    reproducir_sonido("record" if puntuacion > 0 else "game_over")
    actualizar_musica_estado()
    redibujar()

def iniciar_modo_individual(modo="CLASICO"):
    global estado_pantalla, modo_juego, modo_individual, juego_en_pausa, tiempo_inicio_modo, tiempo_pausado_total, tiempo_inicio_pausa, oleada_survival, es_victoria_modo, tiempo_final_sprint
    detener_timers_juego()
    modo_juego = "SOLO"
    modo_individual = modo
    estado_pantalla = "JUEGO"
    juego_en_pausa = False
    oleada_survival = 0
    es_victoria_modo = False
    tiempo_final_sprint = 0.0
    tiempo_inicio_modo = time.time()
    tiempo_pausado_total = 0.0
    tiempo_inicio_pausa = 0.0
    ajustar_tamano_ventana()
    reiniciar_juego()
    actualizar_musica_estado()

def dibujar_pantalla_modos():
    global coords_btn_modos
    off_x, off_y, cw, ch = obtener_offset_pantalla()
    img_bg = obtener_imagen_menu_escalada(cw, ch)
    if img_bg is not None:
        canvas.create_image(0, 0, image=img_bg, anchor="nw")
    else:
        canvas.create_rectangle(0, 0, cw, ch, fill="#121218", outline="")

    cx = cw // 2

    # Adaptar tamaños según resolución de pantalla vertical y horizontal (7 botones)
    if ch < 680 or cw < 600:
        bw = min(420, max(280, int(cw * 0.88)))
        bh = 26
        espacio = 3
        pad_x = 10
        pad_y = 5
        font_header = 11
        font_sub = 7
        font_tit = 8
        font_desc = 6
        y_header_offset = 5
        header_text_gap = 12
        header_sub_gap = 8
        header_div_gap = 5
    elif ch < 860:
        # Pantallas estándar maximizadas (1366x768, 720p, 1080p con escalado)
        bw = min(520, max(360, int(cw * 0.46)))
        bh = 32
        espacio = 4
        pad_x = 18
        pad_y = 8
        font_header = 14
        font_sub = 8
        font_tit = 9
        font_desc = 7
        y_header_offset = 6
        header_text_gap = 15
        header_sub_gap = 10
        header_div_gap = 6
    else:
        # Pantallas grandes Full HD o superiores sin escalado
        bw = min(560, max(400, int(cw * 0.42)))
        bh = 38
        espacio = 6
        pad_x = 22
        pad_y = 10
        font_header = 16
        font_sub = 9
        font_tit = 10
        font_desc = 8
        y_header_offset = 10
        header_text_gap = 18
        header_sub_gap = 12
        header_div_gap = 8

    h_header = pad_y + y_header_offset + header_text_gap + header_sub_gap + header_div_gap
    total_botones_h = 7 * bh + 6 * espacio
    card_h = h_header + total_botones_h + pad_y
    card_w = bw + pad_x * 2

    card_x1 = cx - card_w // 2
    card_x2 = cx + card_w // 2

    # Límite inferior para asegurar margen al pie de página (footer)
    max_card_bottom = ch - 34
    target_y1 = int(ch * 0.43)

    if target_y1 + card_h > max_card_bottom:
        card_y1 = max(10, max_card_bottom - card_h)
    else:
        card_y1 = target_y1

    card_y2 = card_y1 + card_h

    # Sombra del panel central
    canvas.create_rectangle(card_x1 + 6, card_y1 + 6, card_x2 + 6, card_y2 + 6, fill="#000000", outline="")
    # Contenedor central (Panel translúcido oscuro cyberpunk)
    canvas.create_rectangle(card_x1, card_y1, card_x2, card_y2, fill="#0d0a1a", outline="#2f1e4a", width=2)
    # Detalles neón de acento en bordes superior e inferior
    canvas.create_line(card_x1 + 15, card_y1, card_x2 - 15, card_y1, fill="#00f0ff", width=2)
    canvas.create_line(card_x1 + 15, card_y2, card_x2 - 15, card_y2, fill="#ff007f", width=2)

    # Encabezado del panel
    y_title = card_y1 + pad_y + y_header_offset
    canvas.create_text(cx + 1, y_title + 1, text="MODOS DE JUEGO", fill="#000000", font=("Arial", font_header, "bold"))
    canvas.create_text(cx, y_title, text="MODOS DE JUEGO", fill="#00f0ff", font=("Arial", font_header, "bold"))

    y_sub = y_title + header_text_gap
    canvas.create_text(cx, y_sub, text="SELECCIONA UN ESTILO DE DESAFÍO", fill="#a0a0c0", font=("Arial", font_sub, "bold"))

    # Divisor horizontal
    y_div = y_sub + header_sub_gap
    canvas.create_line(card_x1 + 20, y_div, card_x2 - 20, y_div, fill="#251a3a", width=1)

    y_inicio_botones = y_div + header_div_gap

    modos_info = [
        ("🏆  MODO CLÁSICO", "Maratón tradicional infinito con velocidad creciente", "#00f0ff", "#102535"),
        ("⚡  SPRINT (40 LÍNEAS)", "Completa 40 líneas lo más rápido posible contra el reloj", "#00ff88", "#103525"),
        ("⏱️  BLITZ (2 MINUTOS)", "Máxima puntuación en 120 segundos contra el cronómetro", "#ffd700", "#353010"),
        ("🌋  SUPERVIVENCIA", "Resiste oleadas continuas de basura cada 12 segundos", "#ff5500", "#3d1a10"),
        ("🎲  MODO CAOS / TRAMPAS", "Piezas 100% impredecibles, bloques gigantes y piezas trampa", "#e056fd", "#35103a"),
        ("💥  MODO POWER-UPS", "Bombas, rayos láser, congelación y purga de bloques", "#ff007f", "#3a1025"),
        ("◀  VOLVER AL MENÚ", "Regresar a la pantalla principal", "#a0a0c0", "#20202d")
    ]

    for idx, (tit, desc, col_activo, col_bg_sel) in enumerate(modos_info):
        by1 = y_inicio_botones + idx * (bh + espacio)
        by2 = by1 + bh
        bx1 = cx - bw // 2
        bx2 = cx + bw // 2
        coords_btn_modos[idx] = [bx1, by1, bx2, by2]

        es_sel = (opcion_modos_seleccionada == idx)
        borde = "#ffffff" if es_sel else col_activo
        bg = col_bg_sel if es_sel else "#141122"
        ancho_borde = 2 if es_sel else 1

        # Sombra y marco del botón
        canvas.create_rectangle(bx1 + 2, by1 + 2, bx2 + 2, by2 + 2, fill="#000000", outline="")
        canvas.create_rectangle(bx1, by1, bx2, by2, fill=bg, outline=borde, width=ancho_borde)

        prefix = "▶  " if es_sel else ""
        suffix = "  ◀" if es_sel else ""

        y_btn_tit = by1 + int(bh * 0.35)
        y_btn_desc = by1 + int(bh * 0.74)

        canvas.create_text(cx, y_btn_tit, text=prefix + tit + suffix, fill="#ffffff" if es_sel else col_activo, font=("Arial", font_tit, "bold"))
        canvas.create_text(cx, y_btn_desc, text=desc, fill="#e5e5f5" if es_sel else "#8888a5", font=("Arial", font_desc))

    # Pie de página
    canvas.create_text(cx, ch - 16, text="Usa [ ↑ / ↓ ] y [ ENTER ] para seleccionar  •  [ ESC ] para volver", fill="#7a7a98", font=("Arial", 8 if ch < 700 else 9))

def dibujar_pantalla_online():
    off_x, off_y, cw, ch = obtener_offset_pantalla()
    canvas.create_rectangle(0, 0, cw, ch, fill="#121218", outline="")
    canvas.create_text(cw // 2, off_y + 35, text="MULTIJUGADOR ONLINE Y LOCAL", fill="#ff007f", font=("Arial", 20, "bold"))

    if estado_sala_online == "ESPERANDO":
        canvas.create_rectangle(off_x + 30, off_y + 70, off_x + 450, off_y + 360, fill="#1c1c2b", outline="#00e5ff", width=2)
        canvas.create_text(cw // 2, off_y + 105, text="👑 SALA CREADA CON ÉXITO", fill="#ffd700", font=("Arial", 14, "bold"))
        canvas.create_text(cw // 2, off_y + 145, text="CÓDIGO DE SALA:", fill="#ffffff", font=("Arial", 10, "bold"))
        canvas.create_rectangle(cw // 2 - 120, off_y + 170, cw // 2 + 120, off_y + 230, fill="#0d091a", outline="#ff007f", width=2)
        canvas.create_text(cw // 2, off_y + 200, text=codigo_sala_actual, fill="#00e5ff", font=("Arial", 28, "bold"))

        canvas.create_text(cw // 2, off_y + 265, text="Comparte este código de 4 dígitos con tu rival.", fill="#a0a0c0", font=("Arial", 9))
        canvas.create_text(cw // 2, off_y + 295, text="⏳ Esperando que el rival se vincule...", fill="#ffd700", font=("Arial", 10, "bold"))

        dibujar_boton(off_x + 140, off_y + 420, off_x + 340, off_y + 470, "CANCELAR SALA", "#ff4444")
    else:
        canvas.create_rectangle(off_x + 30, off_y + 60, off_x + 450, off_y + 225, fill="#1c1c2b", outline="#ff007f", width=2)
        canvas.create_text(cw // 2, off_y + 80, text="⚔️ REGLAS DE COMBATE MULTIJUGADOR", fill="#ffd700", font=("Arial", 11, "bold"))

        reglas = [
            ("• 2 Líneas (Doble):", "💣 Envia 1 Línea de Basura al rival"),
            ("• 3 Líneas (Triple):", "💣 Envia 2 Líneas de Basura al rival"),
            ("• 4 Líneas (Tetris):", "💣 Envia 4 Líneas de Basura al rival"),
            ("• Combos Seguidos:", "💣 +1 Línea extra de basura por combo")
        ]
        y_reg = off_y + 105
        for lab, val in reglas:
            canvas.create_text(off_x + 50, y_reg, text=lab, fill="#ffffff", font=("Arial", 9, "bold"), anchor="w")
            canvas.create_text(off_x + 210, y_reg, text=val, fill="#00e5ff", font=("Arial", 9), anchor="w")
            y_reg += 24

        t_crear = "▶  👑 CREAR SALA ONLINE  ◀" if opcion_online_seleccionada == 0 else "👑 CREAR SALA ONLINE"
        t_vinc = "▶  🔗 VINCULAR SALA (INGRESAR CÓDIGO)  ◀" if opcion_online_seleccionada == 1 else "🔗 VINCULAR SALA (INGRESAR CÓDIGO)"
        t_local = "▶  ⚔️ MODO VERSUS LOCAL (IA / 2 PANTALLAS)  ◀" if opcion_online_seleccionada == 2 else "⚔️ MODO VERSUS LOCAL (IA / 2 PANTALLAS)"
        t_volver = "▶  VOLVER AL MENÚ  ◀" if opcion_online_seleccionada == 3 else "VOLVER AL MENÚ"

        b_crear = "#ffffff" if opcion_online_seleccionada == 0 else "#00e5ff"
        b_vinc = "#ffffff" if opcion_online_seleccionada == 1 else "#ff007f"
        b_local = "#ffffff" if opcion_online_seleccionada == 2 else "#ffd700"
        b_volver = "#ffffff" if opcion_online_seleccionada == 3 else "#a0a0c0"

        f_crear = "#103540" if opcion_online_seleccionada == 0 else "#0d091a"
        f_vinc = "#401025" if opcion_online_seleccionada == 1 else "#0d091a"
        f_local = "#403510" if opcion_online_seleccionada == 2 else "#0d091a"
        f_volver = "#303040" if opcion_online_seleccionada == 3 else "#0d091a"

        dibujar_boton(off_x + 60, off_y + 240, off_x + 420, off_y + 285, t_crear, b_crear, color_fondo=f_crear, font_size=10)
        dibujar_boton(off_x + 60, off_y + 295, off_x + 420, off_y + 340, t_vinc, b_vinc, color_fondo=f_vinc, font_size=10)
        dibujar_boton(off_x + 60, off_y + 350, off_x + 420, off_y + 395, t_local, b_local, color_fondo=f_local, font_size=9)

        conectar_firebase()
        if firebase_conectado:
            canvas.create_text(cw // 2, off_y + 415, text="🟢 CONECTADO A FIREBASE FIRESTORE", fill="#00ff88", font=("Arial", 8, "bold"))
        else:
            canvas.create_text(cw // 2, off_y + 415, text="🟡 CONECTADO A SERVIDOR RENDER", fill="#ffd700", font=("Arial", 8, "bold"))

        t_volver = "▶  VOLVER AL MENÚ  ◀" if opcion_online_seleccionada == 3 else "VOLVER AL MENÚ"
        b_volver = "#ffffff" if opcion_online_seleccionada == 3 else "#a0a0c0"
        f_volver = "#303040" if opcion_online_seleccionada == 3 else "#0d091a"
        dibujar_boton(off_x + 140, off_y + 440, off_x + 340, off_y + 490, t_volver, b_volver, color_fondo=f_volver)

def dibujar_pantalla_ajustes():
    off_x, off_y, cw, ch = obtener_offset_pantalla()
    canvas.create_rectangle(0, 0, cw, ch, fill="#121218", outline="")
    canvas.create_text(cw // 2, off_y + 50, text="AJUSTES Y OPCIONES", fill="#ffd700", font=("Arial", 22, "bold"))

    canvas.create_rectangle(off_x + 40, off_y + 85, off_x + 440, off_y + 205, fill="#1f1f2e", outline="#36364d", width=2)
    canvas.create_text(off_x + 210, off_y + 115, text="EFECTOS DE SONIDO:", fill="#ffffff", font=("Arial", 10, "bold"), anchor="e")
    estado_sonido = "ACTIVADO" if sonido_activado else "DESACTIVADO"
    color_sonido = "#00ff88" if sonido_activado else "#ff4444"
    t_sonido = f"▶ {estado_sonido} ◀" if opcion_ajustes_seleccionada == 0 else estado_sonido
    b_sonido = "#ffffff" if opcion_ajustes_seleccionada == 0 else color_sonido
    dibujar_boton(off_x + 235, off_y + 100, off_x + 415, off_y + 135, t_sonido, b_sonido, color_texto=color_sonido)

    canvas.create_text(off_x + 210, off_y + 165, text="MÚSICA DE FONDO:", fill="#ffffff", font=("Arial", 10, "bold"), anchor="e")
    estado_musica = "ACTIVADO" if musica_activada else "DESACTIVADO"
    color_musica = "#00ff88" if musica_activada else "#ff4444"
    t_musica = f"▶ {estado_musica} ◀" if opcion_ajustes_seleccionada == 1 else estado_musica
    b_musica = "#ffffff" if opcion_ajustes_seleccionada == 1 else color_musica
    dibujar_boton(off_x + 235, off_y + 150, off_x + 415, off_y + 185, t_musica, b_musica, color_texto=color_musica)

    canvas.create_rectangle(off_x + 40, off_y + 215, off_x + 440, off_y + 290, fill="#1f1f2e", outline="#36364d", width=2)
    canciones = obtener_canciones_juego()
    nombre_cancion = canciones[cancion_actual_idx % len(canciones)] if canciones else "Sin canciones"
    nombre_sin_ext = os.path.splitext(nombre_cancion)[0]
    canvas.create_text(off_x + 210, off_y + 238, text=f"🎵 {nombre_sin_ext[:15]}", fill="#00e5ff", font=("Arial", 8, "bold"), anchor="e")
    t_pista = "▶  CAMBIAR PISTA  ◀" if opcion_ajustes_seleccionada == 2 else "CAMBIAR PISTA"
    b_pista = "#ffffff" if opcion_ajustes_seleccionada == 2 else "#ff007f"
    dibujar_boton(off_x + 225, off_y + 223, off_x + 435, off_y + 250, t_pista, b_pista, font_size=8)

    fondos = obtener_rutas_fondos_juego()
    total_f = len(fondos) if fondos else 1
    lbl_fondo = f"🖼️ Fondo {fondo_juego_actual + 1} / {total_f}"
    canvas.create_text(off_x + 210, off_y + 272, text=lbl_fondo, fill="#00ff88", font=("Arial", 8, "bold"), anchor="e")
    t_fondo = "▶  CAMBIAR FONDO  ◀" if opcion_ajustes_seleccionada == 3 else "CAMBIAR FONDO"
    b_fondo = "#ffffff" if opcion_ajustes_seleccionada == 3 else "#00ff88"
    dibujar_boton(off_x + 225, off_y + 257, off_x + 435, off_y + 284, t_fondo, b_fondo, font_size=8)

    canvas.create_rectangle(off_x + 40, off_y + 300, off_x + 440, off_y + 470, fill="#1f1f2e", outline="#36364d", width=2)
    canvas.create_text(cw // 2, off_y + 320, text="CONTROLES DEL JUEGO", fill="#00e5ff", font=("Arial", 10, "bold"))
    controles_info = [
        ("Mover Izq / Der:", "Flechas <- / ->  |  Botones ◀ ▶"),
        ("Rotar Pieza:", "Flecha Arriba  |  Botón 🔄"),
        ("Caída Rápida / Instant:", "Abajo / Espacio  |  Botones ▼ ⏬"),
        ("Guardar Pieza:", "Tecla C  |  Botón 📦"),
        ("Reiniciar Partida:", "Tecla R  |  Botón 🔄"),
        ("Pausar / Opciones:", "Esc / P / M  |  Botones ⏸️ ⚙️")
    ]
    y_pos = off_y + 345
    for lab, val in controles_info:
        canvas.create_text(off_x + 210, y_pos, text=lab, fill="#cccccc", font=("Arial", 9), anchor="e")
        canvas.create_text(off_x + 225, y_pos, text=val, fill="#ffd700", font=("Arial", 9, "bold"), anchor="w")
        y_pos += 19

    if juego_en_pausa:
        t_reanudar = "▶  REANUDAR JUEGO  ◀" if opcion_ajustes_seleccionada == 4 else "REANUDAR JUEGO"
        b_reanudar = "#ffffff" if opcion_ajustes_seleccionada == 4 else "#00ff88"
        f_reanudar = "#104025" if opcion_ajustes_seleccionada == 4 else "#0d091a"
        dibujar_boton(off_x + 60, off_y + 485, off_x + 230, off_y + 530, t_reanudar, b_reanudar, color_fondo=f_reanudar)

        t_menu = "▶  MENÚ PRINCIPAL  ◀" if opcion_ajustes_seleccionada == 5 else "MENÚ PRINCIPAL"
        b_menu = "#ffffff" if opcion_ajustes_seleccionada == 5 else "#a0a0c0"
        f_menu = "#303040" if opcion_ajustes_seleccionada == 5 else "#0d091a"
        dibujar_boton(off_x + 250, off_y + 485, off_x + 420, off_y + 530, t_menu, b_menu, color_fondo=f_menu)
    else:
        t_volver_ajustes = "▶  VOLVER AL MENÚ  ◀" if opcion_ajustes_seleccionada == 4 else "VOLVER AL MENÚ"
        b_volver_ajustes = "#ffffff" if opcion_ajustes_seleccionada == 4 else "#a0a0c0"
        f_volver_ajustes = "#303040" if opcion_ajustes_seleccionada == 4 else "#0d091a"
        dibujar_boton(off_x + 140, off_y + 485, off_x + 340, off_y + 530, t_volver_ajustes, b_volver_ajustes, color_fondo=f_volver_ajustes)

def redibujar():
    canvas.delete("all")
    off_x, off_y, cw, ch = obtener_offset_pantalla()
    if estado_pantalla == "INTRO":
        pass
    elif estado_pantalla == "MENU":
        dibujar_menu_principal()
    elif estado_pantalla == "MODOS":
        dibujar_pantalla_modos()
    elif estado_pantalla == "ONLINE":
        dibujar_pantalla_online()
    elif estado_pantalla == "AJUSTES":
        dibujar_pantalla_ajustes()
    elif estado_pantalla == "JUEGO":
        img_bg = obtener_imagen_juego_escalada(fondo_juego_actual, cw, ch)
        if img_bg is not None:
            canvas.create_image(0, 0, image=img_bg, anchor="nw")
        else:
            canvas.create_rectangle(0, 0, cw, ch, fill="#121218", outline="")
        dibujar_tablero()
        dibujar_pieza()
        dibujar_panel()
        if modo_juego == "VERSUS":
            dibujar_panel_rival()

        # Renderizado y fisica de particulas (Hard Drop y Bombas)
        actualizar_y_dibujar_particulas()

        if texto_flotante_msg and (time.time() - texto_flotante_tiempo < 1.2):
            dt = time.time() - texto_flotante_tiempo
            dy = int(dt * 20)
            canvas.create_text(off_x + ancho // 2 + 1, off_y + 220 - dy + 1, text=texto_flotante_msg, fill="#000000", font=("Arial", 16, "bold"))
            canvas.create_text(off_x + ancho // 2, off_y + 220 - dy, text=texto_flotante_msg, fill=texto_flotante_color, font=("Arial", 16, "bold"))

        if modo_juego == "VERSUS":
            if msg_ataque_p1 and (time.time() - msg_ataque_p1_tiempo < 1.5):
                canvas.create_text(off_x + ancho // 2, off_y + 140, text=msg_ataque_p1, fill="#ff4444", font=("Arial", 11, "bold"))
            if msg_ataque_rival and (time.time() - msg_ataque_rival_tiempo < 1.5):
                off_r = off_x + ancho + 200
                canvas.create_text(off_r + ancho // 2, off_y + 140, text=msg_ataque_rival, fill="#00ff88", font=("Arial", 11, "bold"))

        if juego_en_pausa:
            dibujar_modal_pausa()
        elif juego_terminado or (modo_juego == "VERSUS" and juego_terminado_rival):
            dibujar_game_over()

def reanudar_juego():
    global estado_pantalla, juego_en_pausa, tiempo_pausado_total, tiempo_inicio_pausa
    if tiempo_inicio_pausa > 0:
        tiempo_pausado_total += time.time() - tiempo_inicio_pausa
        tiempo_inicio_pausa = 0.0
    estado_pantalla = "JUEGO"
    juego_en_pausa = False
    actualizar_musica_estado()
    redibujar()
    caer()
    if modo_juego == "VERSUS":
        caer_rival()
    if modo_individual in ["SPRINT", "BLITZ", "SURVIVAL"]:
        bucle_tick_modo()
    if modo_individual == "SURVIVAL":
        iniciar_bucle_survival()

def volver_al_menu(event=None):
    global estado_pantalla, juego_en_pausa, stop_sync_online, juego_terminado, juego_terminado_rival
    stop_sync_online = True
    detener_timers_juego()
    estado_pantalla = "MENU"
    juego_en_pausa = False
    juego_terminado = False
    juego_terminado_rival = False
    ajustar_tamano_ventana()
    actualizar_musica_estado()
    redibujar()

def manejar_clic(event):
    global estado_pantalla, sonido_activado, musica_activada, juego_en_pausa
    if estado_pantalla == "INTRO":
        finalizar_intro()
        return
    x, y = event.x, event.y
    off_x, off_y, cw, ch = obtener_offset_pantalla()

    if estado_pantalla == "MENU":
        if coords_btn_solo[0] <= x <= coords_btn_solo[2] and coords_btn_solo[1] <= y <= coords_btn_solo[3]:
            opcion_menu_seleccionada = 0
            iniciar_un_solo_jugador()
        elif coords_btn_online[0] <= x <= coords_btn_online[2] and coords_btn_online[1] <= y <= coords_btn_online[3]:
            opcion_menu_seleccionada = 1
            estado_pantalla = "ONLINE"
            redibujar()
        elif coords_btn_ajustes[0] <= x <= coords_btn_ajustes[2] and coords_btn_ajustes[1] <= y <= coords_btn_ajustes[3]:
            opcion_menu_seleccionada = 2
            estado_pantalla = "AJUSTES"
            redibujar()
    elif estado_pantalla == "MODOS":
        for idx, coords in enumerate(coords_btn_modos):
            if coords[0] <= x <= coords[2] and coords[1] <= y <= coords[3]:
                opcion_modos_seleccionada = idx
                reproducir_sonido("menu_select")
                if idx == 0:
                    iniciar_modo_individual("CLASICO")
                elif idx == 1:
                    iniciar_modo_individual("SPRINT")
                elif idx == 2:
                    iniciar_modo_individual("BLITZ")
                elif idx == 3:
                    iniciar_modo_individual("SURVIVAL")
                elif idx == 4:
                    iniciar_modo_individual("CAOS")
                elif idx == 5:
                    iniciar_modo_individual("POWERUPS")
                elif idx == 6:
                    volver_al_menu()
                return
    elif estado_pantalla == "JUEGO":
        # Clics cuando la partida ha terminado (Game Over / Victoria)
        if juego_terminado or (modo_juego == "VERSUS" and juego_terminado_rival):
            if coords_btn_gameover_restart[0] <= x <= coords_btn_gameover_restart[2] and coords_btn_gameover_restart[1] <= y <= coords_btn_gameover_restart[3]:
                reproducir_sonido("menu_select")
                reiniciar_juego()
                return
            elif coords_btn_gameover_menu[0] <= x <= coords_btn_gameover_menu[2] and coords_btn_gameover_menu[1] <= y <= coords_btn_gameover_menu[3]:
                reproducir_sonido("menu_select")
                volver_al_menu()
                return

        if modo_individual == "POWERUPS":
            for p_idx, p_coords in enumerate(coords_btn_powerups):
                if p_coords[0] <= x <= p_coords[2] and p_coords[1] <= y <= p_coords[3]:
                    activar_powerup(p_idx)
                    return
            if (off_y + 428) <= y <= (off_y + 458):
                if (off_x + ancho + 15) <= x <= (off_x + ancho + 62):
                    mover(-1)
                    return
                elif (off_x + ancho + 67) <= x <= (off_x + ancho + 113):
                    intentar_rotar()
                    return
                elif (off_x + ancho + 118) <= x <= (off_x + ancho + 165):
                    mover(1)
                    return
            elif (off_y + 463) <= y <= (off_y + 494):
                if (off_x + ancho + 15) <= x <= (off_x + ancho + 87):
                    bajar_rapido()
                    return
                elif (off_x + ancho + 93) <= x <= (off_x + ancho + 165):
                    caida_instantanea()
                    return
            elif (off_y + 499) <= y <= (off_y + 535):
                if (off_x + ancho + 15) <= x <= (off_x + ancho + 87):
                    alternar_pausa()
                    return
                elif (off_x + ancho + 93) <= x <= (off_x + ancho + 165):
                    pausar_y_abrir_opciones()
                    return
            return

        if (off_y + 390) <= y <= (off_y + 422):
            if (off_x + ancho + 15) <= x <= (off_x + ancho + 62):
                mover(-1)
                return
            elif (off_x + ancho + 67) <= x <= (off_x + ancho + 113):
                intentar_rotar()
                return
            elif (off_x + ancho + 118) <= x <= (off_x + ancho + 165):
                mover(1)
                return

        elif (off_y + 427) <= y <= (off_y + 459):
            if (off_x + ancho + 15) <= x <= (off_x + ancho + 87):
                bajar_rapido()
                return
            elif (off_x + ancho + 93) <= x <= (off_x + ancho + 165):
                caida_instantanea()
                return

        elif (off_y + 464) <= y <= (off_y + 496):
            if (off_x + ancho + 15) <= x <= (off_x + ancho + 87):
                guardar_pieza()
                return
            elif (off_x + ancho + 93) <= x <= (off_x + ancho + 165):
                reiniciar_juego()
                return

        elif (off_y + 501) <= y <= (off_y + 537):
            if (off_x + ancho + 15) <= x <= (off_x + ancho + 87):
                alternar_pausa()
                return
            elif (off_x + ancho + 93) <= x <= (off_x + ancho + 165):
                pausar_y_abrir_opciones()
                return

        if juego_en_pausa:
            cx = off_x + (ancho // 2)
            cy = off_y + (alto // 2)
            box_h = 240
            y1 = cy - box_h // 2
            if (cx - 110) <= x <= (cx + 110) and (y1 + 75) <= y <= (y1 + 115):
                reanudar_juego()
            elif (cx - 110) <= x <= (cx + 110) and (y1 + 125) <= y <= (y1 + 165):
                estado_pantalla = "AJUSTES"
                redibujar()
            elif (cx - 110) <= x <= (cx + 110) and (y1 + 175) <= y <= (y1 + 215):
                volver_al_menu()
    elif estado_pantalla == "ONLINE":
        if estado_sala_online == "ESPERANDO":
            if (off_x + 140) <= x <= (off_x + 340) and (off_y + 420) <= y <= (off_y + 470):
                cancelar_sala_online()
        else:
            if (off_x + 60) <= x <= (off_x + 420) and (off_y + 240) <= y <= (off_y + 285):
                crear_sala_online()
            elif (off_x + 60) <= x <= (off_x + 420) and (off_y + 295) <= y <= (off_y + 340):
                vincular_sala_online()
            elif (off_x + 60) <= x <= (off_x + 420) and (off_y + 350) <= y <= (off_y + 395):
                iniciar_modo_versus()
            elif (off_x + 140) <= x <= (off_x + 340) and (off_y + 440) <= y <= (off_y + 490):
                volver_al_menu()
    elif estado_pantalla == "AJUSTES":
        if (off_x + 235) <= x <= (off_x + 415) and (off_y + 100) <= y <= (off_y + 135):
            opcion_ajustes_seleccionada = 0
            sonido_activado = not sonido_activado
            redibujar()
        elif (off_x + 235) <= x <= (off_x + 415) and (off_y + 150) <= y <= (off_y + 185):
            opcion_ajustes_seleccionada = 1
            musica_activada = not musica_activada
            actualizar_musica_estado()
            redibujar()
        elif (off_x + 225) <= x <= (off_x + 435) and (off_y + 223) <= y <= (off_y + 250):
            opcion_ajustes_seleccionada = 2
            cambiar_cancion()
        elif (off_x + 225) <= x <= (off_x + 435) and (off_y + 257) <= y <= (off_y + 284):
            opcion_ajustes_seleccionada = 3
            cambiar_fondo()
        elif juego_en_pausa:
            if (off_x + 60) <= x <= (off_x + 230) and (off_y + 485) <= y <= (off_y + 530):
                opcion_ajustes_seleccionada = 4
                reanudar_juego()
            elif (off_x + 250) <= x <= (off_x + 420) and (off_y + 485) <= y <= (off_y + 530):
                opcion_ajustes_seleccionada = 5
                volver_al_menu()
        else:
            if (off_x + 140) <= x <= (off_x + 340) and (off_y + 485) <= y <= (off_y + 530):
                opcion_ajustes_seleccionada = 4
                volver_al_menu()

def alternar_pantalla_completa(event=None):
    es_full = root.attributes("-fullscreen")
    root.attributes("-fullscreen", not es_full)

canvas.bind("<Button-1>", manejar_clic)
canvas.bind("<Configure>", lambda e: redibujar())

def activar_powerup(idx):
    global slots_powerups, tiempo_congelado_hasta, texto_flotante_msg, texto_flotante_color, texto_flotante_tiempo, puntuacion, tablero
    if modo_individual != "POWERUPS" or estado_pantalla != "JUEGO" or juego_terminado or juego_en_pausa:
        return
    if idx < 0 or idx >= len(slots_powerups):
        return
    poder = slots_powerups.pop(idx)
    off_x, off_y, _, _ = obtener_offset_pantalla()

    if poder == "BOMBA":
        cx = max(1, min(COLUMNAS - 2, pos_x + 1))
        cy = max(1, min(FILAS - 2, pos_y + 1))
        bloques = 0
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < FILAS and 0 <= nx < COLUMNAS:
                    if tablero[ny][nx] != 0:
                        bloques += 1
                    tablero[ny][nx] = 0
        centro_x = off_x + (cx + 0.5) * TAMANO_BLOQUE
        centro_y = off_y + (cy + 0.5) * TAMANO_BLOQUE
        agregar_particulas_impacto(centro_x, centro_y, color="#ff3838", cantidad=30, velocidad=9.0)
        agregar_particulas_impacto(centro_x, centro_y, color="#ffd700", cantidad=20, velocidad=6.0)
        reproducir_sonido("explosion")
        pts = 300 + bloques * 50
        puntuacion += pts
        texto_flotante_msg = f"💣 ¡BOMBA DETONADA! +{pts} 💣"
        texto_flotante_color = "#ff4444"
        texto_flotante_tiempo = time.time()
        limpiar_filas()
        redibujar()

    elif poder == "LASER":
        c1 = max(0, min(COLUMNAS - 2, pos_x))
        c2 = c1 + 1
        bloques = 0
        for y in range(FILAS):
            if tablero[y][c1] != 0:
                bloques += 1
            if tablero[y][c2] != 0:
                bloques += 1
            tablero[y][c1] = 0
            tablero[y][c2] = 0
        for y in range(0, FILAS, 2):
            agregar_particulas_impacto(off_x + (c1 + 1) * TAMANO_BLOQUE, off_y + y * TAMANO_BLOQUE, color="#00f0ff", cantidad=6, velocidad=5.0)
            agregar_particulas_impacto(off_x + (c1 + 1) * TAMANO_BLOQUE, off_y + y * TAMANO_BLOQUE, color="#ff00ff", cantidad=4, velocidad=4.0)
        reproducir_sonido("tetris")
        pts = 400 + bloques * 40
        puntuacion += pts
        texto_flotante_msg = f"⚡ ¡LÁSER PURGADOR! +{pts} ⚡"
        texto_flotante_color = "#00f0ff"
        texto_flotante_tiempo = time.time()
        limpiar_filas()
        redibujar()

    elif poder == "CONGELAR":
        tiempo_congelado_hasta = time.time() + 8.0
        reproducir_sonido("hold")
        off_x, off_y, _, _ = obtener_offset_pantalla()
        agregar_particulas_impacto(off_x + ancho // 2, off_y + alto // 2, color="#70fff0", cantidad=35, velocidad=7.0)
        texto_flotante_msg = "❄️ ¡TIEMPO CONGELADO (8s)! ❄️"
        texto_flotante_color = "#00ffff"
        texto_flotante_tiempo = time.time()
        reiniciar_timer_caer()
        redibujar()

    elif poder == "LIMPIADOR":
        filas_con_bloques = [y for y in range(FILAS) if any(tablero[y][x] != 0 for x in range(COLUMNAS))]
        borrar = filas_con_bloques[-4:] if len(filas_con_bloques) >= 4 else filas_con_bloques
        for y in borrar:
            for x in range(COLUMNAS):
                tablero[y][x] = 0
        nuevas = [f for idx, f in enumerate(tablero) if idx not in borrar]
        vacias: list[list[int | str]] = [[0 for _ in range(COLUMNAS)] for _ in range(len(borrar))]
        tablero = vacias + nuevas
        reproducir_sonido("level_up")
        off_x, off_y, _, _ = obtener_offset_pantalla()
        agregar_particulas_impacto(off_x + ancho // 2, off_y + alto - 60, color="#ffd700", cantidad=30, velocidad=8.0)
        puntuacion += 500
        texto_flotante_msg = "🧹 ¡SUELO LIMPIADO! +500 🧹"
        texto_flotante_color = "#ffd700"
        texto_flotante_tiempo = time.time()
        redibujar()

def guardar_pieza():
    global pieza_actual, colores_actual, pos_x, pos_y, nombre_pieza, nombre_siguiente_pieza, nombre_pieza_guardada, puede_guardar, conteo_piezas
    if estado_pantalla != "JUEGO" or not puede_guardar or juego_terminado or juego_en_pausa or (modo_juego == "VERSUS" and juego_terminado_rival):
        return
    if nombre_pieza_guardada is None:
        nombre_pieza_guardada = nombre_pieza
        nombre_pieza = nombre_siguiente_pieza
        nombre_siguiente_pieza = obtener_siguiente_de_bolsa(es_rival=False)
        conteo_piezas[nombre_pieza] = conteo_piezas.get(nombre_pieza, 0) + 1
    else:
        nombre_pieza, nombre_pieza_guardada = nombre_pieza_guardada, nombre_pieza
    pieza_actual = PIEZAS[nombre_pieza]
    colores_actual = COLORES[nombre_pieza]
    pos_x = COLUMNAS // 2 - 1
    pos_y = 0
    puede_guardar = False
    reproducir_sonido("hold")
    redibujar()

def reiniciar_juego():
    global tablero, puntuacion, nombre_pieza, nombre_siguiente_pieza, pieza_actual, colores_actual, pos_x, pos_y, nombre_pieza_guardada, puede_guardar, juego_terminado, juego_terminado_rival, es_nuevo_record, lineas_totales, combo_actual, conteo_piezas, bolsa_piezas_p1, tiempo_inicio_modo, tiempo_pausado_total, tiempo_inicio_pausa, oleada_survival, es_victoria_modo, tiempo_final_sprint, energia_powerups, slots_powerups, tiempo_congelado_hasta
    detener_timers_juego()
    tablero = [[0 for _ in range(COLUMNAS)] for _ in range(FILAS)]
    puntuacion = 0
    lineas_totales = 0
    combo_actual = 0
    oleada_survival = 0
    es_victoria_modo = False
    tiempo_final_sprint = 0.0
    tiempo_inicio_modo = time.time()
    tiempo_pausado_total = 0.0
    tiempo_inicio_pausa = 0.0
    energia_powerups = 0
    slots_powerups = ["BOMBA"] if modo_individual == "POWERUPS" else []
    tiempo_congelado_hasta = 0.0
    conteo_piezas = {k: 0 for k in PIEZAS}
    es_nuevo_record = False
    bolsa_piezas_p1 = rellenar_bolsa_7() + rellenar_bolsa_7()
    nombre_pieza = obtener_siguiente_de_bolsa(es_rival=False)
    nombre_siguiente_pieza = obtener_siguiente_de_bolsa(es_rival=False)
    conteo_piezas[nombre_pieza] = 1
    pieza_actual = PIEZAS[nombre_pieza]
    colores_actual = COLORES[nombre_pieza]
    pos_x = COLUMNAS // 2 - 1
    pos_y = 0
    nombre_pieza_guardada = None
    puede_guardar = True
    juego_terminado = False
    juego_terminado_rival = False
    seleccionar_cancion_aleatoria_juego(forzar_diferente=True)
    actualizar_musica_estado(forzar_juego=True)
    seleccionar_fondo_aleatorio_juego(forzar_diferente=True)
    redibujar()
    if estado_pantalla == "JUEGO":
        caer()
        if modo_juego == "VERSUS":
            caer_rival()
        if modo_individual in ["SPRINT", "BLITZ", "SURVIVAL"]:
            bucle_tick_modo()
        if modo_individual == "SURVIVAL":
            iniciar_bucle_survival()

def fijar_pieza(es_hard_drop=False):
    global pieza_actual, colores_actual, pos_x, pos_y, puede_guardar, nombre_pieza, nombre_siguiente_pieza, juego_terminado, maximo_puntaje, es_nuevo_record, conteo_piezas, puntuacion, texto_flotante_msg, texto_flotante_color, texto_flotante_tiempo, tablero
    if juego_terminado or (modo_juego == "VERSUS" and juego_terminado_rival):
        return

    # MECÁNICA ESPECIAL BLOCKS BOOM: DETONACIÓN DE BOMBA
    if nombre_pieza == 'BOMB':
        # Calcular centro de impacto de la bomba
        cx = pos_x
        cy = pos_y
        bloques_destruidos = 0
        off_x, off_y, _, _ = obtener_offset_pantalla()

        # Destruir bloques en radio 3x3 alrededor del centro
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                nx = cx + dx
                ny = cy + dy
                if 0 <= nx < COLUMNAS and 0 <= ny < FILAS:
                    if tablero[ny][nx] != 0:
                        bloques_destruidos += 1
                    tablero[ny][nx] = 0

        # Particulas y sonido de la gran explosion
        centro_px_x = off_x + (cx + 0.5) * TAMANO_BLOQUE
        centro_px_y = off_y + (cy + 0.5) * TAMANO_BLOQUE
        agregar_particulas_impacto(centro_px_x, centro_px_y, color="#ff3838", cantidad=25, velocidad=8.0)
        agregar_particulas_impacto(centro_px_x, centro_px_y, color="#ffd700", cantidad=18, velocidad=6.0)
        reproducir_sonido("explosion")

        pts_bomba = 250 + bloques_destruidos * 50
        puntuacion += pts_bomba
        texto_flotante_msg = f"💣 ¡BOOM! +{pts_bomba} 💣"
        texto_flotante_color = "#ff4444"
        texto_flotante_tiempo = time.time()
        filas_limpiadas = limpiar_filas()
    else:
        for f_idx, fila in enumerate(pieza_actual):
            for c_idx, valor in enumerate(fila):
                if valor:
                    tablero[pos_y + f_idx][pos_x + c_idx] = colores_actual
        filas_limpiadas = limpiar_filas()
        if filas_limpiadas == 0 and not es_hard_drop:
            reproducir_sonido("fijar")

    puede_guardar = True
    nombre_pieza = nombre_siguiente_pieza
    nombre_siguiente_pieza = obtener_siguiente_de_bolsa(es_rival=False)
    conteo_piezas[nombre_pieza] = conteo_piezas.get(nombre_pieza, 0) + 1
    pieza_actual = PIEZAS[nombre_pieza]
    colores_actual = COLORES[nombre_pieza]
    pos_x = COLUMNAS // 2 - 1 
    pos_y = 0

    if not es_valido(pieza_actual, pos_x, pos_y):
        juego_terminado = True
        detener_timers_juego()
        if puntuacion > 0:
            guardar_puntaje_firebase("Jugador 1", puntuacion)
        if puntuacion > maximo_puntaje:
            maximo_puntaje = puntuacion
            es_nuevo_record = True
            reproducir_sonido("record")
        else:
            es_nuevo_record = False
        actualizar_musica_estado()
        redibujar()

def limpiar_filas():
    global tablero, puntuacion, lineas_totales, combo_actual, texto_flotante_msg, texto_flotante_color, texto_flotante_tiempo, msg_ataque_rival, msg_ataque_rival_tiempo, juego_terminado, es_victoria_modo, tiempo_final_sprint, energia_powerups, slots_powerups
    indices_completos = [idx for idx, fila in enumerate(tablero) if all(valor != 0 for valor in fila)]
    filas_eliminadas = len(indices_completos)
    if filas_eliminadas > 0:
        nuevas_filas = [fila for idx, fila in enumerate(tablero) if idx not in indices_completos]
        filas_vacias: list[list[int | str]] = [[0 for _ in range(COLUMNAS)] for _ in range(filas_eliminadas)]
        tablero = filas_vacias + nuevas_filas
        lineas_totales += filas_eliminadas
        combo_actual += 1

        if modo_individual == "POWERUPS":
            energia_ganada = filas_eliminadas * 25
            energia_powerups = min(100, energia_powerups + energia_ganada)
            if energia_powerups >= 100:
                if len(slots_powerups) < 3:
                    nuevo_poder = random.choice(["BOMBA", "LASER", "CONGELAR", "LIMPIADOR"])
                    slots_powerups.append(nuevo_poder)
                    energia_powerups = 0
                    reproducir_sonido("record")
                    texto_flotante_msg = f"✨ ¡PODER LISTO: {nuevo_poder}! ✨"
                    texto_flotante_color = "#ff77cc"
                    texto_flotante_tiempo = time.time()

        if modo_individual == "SPRINT" and lineas_totales >= lineas_objetivo_sprint:
            juego_terminado = True
            es_victoria_modo = True
            tiempo_final_sprint = max(0.0, time.time() - tiempo_inicio_modo - tiempo_pausado_total)
            detener_timers_juego()
            reproducir_sonido("victoria")
            actualizar_musica_estado()
            redibujar()
            return filas_eliminadas

        nivel_ant = min(10, 1 + puntuacion // 1000)
        pts_base = 100
        if filas_eliminadas == 4:
            pts_base = 800
            reproducir_sonido("tetris")
            texto_flotante_msg = "💥 ¡AMEIZING! +800 💥"
            texto_flotante_color = "#ffd700"
            texto_flotante_tiempo = time.time()
            off_x, off_y, _, _ = obtener_offset_pantalla()
            agregar_particulas_impacto(off_x + ancho // 2, off_y + alto // 2, color="#ffd700", cantidad=20, velocidad=6.0)
        elif filas_eliminadas == 3:
            pts_base = 500
            reproducir_sonido("limpiar_3")
            texto_flotante_msg = "✨ TRIPLE! +500 ✨"
            texto_flotante_color = "#ffdd00"
            texto_flotante_tiempo = time.time()
        elif filas_eliminadas == 2:
            pts_base = 300
            reproducir_sonido("limpiar_2")
            texto_flotante_msg = "⭐ DOBLE! +300 ⭐"
            texto_flotante_color = "#aaffaa"
            texto_flotante_tiempo = time.time()
        else:
            pts_base = 100
            reproducir_sonido("limpiar_1")

        bonus_combo = 0
        if combo_actual > 1:
            bonus_combo = (combo_actual - 1) * 50
            reproducir_sonido_combo(combo_actual)
            if filas_eliminadas < 4:
                texto_flotante_msg = f"🔥 COMBO x{combo_actual}! +{bonus_combo} 🔥"
                texto_flotante_color = "#ff9900"
                texto_flotante_tiempo = time.time()

        puntuacion += pts_base + bonus_combo
        nivel_post = min(10, 1 + puntuacion // 1000)
        if nivel_post > nivel_ant:
            reproducir_sonido("level_up")
            if filas_eliminadas < 4:
                texto_flotante_msg = f"🏆 ¡NIVEL {nivel_post}! 🏆"
                texto_flotante_color = "#ffd700"
                texto_flotante_tiempo = time.time()

        # Sistema de Ataques de Basura (Estilo Tetris 99)
        filas_ataque = 0
        if filas_eliminadas == 2: filas_ataque = 1
        elif filas_eliminadas == 3: filas_ataque = 2
        elif filas_eliminadas == 4: filas_ataque = 4

        if combo_actual > 1:
            filas_ataque += 1

        if modo_juego == "VERSUS" and filas_ataque > 0:
            if codigo_sala_actual:
                enviar_basura_online(filas_ataque)
            else:
                agregar_lineas_basura(tablero_rival, filas_ataque)
            msg_ataque_rival = f"💣 ¡BASURA ENVIADA +{filas_ataque}!"
            msg_ataque_rival_tiempo = time.time()
    else:
        combo_actual = 0
    return filas_eliminadas

def bajar_rapido():
    global pos_y
    if estado_pantalla != "JUEGO" or juego_terminado or juego_en_pausa or (modo_juego == "VERSUS" and juego_terminado_rival):
        return
    if es_valido(pieza_actual, pos_x, pos_y + 1):
        pos_y += 1
        cancelar_lock_delay()
        redibujar()
    else:
        refrescar_lock_delay_si_aplica()

"""
Navegacion y manejadores de eventos del raton
"""
def iniciar_un_solo_jugador():
    global estado_pantalla, opcion_modos_seleccionada
    estado_pantalla = "MODOS"
    opcion_modos_seleccionada = 0
    actualizar_musica_estado()
    redibujar()

def iniciar_modo_versus():
    global estado_pantalla, modo_juego, modo_individual, juego_en_pausa, tablero_rival, puntuacion_rival, lineas_rival, juego_terminado_rival, nombre_pieza_rival, nombre_siguiente_rival, pieza_actual_rival, colores_actual_rival, pos_x_rival, pos_y_rival, bolsa_piezas_rival
    detener_timers_juego()
    modo_juego = "VERSUS"
    modo_individual = "CLASICO"
    estado_pantalla = "JUEGO"
    juego_en_pausa = False
    ajustar_tamano_ventana()
    reiniciar_juego()

    tablero_rival = [[0 for _ in range(COLUMNAS)] for _ in range(FILAS)]
    puntuacion_rival = 0
    lineas_rival = 0
    juego_terminado_rival = False
    bolsa_piezas_rival = rellenar_bolsa_7() + rellenar_bolsa_7()
    nombre_pieza_rival = obtener_siguiente_de_bolsa(es_rival=True)
    nombre_siguiente_rival = obtener_siguiente_de_bolsa(es_rival=True)
    pieza_actual_rival = PIEZAS[nombre_pieza_rival]
    colores_actual_rival = COLORES[nombre_pieza_rival]
    pos_x_rival = COLUMNAS // 2 - 1
    pos_y_rival = 0

    actualizar_musica_estado()
    caer()
    caer_rival()

def alternar_pausa(event=None):
    global juego_en_pausa, estado_pantalla, tiempo_inicio_pausa
    if estado_pantalla == "JUEGO":
        if juego_en_pausa:
            reanudar_juego()
        else:
            juego_en_pausa = True
            tiempo_inicio_pausa = time.time()
            detener_timers_juego()
            actualizar_musica_estado()
            redibujar()
    elif estado_pantalla == "AJUSTES" and juego_en_pausa:
        reanudar_juego()

def pausar_y_abrir_opciones(event=None):
    global estado_pantalla, juego_en_pausa, tiempo_inicio_pausa
    if estado_pantalla == "JUEGO":
        if juego_terminado or (modo_juego == "VERSUS" and juego_terminado_rival):
            volver_al_menu()
            return
        juego_en_pausa = True
        tiempo_inicio_pausa = time.time()
        detener_timers_juego()
        estado_pantalla = "AJUSTES"
        actualizar_musica_estado()
        redibujar()
    elif estado_pantalla == "AJUSTES":
        if juego_en_pausa:
            reanudar_juego()
        else:
            volver_al_menu()
def navegar_menu(delta):
    global opcion_menu_seleccionada, opcion_modos_seleccionada, opcion_online_seleccionada, opcion_ajustes_seleccionada
    if estado_pantalla == "MENU":
        opcion_menu_seleccionada = (opcion_menu_seleccionada + delta) % 3
        reproducir_sonido("menu_move")
        redibujar()
    elif estado_pantalla == "MODOS":
        opcion_modos_seleccionada = (opcion_modos_seleccionada + delta) % 7
        reproducir_sonido("menu_move")
        redibujar()
    elif estado_pantalla == "ONLINE":
        if estado_sala_online != "ESPERANDO":
            opcion_online_seleccionada = (opcion_online_seleccionada + delta) % 4
            reproducir_sonido("menu_move")
            redibujar()
    elif estado_pantalla == "AJUSTES":
        total = 6 if juego_en_pausa else 5
        opcion_ajustes_seleccionada = (opcion_ajustes_seleccionada + delta) % total
        reproducir_sonido("menu_move")
        redibujar()

def navegar_horizontal_ajustes(delta):
    global opcion_ajustes_seleccionada
    if estado_pantalla == "AJUSTES" and juego_en_pausa:
        if opcion_ajustes_seleccionada in [4, 5]:
            if delta > 0 and opcion_ajustes_seleccionada == 4:
                opcion_ajustes_seleccionada = 5
                reproducir_sonido("menu_move")
                redibujar()
            elif delta < 0 and opcion_ajustes_seleccionada == 5:
                opcion_ajustes_seleccionada = 4
                reproducir_sonido("menu_move")
                redibujar()

def seleccionar_opcion_menu():
    global estado_pantalla, sonido_activado, musica_activada, opcion_modos_seleccionada
    if estado_pantalla == "MENU":
        reproducir_sonido("menu_select")
        if opcion_menu_seleccionada == 0:
            iniciar_un_solo_jugador()
        elif opcion_menu_seleccionada == 1:
            estado_pantalla = "ONLINE"
            redibujar()
        elif opcion_menu_seleccionada == 2:
            estado_pantalla = "AJUSTES"
            redibujar()
    elif estado_pantalla == "MODOS":
        reproducir_sonido("menu_select")
        if opcion_modos_seleccionada == 0:
            iniciar_modo_individual("CLASICO")
        elif opcion_modos_seleccionada == 1:
            iniciar_modo_individual("SPRINT")
        elif opcion_modos_seleccionada == 2:
            iniciar_modo_individual("BLITZ")
        elif opcion_modos_seleccionada == 3:
            iniciar_modo_individual("SURVIVAL")
        elif opcion_modos_seleccionada == 4:
            iniciar_modo_individual("CAOS")
        elif opcion_modos_seleccionada == 5:
            iniciar_modo_individual("POWERUPS")
        elif opcion_modos_seleccionada == 6:
            volver_al_menu()
    elif estado_pantalla == "ONLINE":
        reproducir_sonido("menu_select")
        if estado_sala_online == "ESPERANDO":
            cancelar_sala_online()
        else:
            if opcion_online_seleccionada == 0:
                crear_sala_online()
            elif opcion_online_seleccionada == 1:
                vincular_sala_online()
            elif opcion_online_seleccionada == 2:
                iniciar_modo_versus()
            elif opcion_online_seleccionada == 3:
                volver_al_menu()
    elif estado_pantalla == "AJUSTES":
        reproducir_sonido("menu_select")
        if opcion_ajustes_seleccionada == 0:
            sonido_activado = not sonido_activado
            redibujar()
        elif opcion_ajustes_seleccionada == 1:
            musica_activada = not musica_activada
            actualizar_musica_estado()
            redibujar()
        elif opcion_ajustes_seleccionada == 2:
            cambiar_cancion()
        elif opcion_ajustes_seleccionada == 3:
            cambiar_fondo()
        elif opcion_ajustes_seleccionada == 4:
            if juego_en_pausa:
                reanudar_juego()
            else:
                volver_al_menu()
        elif opcion_ajustes_seleccionada == 5 and juego_en_pausa:
            volver_al_menu()
    elif estado_pantalla == "INTRO":
        finalizar_intro()

def manejar_tecla_presionada(event):
    if estado_pantalla == "INTRO":
        finalizar_intro()

root.bind("<Escape>", pausar_y_abrir_opciones)
root.bind("<m>", pausar_y_abrir_opciones)
root.bind("<M>", pausar_y_abrir_opciones)
root.bind("<p>", alternar_pausa)
root.bind("<P>", alternar_pausa)
root.bind("<F11>", alternar_pantalla_completa)

root.bind("<Return>", lambda e: seleccionar_opcion_menu())
root.bind("<KP_Enter>", lambda e: seleccionar_opcion_menu())
root.bind("<space>", lambda e: seleccionar_opcion_menu() if estado_pantalla in ["MENU", "MODOS", "INTRO"] else caida_instantanea())
root.bind("<Escape>", lambda e: volver_al_menu() if (estado_pantalla in ["MODOS", "ONLINE", "AJUSTES"] or (estado_pantalla == "JUEGO" and (juego_terminado or (modo_juego == "VERSUS" and juego_terminado_rival)))) else pausar_y_abrir_opciones(e))

root.bind("1", lambda e: activar_powerup(0) if estado_pantalla == "JUEGO" else None)
root.bind("<KP_1>", lambda e: activar_powerup(0) if estado_pantalla == "JUEGO" else None)
root.bind("2", lambda e: activar_powerup(1) if estado_pantalla == "JUEGO" else None)
root.bind("<KP_2>", lambda e: activar_powerup(1) if estado_pantalla == "JUEGO" else None)
root.bind("3", lambda e: activar_powerup(2) if estado_pantalla == "JUEGO" else None)
root.bind("<KP_3>", lambda e: activar_powerup(2) if estado_pantalla == "JUEGO" else None)

for k in ["<KeyPress-Left>", "<KeyPress-a>", "<KeyPress-A>"]:
    root.bind(k, on_press_left)
for k in ["<KeyRelease-Left>", "<KeyRelease-a>", "<KeyRelease-A>"]:
    root.bind(k, on_release_left)

for k in ["<KeyPress-Right>", "<KeyPress-d>", "<KeyPress-D>"]:
    root.bind(k, on_press_right)
for k in ["<KeyRelease-Right>", "<KeyRelease-d>", "<KeyRelease-D>"]:
    root.bind(k, on_release_right)

for k in ["<KeyPress-Down>", "<KeyPress-s>", "<KeyPress-S>"]:
    root.bind(k, on_press_down)
for k in ["<KeyRelease-Down>", "<KeyRelease-s>", "<KeyRelease-S>"]:
    root.bind(k, on_release_down)

for k in ["<KeyPress-Up>", "<KeyPress-w>", "<KeyPress-W>"]:
    root.bind(k, on_press_up)

root.bind("<FocusOut>", lambda e: cancelar_das_timers())

root.bind("<c>", lambda e: guardar_pieza() if estado_pantalla == "JUEGO" else None)
root.bind("<C>", lambda e: guardar_pieza() if estado_pantalla == "JUEGO" else None)

root.bind("<r>", lambda e: reiniciar_juego() if estado_pantalla == "JUEGO" else None)
root.bind("<R>", lambda e: reiniciar_juego() if estado_pantalla == "JUEGO" else None)

root.bind("<Key>", manejar_tecla_presionada)

"""
Inicio de la aplicacion en la intro o menu principal
"""
if __name__ == "__main__":
    root.after(500, verificar_musica_continua)

    if os.path.exists(obtener_ruta_recurso(os.path.join("media", "Rueda_del_zodiaco_girando_202608131229.mp4"))):
        reproducir_intro_video()
    else:
        estado_pantalla = "MENU"
        actualizar_musica_estado()
        redibujar()
    root.mainloop()











