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

winmm = ctypes.windll.winmm

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
        
        archivos_json = glob.glob("*.json")
        archivo_credencial = None
        for f in archivos_json:
            if "firebase" in f.lower() or "service" in f.lower() or f.lower() == "firebase_key.json":
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
            info_conexion_firebase = f"Conectado: {archivo_credencial}"
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
        import urllib.request, json
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
        import urllib.request, json
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

root = tk.Tk()
root.title("tetris prueba")
root.configure(bg="#121218")

ancho = COLUMNAS * TAMANO_BLOQUE
alto = FILAS * TAMANO_BLOQUE

canvas = tk.Canvas(root, width=ancho + 180, height=alto, bg="#121218", highlightthickness=0)
canvas.pack(fill="both", expand=True)

"""
Calculo dinamico de offset de centrado al cambiar tamano de ventana
"""
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

def dibujar_tablero():
    off_x, off_y, _, _ = obtener_offset_pantalla()
    # Dibujar tablero Jugador 1
    for f in range(FILAS):
        for c in range(COLUMNAS):
            x1 = off_x + c * TAMANO_BLOQUE
            y1 = off_y + f * TAMANO_BLOQUE
            x2 = x1 + TAMANO_BLOQUE
            y2 = y1 + TAMANO_BLOQUE
            color = str(tablero[f][c]) if isinstance(tablero[f][c], str) else ""
            outline_color = "#333348" if tablero[f][c] == 0 else "white"
            canvas.create_rectangle(x1, y1, x2, y2, outline=outline_color, fill=color)

    # Dibujar tablero Rival en Modo Versus
    if modo_juego == "VERSUS":
        off_rival_x = off_x + ancho + 200
        for f in range(FILAS):
            for c in range(COLUMNAS):
                x1 = off_rival_x + c * TAMANO_BLOQUE
                y1 = off_y + f * TAMANO_BLOQUE
                x2 = x1 + TAMANO_BLOQUE
                y2 = y1 + TAMANO_BLOQUE
                color = str(tablero_rival[f][c]) if isinstance(tablero_rival[f][c], str) else ""
                outline_color = "#443344" if tablero_rival[f][c] == 0 else "#ff88aa"
                canvas.create_rectangle(x1, y1, x2, y2, outline=outline_color, fill=color)


"""
Desactivar inicio temprano
"""
#dibujar_tablero()
#root.mainloop()


PIEZAS = {
    'I':[[1, 1, 1, 1]],
    'O':[[1,1],[1,1]],
    'T':[[0,1,0],[1,1,1]],
    'S':[[0,1,1],[1,1,0]],
    'Z':[[1,1,0],[0,1,1]],
    'J':[[1,0,0],[1,1,1]],
    'L':[[0,0,1],[1,1,1]],
}

COLORES = {
    'I':'cyan',
    'O':'yellow',
    'T':'purple',
    'S':'green',
    'Z':'red',
    'J':'blue',
    'L':'orange',
}

nombre_pieza = random.choice(list(PIEZAS.keys()))
nombre_siguiente_pieza = random.choice(list(PIEZAS.keys()))
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
estela_hard_drop_coords = None
estela_hard_drop_tiempo = 0.0
conteo_piezas = {'I': 0, 'O': 0, 'T': 0, 'S': 0, 'Z': 0, 'J': 0, 'L': 0}

"""
Estado y variables para Modo Versus (Doble Pantalla / Tetris 99)
"""
modo_juego = "SOLO"

tablero_rival: list[list[int | str]] = [[0 for _ in range(COLUMNAS)] for _ in range(FILAS)]
nombre_pieza_rival = random.choice(list(PIEZAS.keys()))
nombre_siguiente_rival = random.choice(list(PIEZAS.keys()))
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
    ruta_menu = os.path.join("img", "tetris menu.png")
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
_cache_juego_key = (-1, 0, 0)

"""
Escalado dinamico con cache para imagenes de fondo de partida
"""
def obtener_imagen_juego_escalada(idx, cw, ch):
    global _cache_img_juego, _cache_juego_key
    key = (idx, cw, ch)
    if _cache_img_juego is not None and _cache_juego_key == key:
        return _cache_img_juego
    rutas = [os.path.join("img", "game.png"), os.path.join("img", "game2.png")]
    if 0 <= idx < len(rutas) and os.path.exists(rutas[idx]):
        try:
            from PIL import Image, ImageTk
            img = Image.open(rutas[idx]).resize((cw, ch), Image.Resampling.LANCZOS)
            _cache_img_juego = ImageTk.PhotoImage(img)
            _cache_juego_key = key
            return _cache_img_juego
        except Exception:
            pass
    return None

def cambiar_fondo():
    global fondo_juego_actual
    fondo_juego_actual = (fondo_juego_actual + 1) % 2
    redibujar()

"""
Carga de canciones de fondo
"""
directorio_musica = "music"
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
            detener_musica()
            winmm.mciSendStringW('close sfx_audio', None, 0, 0)
            winmm.mciSendStringW(f'open "{ruta}" type mpegvideo alias sfx_audio', None, 0, 0)
            winmm.mciSendStringW('play sfx_audio', None, 0, 0)
        except Exception:
            pass

def reproducir_musica_por_nombre(nombre_cancion):
    global cancion_reproduciendose
    if not musica_activada or not nombre_cancion:
        detener_musica()
        return
    if cancion_reproduciendose == nombre_cancion:
        return
    try:
        detener_musica()
        ruta_cancion = os.path.abspath(os.path.join(directorio_musica, nombre_cancion))
        winmm.mciSendStringW(f'open "{ruta_cancion}" type mpegvideo alias bgm', None, 0, 0)
        winmm.mciSendStringW('play bgm repeat', None, 0, 0)
        cancion_reproduciendose = nombre_cancion
    except Exception:
        pass

def actualizar_musica_estado():
    if not musica_activada or not lista_canciones:
        detener_musica()
        return
    if juego_en_pausa:
        cancion_pausa = next((f for f in lista_canciones if f.lower() == "pausa.mp3"), None)
        if cancion_pausa:
            reproducir_musica_por_nombre(cancion_pausa)
        else:
            detener_musica()
    elif estado_pantalla in ["MENU", "ONLINE", "AJUSTES"]:
        cancion_menu = next((f for f in lista_canciones if f.lower() == "menu.mp3"), None)
        if cancion_menu:
            reproducir_musica_por_nombre(cancion_menu)
        else:
            detener_musica()
    elif estado_pantalla == "JUEGO":
        canciones_juego = [f for f in lista_canciones if f.lower() not in ["menu.mp3", "pausa.mp3"]]
        if canciones_juego:
            nombre_cancion = random.choice(canciones_juego)
            reproducir_musica_por_nombre(nombre_cancion)
        else:
            detener_musica()

def cambiar_cancion():
    global cancion_actual_idx, lista_canciones
    if not lista_canciones:
        return
    canciones_juego = [f for f in lista_canciones if f.lower() not in ["menu.mp3", "pausa.mp3"]]
    if not canciones_juego:
        return
    nombre_cancion = random.choice(canciones_juego)
    reproducir_musica_por_nombre(nombre_cancion)
    redibujar()

"""
Sintetizador y reproductor de efectos de sonido retro
"""
SND_ASYNC = 0x0001
SND_MEMORY = 0x0004

def generar_wav_notas(lista_notas, sample_rate=44100, volumen=0.3, tipo_onda="sine"):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for freq, dur in lista_notas:
            n_samples = int(sample_rate * (dur / 1000.0))
            for i in range(n_samples):
                t = i / sample_rate
                env = max(0.0, 1.0 - (i / n_samples))
                if tipo_onda == "square":
                    val = 0.6 if math.sin(2 * math.pi * freq * t) >= 0 else -0.6
                else:
                    val = math.sin(2 * math.pi * freq * t)
                sample = int(val * env * volumen * 32767)
                sample = max(-32768, min(32767, sample))
                frames.extend(struct.pack('<h', sample))
        wf.writeframes(frames)
    return buffer.getvalue()

EFECTOS_SONIDO = {
    "mover": generar_wav_notas([(420, 18)], volumen=0.18, tipo_onda="sine"),
    "rotar": generar_wav_notas([(620, 22)], volumen=0.22, tipo_onda="sine"),
    "fijar": generar_wav_notas([(180, 25)], volumen=0.25, tipo_onda="sine"),
    "limpiar": generar_wav_notas([(523, 40), (659, 40), (784, 40), (1046, 60)], volumen=0.25, tipo_onda="sine"),
    "tetris": generar_wav_notas([(523, 40), (659, 40), (784, 40), (1046, 50), (1318, 50), (1568, 80)], volumen=0.35, tipo_onda="sine"),
    "combo": generar_wav_notas([(659, 30), (880, 40), (1046, 50)], volumen=0.3, tipo_onda="sine"),
    "game_over": generar_wav_notas([(330, 70), (261, 70), (196, 80), (130, 100)], volumen=0.3, tipo_onda="sine"),
    "record": generar_wav_notas([(784, 40), (1046, 40), (1318, 50), (1568, 80)], volumen=0.3, tipo_onda="sine")
}

def reproducir_sonido(tipo):
    if not sonido_activado or tipo not in EFECTOS_SONIDO:
        return
    try:
        winmm.PlaySoundW(EFECTOS_SONIDO[tipo], 0, SND_MEMORY | SND_ASYNC)
    except Exception:
        pass

"""
Reproduccion del video de intro
"""
def reproducir_intro_video():
    global cap_intro, video_reproduciendose, estado_pantalla, tiempo_inicio_intro, num_frame_actual
    ruta_video = os.path.join("media", "Rueda_del_zodiaco_girando_202608131229.mp4")
    ruta_audio = os.path.join("media", "intro.mp3")
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
        for f_idx, fila in enumerate(pieza_actual):
            for c_idx, valor in enumerate(fila):
                if valor:
                    x1 = off_x + (pos_x + c_idx) * TAMANO_BLOQUE
                    y1 = off_y + (g_y + f_idx) * TAMANO_BLOQUE
                    x2 = x1 + TAMANO_BLOQUE
                    y2 = y1 + TAMANO_BLOQUE
                    canvas.create_rectangle(x1, y1, x2, y2, outline="#8888aa", fill="", width=1)

    for f_idx, fila in enumerate(pieza_actual):
        for c_idx, valor in enumerate(fila):
            if valor:
                x1 = off_x + (pos_x + c_idx) * TAMANO_BLOQUE
                y1 = off_y + (pos_y + f_idx) * TAMANO_BLOQUE
                x2 = x1 + TAMANO_BLOQUE
                y2 = y1 + TAMANO_BLOQUE
                canvas.create_rectangle(x1, y1, x2, y2, fill=colores_actual, outline="white")

    if modo_juego == "VERSUS":
        off_rival_x = off_x + ancho + 200
        for f_idx, fila in enumerate(pieza_actual_rival):
            for c_idx, valor in enumerate(fila):
                if valor:
                    x1 = off_rival_x + (pos_x_rival + c_idx) * TAMANO_BLOQUE
                    y1 = off_y + (pos_y_rival + f_idx) * TAMANO_BLOQUE
                    x2 = x1 + TAMANO_BLOQUE
                    y2 = y1 + TAMANO_BLOQUE
                    canvas.create_rectangle(x1, y1, x2, y2, fill=colores_actual_rival, outline="white")

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
    nombre_siguiente_rival = random.choice(list(PIEZAS.keys()))
    pieza_actual_rival = PIEZAS[nombre_pieza_rival]
    colores_actual_rival = COLORES[nombre_pieza_rival]
    pos_x_rival = COLUMNAS // 2 - 1
    pos_y_rival = 0

    if not es_valido_rival(pieza_actual_rival, pos_x_rival, pos_y_rival):
        juego_terminado_rival = True
        if not juego_terminado:
            reproducir_audio_efecto("victoria.mp3")
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
    global pos_y_rival, pos_x_rival
    if estado_pantalla != "JUEGO" or modo_juego != "VERSUS" or juego_terminado_rival or juego_en_pausa:
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
    root.after(350, caer_rival)

def caida_instantanea(event=None):
    global pos_y, puntuacion, estela_hard_drop_coords, estela_hard_drop_tiempo
    if estado_pantalla != "JUEGO" or juego_terminado:
        return
    off_x, off_y, _, _ = obtener_offset_pantalla()
    y_inicio = pos_y
    pasos = 0
    while es_valido(pieza_actual, pos_x, pos_y + 1):
        pos_y += 1
        pasos += 1
    puntuacion += pasos * 2
    estela_hard_drop_coords = (off_x + pos_x * TAMANO_BLOQUE, off_y + y_inicio * TAMANO_BLOQUE, off_x + (pos_x + len(pieza_actual[0])) * TAMANO_BLOQUE, off_y + (pos_y + len(pieza_actual)) * TAMANO_BLOQUE)
    estela_hard_drop_tiempo = time.time()
    fijar_pieza()
    redibujar()

def mover(dx):
    global pos_x
    if estado_pantalla != "JUEGO":
        return
    if es_valido(pieza_actual, pos_x + dx, pos_y):
        pos_x += dx
        reproducir_sonido("mover")
        redibujar()
root.bind("<Left>",lambda event:mover(-1))
root.bind("<Right>",lambda event:mover(1))

def caer():
    global pos_y
    if estado_pantalla != "JUEGO" or juego_terminado:
        return
    if es_valido(pieza_actual, pos_x, pos_y + 1):
        pos_y += 1
        redibujar()
    else:
        fijar_pieza()
        if juego_terminado:
            return
        redibujar()
    nivel = min(10, 1 + puntuacion // 1000)
    velocidad = max(80, 500 - (nivel - 1) * 45)
    es_panico = any(any(val != 0 for val in fila) for fila in tablero[:7])
    if es_panico:
        velocidad = max(50, int(velocidad * 0.6))
    root.after(velocidad, caer)

#dibujar_tablero()
#dibujar_pieza()
#caer()
#root.mainloop()

def es_valido(pieza, p_x, p_y):
    for f_idx, fila in enumerate(pieza):
        for c_idx, valor in enumerate(fila):
            if valor:
                x = p_x + c_idx
                y = p_y + f_idx
                if x < 0 or x >= COLUMNAS or y >= FILAS:
                    return False
                if y >= 0 and tablero[y][x] !=0:
                    return False
    return True
def rotar(pieza):
    return[list(fila) for fila in zip(*pieza[::-1])]

def intentar_rotar():
    global pieza_actual
    if estado_pantalla != "JUEGO":
        return
    nueva = rotar(pieza_actual)
    if es_valido(nueva, pos_x, pos_y):
        pieza_actual = nueva
        reproducir_sonido("rotar")
        redibujar()

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
                    canvas.create_rectangle(x1, y1, x2, y2, fill=color_m, outline="white")

def dibujar_panel():
    off_x, off_y, _, _ = obtener_offset_pantalla()
    canvas.create_rectangle(off_x + ancho, off_y + 0, off_x + ancho + 180, off_y + alto, fill="#181822", outline="#2e2e42")
    nivel = min(10, 1 + puntuacion // 1000)

    canvas.create_rectangle(off_x + ancho + 10, off_y + 10, off_x + ancho + 170, off_y + 55, fill="#222230", outline="#36364d")
    canvas.create_text(off_x + ancho + 90, off_y + 22, text="PUNTOS", fill="#a0a0c0", font=("Arial", 8, "bold"))
    canvas.create_text(off_x + ancho + 90, off_y + 40, text=str(puntuacion), fill="#ffd700", font=("Arial", 12, "bold"))

    canvas.create_rectangle(off_x + ancho + 10, off_y + 65, off_x + ancho + 170, off_y + 110, fill="#222230", outline="#36364d")
    canvas.create_text(off_x + ancho + 90, off_y + 77, text="RÉCORD", fill="#a0a0c0", font=("Arial", 8, "bold"))
    canvas.create_text(off_x + ancho + 90, off_y + 95, text=str(maximo_puntaje), fill="#ff9900", font=("Arial", 12, "bold"))

    canvas.create_rectangle(off_x + ancho + 10, off_y + 120, off_x + ancho + 170, off_y + 165, fill="#222230", outline="#36364d")
    canvas.create_text(off_x + ancho + 90, off_y + 131, text=f"NIVEL {nivel} | LÍNEAS: {lineas_totales}", fill="#a0a0c0", font=("Arial", 7, "bold"))
    progreso = (lineas_totales % 10) / 10.0
    canvas.create_rectangle(off_x + ancho + 20, off_y + 145, off_x + ancho + 160, off_y + 154, fill="#121218", outline="#00e5ff")
    if progreso > 0:
        canvas.create_rectangle(off_x + ancho + 21, off_y + 146, off_x + ancho + 21 + int(138 * progreso), off_y + 153, fill="#00e5ff", outline="")

    canvas.create_rectangle(off_x + ancho + 10, off_y + 175, off_x + ancho + 170, off_y + 260, fill="#222230", outline="#36364d")
    canvas.create_text(off_x + ancho + 90, off_y + 187, text="SIGUIENTE", fill="#a0a0c0", font=("Arial", 8, "bold"))
    dibujar_miniatura(nombre_siguiente_pieza, off_x + ancho + 50, off_y + 205)

    canvas.create_rectangle(off_x + ancho + 10, off_y + 270, off_x + ancho + 170, off_y + 355, fill="#222230", outline="#36364d")
    canvas.create_text(off_x + ancho + 90, off_y + 282, text="GUARDADA", fill="#a0a0c0", font=("Arial", 8, "bold"))
    if nombre_pieza_guardada:
        dibujar_miniatura(nombre_pieza_guardada, off_x + ancho + 50, off_y + 300)
    else:
        canvas.create_text(off_x + ancho + 90, off_y + 315, text="[ C ]", fill="#666680", font=("Arial", 10))

    canvas.create_rectangle(off_x + ancho + 10, off_y + 365, off_x + ancho + 170, off_y + 525, fill="#222230", outline="#36364d")
    canvas.create_text(off_x + ancho + 90, off_y + 380, text="CONTROLES", fill="#a0a0c0", font=("Arial", 8, "bold"))
    controles = [("<- / ->", "Mover"), ("Up", "Rotar"), ("Down", "Bajar"), ("Espacio", "Caída"), ("C", "Guardar"), ("R", "Reiniciar"), ("Esc / M", "Opciones")]
    y_ctrl = off_y + 396
    for tecla, accion in controles:
        canvas.create_text(off_x + ancho + 20, y_ctrl, text=tecla, fill="#00ffff", font=("Arial", 7, "bold"), anchor="w")
        canvas.create_text(off_x + ancho + 82, y_ctrl, text=accion, fill="#cccccc", font=("Arial", 7), anchor="w")
        y_ctrl += 18

    dibujar_boton(off_x + ancho + 15, off_y + 535, off_x + ancho + 165, off_y + 580, "⚙️ OPCIONES", "#ffd700", font_size=10)

def dibujar_game_over():
    off_x, off_y, _, _ = obtener_offset_pantalla()
    canvas.create_rectangle(off_x + 20, off_y + 160, off_x + ancho - 20, off_y + 440, fill="#1c1c28", outline="#ff4444" if not es_nuevo_record else "#ffd700", width=3)
    canvas.create_text(off_x + ancho // 2, off_y + 190, text="GAME OVER", fill="#ff4444", font=("Arial", 18, "bold"))
    if es_nuevo_record:
        canvas.create_text(off_x + ancho // 2, off_y + 220, text="!NUEVO RECORD!", fill="#ffd700", font=("Arial", 13, "bold"))
    canvas.create_text(off_x + ancho // 2, off_y + 255, text=f"Puntuación: {puntuacion}", fill="white", font=("Arial", 12))
    canvas.create_text(off_x + ancho // 2, off_y + 285, text=f"Líneas Despejadas: {lineas_totales}", fill="#00ff88", font=("Arial", 11, "bold"))
    canvas.create_text(off_x + ancho // 2, off_y + 315, text=f"Récord Máximo: {maximo_puntaje}", fill="#00e5ff", font=("Arial", 11))
    
    stats_str = "Piezas: " + " ".join([f"{k}:{v}" for k, v in conteo_piezas.items() if v > 0])
    canvas.create_text(off_x + ancho // 2, off_y + 355, text=stats_str[:38], fill="#a0a0c0", font=("Arial", 8))
    canvas.create_text(off_x + ancho // 2, off_y + 400, text="Presiona [ R ] para reiniciar", fill="#aaaaaa", font=("Arial", 10))

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
        canvas.create_text(cw // 2, off_y + 90, text="T E T R I S", fill="#00e5ff", font=("Arial", 28, "bold"))

    bw = min(380, max(260, int(cw * 0.55)))
    bh = max(45, int(ch * 0.09))
    cx = cw // 2

    y1 = off_y + int(ch * 0.30) if ch > 600 else off_y + 190
    y2 = off_y + int(ch * 0.44) if ch > 600 else off_y + 270
    y3 = off_y + int(ch * 0.58) if ch > 600 else off_y + 350

    coords_btn_solo[0], coords_btn_solo[1], coords_btn_solo[2], coords_btn_solo[3] = cx - bw // 2, y1, cx + bw // 2, y1 + bh
    coords_btn_online[0], coords_btn_online[1], coords_btn_online[2], coords_btn_online[3] = cx - bw // 2, y2, cx + bw // 2, y2 + bh
    coords_btn_ajustes[0], coords_btn_ajustes[1], coords_btn_ajustes[2], coords_btn_ajustes[3] = cx - bw // 2, y3, cx + bw // 2, y3 + bh

    font_sub = max(9, int(min(cw, ch) * 0.022))
    font_btn = max(10, int(min(cw, ch) * 0.024))

    y_sub = y1 - 35
    canvas.create_text(cx + 1, y_sub + 1, text="SELECCIONA UN MODO DE JUEGO", fill="#000000", font=("Arial", font_sub, "bold"))
    canvas.create_text(cx, y_sub, text="SELECCIONA UN MODO DE JUEGO", fill="#00f0ff", font=("Arial", font_sub, "bold"))

    dibujar_boton(coords_btn_solo[0], coords_btn_solo[1], coords_btn_solo[2], coords_btn_solo[3], "UN SOLO JUGADOR", "#00f0ff", color_fondo="#0d091a", font_size=font_btn)
    dibujar_boton(coords_btn_online[0], coords_btn_online[1], coords_btn_online[2], coords_btn_online[3], "MODO ONLINE", "#ff007f", color_fondo="#0d091a", font_size=font_btn)
    dibujar_boton(coords_btn_ajustes[0], coords_btn_ajustes[1], coords_btn_ajustes[2], coords_btn_ajustes[3], "AJUSTES", "#ffd700", color_fondo="#0d091a", font_size=font_btn)

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
            import urllib.request, json
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
            import urllib.request, json
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
                            if not juego_terminado:
                                root.after(0, lambda: reproducir_audio_efecto("victoria.mp3"))

                        basura_recibida = data.get(f"{rol}_basura", 0)
                        if basura_recibida > 0:
                            doc_ref.update({f"{rol}_basura": 0})
                            root.after(0, lambda b=basura_recibida: agregar_lineas_basura(tablero, b))
                        root.after(0, redibujar)
            except Exception:
                pass
        else:
            try:
                import urllib.request, json
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

        dibujar_boton(off_x + 60, off_y + 240, off_x + 420, off_y + 285, "👑 CREAR SALA ONLINE", "#00e5ff", font_size=10)
        dibujar_boton(off_x + 60, off_y + 295, off_x + 420, off_y + 340, "🔗 VINCULAR SALA (INGRESAR CÓDIGO)", "#ff007f", font_size=10)
        dibujar_boton(off_x + 60, off_y + 350, off_x + 420, off_y + 395, "⚔️ MODO VERSUS LOCAL (IA / 2 PANTALLAS)", "#ffd700", font_size=9)

        conectar_firebase()
        if firebase_conectado:
            canvas.create_text(cw // 2, off_y + 415, text="🟢 CONECTADO A FIREBASE FIRESTORE", fill="#00ff88", font=("Arial", 8, "bold"))
        else:
            canvas.create_text(cw // 2, off_y + 415, text="🟡 CONECTADO A SERVIDOR RENDER", fill="#ffd700", font=("Arial", 8, "bold"))

        dibujar_boton(off_x + 140, off_y + 440, off_x + 340, off_y + 490, "VOLVER AL MENÚ", "#a0a0c0")

def dibujar_pantalla_ajustes():
    off_x, off_y, cw, ch = obtener_offset_pantalla()
    canvas.create_rectangle(0, 0, cw, ch, fill="#121218", outline="")
    canvas.create_text(cw // 2, off_y + 50, text="AJUSTES Y OPCIONES", fill="#ffd700", font=("Arial", 22, "bold"))

    canvas.create_rectangle(off_x + 40, off_y + 85, off_x + 440, off_y + 205, fill="#1f1f2e", outline="#36364d", width=2)
    canvas.create_text(off_x + 210, off_y + 115, text="EFECTOS DE SONIDO:", fill="#ffffff", font=("Arial", 10, "bold"), anchor="e")
    estado_sonido = "ACTIVADO" if sonido_activado else "DESACTIVADO"
    color_sonido = "#00ff88" if sonido_activado else "#ff4444"
    dibujar_boton(off_x + 235, off_y + 100, off_x + 415, off_y + 135, estado_sonido, color_sonido, color_texto=color_sonido)

    canvas.create_text(off_x + 210, off_y + 165, text="MÚSICA DE FONDO:", fill="#ffffff", font=("Arial", 10, "bold"), anchor="e")
    estado_musica = "ACTIVADO" if musica_activada else "DESACTIVADO"
    color_musica = "#00ff88" if musica_activada else "#ff4444"
    dibujar_boton(off_x + 235, off_y + 150, off_x + 415, off_y + 185, estado_musica, color_musica, color_texto=color_musica)

    canvas.create_rectangle(off_x + 40, off_y + 215, off_x + 440, off_y + 290, fill="#1f1f2e", outline="#36364d", width=2)
    nombre_cancion = lista_canciones[cancion_actual_idx] if lista_canciones else "Sin canciones"
    canvas.create_text(off_x + 210, off_y + 238, text=f"🎵 {nombre_cancion[:14]}", fill="#00e5ff", font=("Arial", 8, "bold"), anchor="e")
    dibujar_boton(off_x + 225, off_y + 223, off_x + 435, off_y + 250, "CAMBIAR PISTA", "#ff007f", font_size=8)

    lbl_fondo = f"🖼️ Fondo {fondo_juego_actual + 1}"
    canvas.create_text(off_x + 210, off_y + 272, text=lbl_fondo, fill="#00ff88", font=("Arial", 8, "bold"), anchor="e")
    dibujar_boton(off_x + 225, off_y + 257, off_x + 435, off_y + 284, "CAMBIAR FONDO", "#00ff88", font_size=8)

    canvas.create_rectangle(off_x + 40, off_y + 300, off_x + 440, off_y + 470, fill="#1f1f2e", outline="#36364d", width=2)
    canvas.create_text(cw // 2, off_y + 320, text="CONTROLES DEL JUEGO", fill="#00e5ff", font=("Arial", 10, "bold"))
    controles_info = [
        ("Mover Izq / Der:", "Flechas <- / ->"),
        ("Rotar Pieza:", "Flecha Arriba"),
        ("Caída Rápida:", "Flecha Abajo"),
        ("Guardar Pieza:", "Tecla C"),
        ("Reiniciar Partida:", "Tecla R"),
        ("Pausar / Opciones:", "Tecla Esc o M")
    ]
    y_pos = off_y + 345
    for lab, val in controles_info:
        canvas.create_text(off_x + 210, y_pos, text=lab, fill="#cccccc", font=("Arial", 9), anchor="e")
        canvas.create_text(off_x + 225, y_pos, text=val, fill="#ffd700", font=("Arial", 9, "bold"), anchor="w")
        y_pos += 19

    if juego_en_pausa:
        dibujar_boton(off_x + 60, off_y + 485, off_x + 230, off_y + 530, "REANUDAR JUEGO", "#00ff88")
        dibujar_boton(off_x + 250, off_y + 485, off_x + 420, off_y + 530, "MENÚ PRINCIPAL", "#a0a0c0")
    else:
        dibujar_boton(off_x + 140, off_y + 485, off_x + 340, off_y + 530, "VOLVER AL MENÚ", "#a0a0c0")

def redibujar():
    canvas.delete("all")
    off_x, off_y, cw, ch = obtener_offset_pantalla()
    if estado_pantalla == "INTRO":
        pass
    elif estado_pantalla == "MENU":
        dibujar_menu_principal()
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

        if estela_hard_drop_coords and (time.time() - estela_hard_drop_tiempo < 0.12):
            x1, y1, x2, y2 = estela_hard_drop_coords
            canvas.create_rectangle(x1 + 2, y1, x2 - 2, y2, fill="", outline="#00ffff", width=2)

        dibujar_pieza()
        dibujar_panel()

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

        if juego_terminado or (modo_juego == "VERSUS" and juego_terminado_rival):
            dibujar_game_over()

def reanudar_juego():
    global estado_pantalla, juego_en_pausa
    estado_pantalla = "JUEGO"
    juego_en_pausa = False
    actualizar_musica_estado()
    redibujar()
    caer()

def volver_al_menu(event=None):
    global estado_pantalla, juego_en_pausa
    estado_pantalla = "MENU"
    juego_en_pausa = False
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
            iniciar_un_solo_jugador()
        elif coords_btn_online[0] <= x <= coords_btn_online[2] and coords_btn_online[1] <= y <= coords_btn_online[3]:
            estado_pantalla = "ONLINE"
            redibujar()
        elif coords_btn_ajustes[0] <= x <= coords_btn_ajustes[2] and coords_btn_ajustes[1] <= y <= coords_btn_ajustes[3]:
            estado_pantalla = "AJUSTES"
            redibujar()
    elif estado_pantalla == "JUEGO":
        if (off_x + ancho + 15) <= x <= (off_x + ancho + 165) and (off_y + 535) <= y <= (off_y + 580):
            pausar_y_abrir_opciones()
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
            sonido_activado = not sonido_activado
            redibujar()
        elif (off_x + 235) <= x <= (off_x + 415) and (off_y + 150) <= y <= (off_y + 185):
            musica_activada = not musica_activada
            actualizar_musica_estado()
            redibujar()
        elif (off_x + 225) <= x <= (off_x + 435) and (off_y + 223) <= y <= (off_y + 250):
            cambiar_cancion()
        elif (off_x + 225) <= x <= (off_x + 435) and (off_y + 257) <= y <= (off_y + 284):
            cambiar_fondo()
        elif juego_en_pausa:
            if (off_x + 60) <= x <= (off_x + 230) and (off_y + 485) <= y <= (off_y + 530):
                reanudar_juego()
            elif (off_x + 250) <= x <= (off_x + 420) and (off_y + 485) <= y <= (off_y + 530):
                volver_al_menu()
        else:
            if (off_x + 140) <= x <= (off_x + 340) and (off_y + 485) <= y <= (off_y + 530):
                volver_al_menu()

def alternar_pantalla_completa(event=None):
    es_full = root.attributes("-fullscreen")
    root.attributes("-fullscreen", not es_full)

canvas.bind("<Button-1>", manejar_clic)
canvas.bind("<Configure>", lambda e: redibujar())

def guardar_pieza():
    global pieza_actual, colores_actual, pos_x, pos_y, nombre_pieza, nombre_siguiente_pieza, nombre_pieza_guardada, puede_guardar
    if estado_pantalla != "JUEGO" or not puede_guardar or juego_terminado:
        return
    if nombre_pieza_guardada is None:
        nombre_pieza_guardada = nombre_pieza
        nombre_pieza = nombre_siguiente_pieza
        nombre_siguiente_pieza = random.choice(list(PIEZAS.keys()))
    else:
        nombre_pieza, nombre_pieza_guardada = nombre_pieza_guardada, nombre_pieza
    pieza_actual = PIEZAS[nombre_pieza]
    colores_actual = COLORES[nombre_pieza]
    pos_x = COLUMNAS // 2 - 1
    pos_y = 0
    puede_guardar = False
    redibujar()

def reiniciar_juego():
    global tablero, puntuacion, nombre_pieza, nombre_siguiente_pieza, pieza_actual, colores_actual, pos_x, pos_y, nombre_pieza_guardada, puede_guardar, juego_terminado, es_nuevo_record, lineas_totales, combo_actual, conteo_piezas
    tablero = [[0 for _ in range(COLUMNAS)] for _ in range(FILAS)]
    puntuacion = 0
    lineas_totales = 0
    combo_actual = 0
    conteo_piezas = {k: 0 for k in PIEZAS}
    es_nuevo_record = False
    nombre_pieza = random.choice(list(PIEZAS.keys()))
    nombre_siguiente_pieza = random.choice(list(PIEZAS.keys()))
    conteo_piezas[nombre_pieza] = conteo_piezas.get(nombre_pieza, 0) + 1
    pieza_actual = PIEZAS[nombre_pieza]
    colores_actual = COLORES[nombre_pieza]
    pos_x = COLUMNAS // 2 - 1
    pos_y = 0
    nombre_pieza_guardada = None
    puede_guardar = True
    estaba_terminado = juego_terminado
    juego_terminado = False
    redibujar()
    if estaba_terminado and estado_pantalla == "JUEGO":
        caer()

root.bind("<Left>", lambda e: mover(-1))
root.bind("<Right>", lambda e: mover(1))
root.bind("<Up>", lambda e: intentar_rotar())
root.bind("<Down>", lambda e: bajar_rapido())
root.bind("<c>", lambda e: guardar_pieza())
root.bind("<C>", lambda e: guardar_pieza())
root.bind("<r>", lambda e: reiniciar_juego())
root.bind("<R>", lambda e: reiniciar_juego())

def fijar_pieza():
    global pieza_actual, colores_actual, pos_x, pos_y, puede_guardar, nombre_pieza, nombre_siguiente_pieza, juego_terminado, maximo_puntaje, es_nuevo_record, conteo_piezas
    for f_idx,fila in enumerate(pieza_actual):
        for c_idx, valor in enumerate(fila):
            if valor:
                tablero[pos_y + f_idx] [pos_x + c_idx] = colores_actual
    filas_limpiadas = limpiar_filas()
    if filas_limpiadas == 0:
        reproducir_sonido("fijar")

    puede_guardar = True
    nombre_pieza = nombre_siguiente_pieza
    nombre_siguiente_pieza = random.choice(list(PIEZAS.keys()))
    conteo_piezas[nombre_pieza] = conteo_piezas.get(nombre_pieza, 0) + 1
    pieza_actual = PIEZAS[nombre_pieza]
    colores_actual = COLORES[nombre_pieza]
    pos_x = COLUMNAS // 2 - 1 
    pos_y = 0

    if not es_valido(pieza_actual, pos_x, pos_y):
        juego_terminado = True
        if puntuacion > 0:
            guardar_puntaje_firebase("Jugador 1", puntuacion)
        if puntuacion > maximo_puntaje:
            maximo_puntaje = puntuacion
            es_nuevo_record = True
            reproducir_sonido("record")
        else:
            es_nuevo_record = False
            reproducir_audio_efecto("game over.mp3")
        redibujar()

def limpiar_filas():
    global tablero, puntuacion, lineas_totales, combo_actual, texto_flotante_msg, texto_flotante_color, texto_flotante_tiempo, msg_ataque_rival, msg_ataque_rival_tiempo
    nuevas_filas = [fila for fila in tablero if any(valor == 0 for valor in fila)]
    filas_eliminadas = FILAS - len(nuevas_filas)
    if filas_eliminadas > 0:
        filas_vacias: list[list[int | str]] = [[0 for _ in range(COLUMNAS)] for _ in range(filas_eliminadas)]
        tablero = filas_vacias + nuevas_filas
        lineas_totales += filas_eliminadas
        combo_actual += 1

        pts_base = 100
        if filas_eliminadas == 4:
            pts_base = 800
            reproducir_sonido("tetris")
            texto_flotante_msg = "⚡ TETRIS! +800 ⚡"
            texto_flotante_color = "#00ffff"
            texto_flotante_tiempo = time.time()
        elif filas_eliminadas == 3:
            pts_base = 500
            reproducir_sonido("limpiar")
        elif filas_eliminadas == 2:
            pts_base = 300
            reproducir_sonido("limpiar")
        else:
            pts_base = 100
            reproducir_sonido("limpiar")

        bonus_combo = 0
        if combo_actual > 1:
            bonus_combo = (combo_actual - 1) * 50
            reproducir_sonido("combo")
            if filas_eliminadas < 4:
                texto_flotante_msg = f"🔥 COMBO x{combo_actual}! +{bonus_combo} 🔥"
                texto_flotante_color = "#ff9900"
                texto_flotante_tiempo = time.time()

        puntuacion += pts_base + bonus_combo

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
    if estado_pantalla != "JUEGO":
        return
    if es_valido(pieza_actual, pos_x, pos_y + 1):
        pos_y += 1
        redibujar()

"""
Navegacion y manejadores de eventos del raton
"""
def iniciar_un_solo_jugador():
    global estado_pantalla, modo_juego, juego_en_pausa
    modo_juego = "SOLO"
    estado_pantalla = "JUEGO"
    juego_en_pausa = False
    reiniciar_juego()
    actualizar_musica_estado()
    caer()

def iniciar_modo_versus():
    global estado_pantalla, modo_juego, juego_en_pausa, tablero_rival, puntuacion_rival, lineas_rival, juego_terminado_rival, nombre_pieza_rival, nombre_siguiente_rival, pieza_actual_rival, colores_actual_rival, pos_x_rival, pos_y_rival
    modo_juego = "VERSUS"
    estado_pantalla = "JUEGO"
    juego_en_pausa = False
    reiniciar_juego()

    tablero_rival = [[0 for _ in range(COLUMNAS)] for _ in range(FILAS)]
    puntuacion_rival = 0
    lineas_rival = 0
    juego_terminado_rival = False
    nombre_pieza_rival = random.choice(list(PIEZAS.keys()))
    nombre_siguiente_rival = random.choice(list(PIEZAS.keys()))
    pieza_actual_rival = PIEZAS[nombre_pieza_rival]
    colores_actual_rival = COLORES[nombre_pieza_rival]
    pos_x_rival = COLUMNAS // 2 - 1
    pos_y_rival = 0

    actualizar_musica_estado()
    caer()
    caer_rival()

def pausar_y_abrir_opciones(event=None):
    global estado_pantalla, juego_en_pausa
    if estado_pantalla == "JUEGO":
        juego_en_pausa = True
        estado_pantalla = "AJUSTES"
        actualizar_musica_estado()
        redibujar()
    elif estado_pantalla == "AJUSTES":
        if juego_en_pausa:
            reanudar_juego()
        else:
            volver_al_menu()
root.bind("<Escape>", pausar_y_abrir_opciones)
root.bind("<m>", pausar_y_abrir_opciones)
root.bind("<M>", pausar_y_abrir_opciones)
root.bind("<F11>", alternar_pantalla_completa)
root.bind("<space>", caida_instantanea)
root.bind("<Key>", lambda e: finalizar_intro() if estado_pantalla == "INTRO" else None)

"""
Inicio de la aplicacion en la intro o menu principal
"""
if os.path.exists(os.path.join("media", "Rueda_del_zodiaco_girando_202608131229.mp4")):
    reproducir_intro_video()
else:
    estado_pantalla = "MENU"
    actualizar_musica_estado()
    redibujar()
root.mainloop()











