import tkinter as tk
import random
import winsound
import threading

COLUMNAS = 10
FILAS = 20
TAMANO_BLOQUE = 30

tablero = [[0 for _ in
range(COLUMNAS)] for _ in
range(FILAS)]

root = tk.Tk()
root.title("tetris prueba")

ancho = COLUMNAS * TAMANO_BLOQUE
alto = FILAS * TAMANO_BLOQUE

canvas =tk.Canvas(root, width=ancho + 180, height=alto, bg="#121218", highlightthickness=0)
canvas.pack()
def dibujar_tablero():
    for f in range(FILAS):
        for c in range(COLUMNAS):
            x1 = c * TAMANO_BLOQUE
            y1 = f * TAMANO_BLOQUE
            x2 = x1 + TAMANO_BLOQUE
            y2 = y1 + TAMANO_BLOQUE
            color = tablero[f][c] if tablero[f][c] != 0 else "#121218"
            outline_color = "#222230" if tablero[f][c] == 0 else "white"
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
Reproductor de sonidos nativos de Windows
"""
def sonar(tipo):
    try:
        if tipo == "mover":
            winsound.PlaySound("SystemDefault", winsound.SND_ALIAS | winsound.SND_ASYNC)
        elif tipo == "rotar":
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
        elif tipo == "limpiar":
            winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
        elif tipo == "game_over":
            winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC)
        elif tipo == "record":
            winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        pass

def reproducir_sonido(tipo):
    threading.Thread(target=sonar, args=(tipo,), daemon=True).start()

def dibujar_pieza():
    for f_idx, fila in enumerate(pieza_actual):
        for c_idx, valor in enumerate(fila):
            if valor:
                x1 = (pos_x + c_idx) * TAMANO_BLOQUE
                y1 = (pos_y + f_idx) * TAMANO_BLOQUE
                x2 = x1 + TAMANO_BLOQUE
                y2 = y1 + TAMANO_BLOQUE
                canvas.create_rectangle(x1, y1, x2, y2, fill=colores_actual, outline="white")

def mover(dx):
    global pos_x
    if es_valido(pieza_actual, pos_x + dx, pos_y):
        pos_x += dx
        reproducir_sonido("mover")
        redibujar()
root.bind("<Left>",lambda event:mover(-1))
root.bind("<Right>",lambda event:mover(1))

def caer():
    global pos_y
    if juego_terminado:
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
    canvas.create_rectangle(ancho, 0, ancho + 180, alto, fill="#181822", outline="#2e2e42")
    nivel = min(10, 1 + puntuacion // 1000)

    canvas.create_rectangle(ancho + 10, 10, ancho + 170, 55, fill="#222230", outline="#36364d")
    canvas.create_text(ancho + 90, 22, text="PUNTOS", fill="#a0a0c0", font=("Arial", 8, "bold"))
    canvas.create_text(ancho + 90, 40, text=str(puntuacion), fill="#ffd700", font=("Arial", 12, "bold"))

    canvas.create_rectangle(ancho + 10, 65, ancho + 170, 110, fill="#222230", outline="#36364d")
    canvas.create_text(ancho + 90, 77, text="RÉCORD", fill="#a0a0c0", font=("Arial", 8, "bold"))
    canvas.create_text(ancho + 90, 95, text=str(maximo_puntaje), fill="#ff9900", font=("Arial", 12, "bold"))

    canvas.create_rectangle(ancho + 10, 120, ancho + 170, 165, fill="#222230", outline="#36364d")
    canvas.create_text(ancho + 90, 132, text="NIVEL", fill="#a0a0c0", font=("Arial", 8, "bold"))
    canvas.create_text(ancho + 90, 150, text=f"{nivel} / 10", fill="#00e5ff", font=("Arial", 12, "bold"))

    canvas.create_rectangle(ancho + 10, 175, ancho + 170, 260, fill="#222230", outline="#36364d")
    canvas.create_text(ancho + 90, 187, text="SIGUIENTE", fill="#a0a0c0", font=("Arial", 8, "bold"))
    dibujar_miniatura(nombre_siguiente_pieza, ancho + 50, 205)

    canvas.create_rectangle(ancho + 10, 270, ancho + 170, 355, fill="#222230", outline="#36364d")
    canvas.create_text(ancho + 90, 282, text="GUARDADA", fill="#a0a0c0", font=("Arial", 8, "bold"))
    if nombre_pieza_guardada:
        dibujar_miniatura(nombre_pieza_guardada, ancho + 50, 300)
    else:
        canvas.create_text(ancho + 90, 315, text="[ C ]", fill="#666680", font=("Arial", 10))

    canvas.create_rectangle(ancho + 10, 365, ancho + 170, 585, fill="#222230", outline="#36364d")
    canvas.create_text(ancho + 90, 380, text="CONTROLES", fill="#a0a0c0", font=("Arial", 8, "bold"))
    controles = [("<- / ->", "Mover"), ("Up", "Rotar"), ("Down", "Caer"), ("C", "Guardar"), ("R", "Reiniciar")]
    y_ctrl = 405
    for tecla, accion in controles:
        canvas.create_text(ancho + 25, y_ctrl, text=tecla, fill="#00ffff", font=("Arial", 8, "bold"), anchor="w")
        canvas.create_text(ancho + 85, y_ctrl, text=accion, fill="#cccccc", font=("Arial", 8), anchor="w")
        y_ctrl += 35

def dibujar_game_over():
    canvas.create_rectangle(20, 180, ancho - 20, 420, fill="#1c1c28", outline="#ff4444" if not es_nuevo_record else "#ffd700", width=3)
    canvas.create_text(ancho // 2, 215, text="GAME OVER", fill="#ff4444", font=("Arial", 18, "bold"))
    if es_nuevo_record:
        canvas.create_text(ancho // 2, 250, text="!NUEVO RECORD!", fill="#ffd700", font=("Arial", 13, "bold"))
    canvas.create_text(ancho // 2, 290, text=f"Puntuacion: {puntuacion}", fill="white", font=("Arial", 12))
    canvas.create_text(ancho // 2, 325, text=f"Record Maximo: {maximo_puntaje}", fill="#00e5ff", font=("Arial", 11))
    canvas.create_text(ancho // 2, 375, text="Presiona [ R ] para reiniciar", fill="#aaaaaa", font=("Arial", 10))

def redibujar():
    canvas.delete("all")
    dibujar_tablero()
    dibujar_pieza()
    dibujar_panel()
    if juego_terminado:
        dibujar_game_over()

def guardar_pieza():
    global pieza_actual, colores_actual, pos_x, pos_y, nombre_pieza, nombre_siguiente_pieza, nombre_pieza_guardada, puede_guardar
    if not puede_guardar or juego_terminado:
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
    global tablero, puntuacion, nombre_pieza, nombre_siguiente_pieza, pieza_actual, colores_actual, pos_x, pos_y, nombre_pieza_guardada, puede_guardar, juego_terminado, es_nuevo_record
    tablero = [[0 for _ in range(COLUMNAS)] for _ in range(FILAS)]
    puntuacion = 0
    es_nuevo_record = False
    nombre_pieza = random.choice(list(PIEZAS.keys()))
    nombre_siguiente_pieza = random.choice(list(PIEZAS.keys()))
    pieza_actual = PIEZAS[nombre_pieza]
    colores_actual = COLORES[nombre_pieza]
    pos_x = COLUMNAS // 2 - 1
    pos_y = 0
    nombre_pieza_guardada = None
    puede_guardar = True
    if juego_terminado:
        juego_terminado = False
        redibujar()
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
    global pieza_actual, colores_actual, pos_x, pos_y, puede_guardar, nombre_pieza, nombre_siguiente_pieza, juego_terminado, maximo_puntaje, es_nuevo_record
    for f_idx,fila in enumerate(pieza_actual):
        for c_idx, valor in enumerate(fila):
            if valor:
                tablero[pos_y + f_idx] [pos_x + c_idx] = colores_actual
    limpiar_filas()

    puede_guardar = True
    nombre_pieza = nombre_siguiente_pieza
    nombre_siguiente_pieza = random.choice(list(PIEZAS.keys()))
    pieza_actual = PIEZAS[nombre_pieza]
    colores_actual = COLORES[nombre_pieza]
    pos_x = COLUMNAS // 2 - 1 
    pos_y = 0

    if not es_valido(pieza_actual, pos_x, pos_y):
        juego_terminado = True
        if puntuacion > maximo_puntaje:
            maximo_puntaje = puntuacion
            es_nuevo_record = True
            reproducir_sonido("record")
        else:
            es_nuevo_record = False
            reproducir_sonido("game_over")
        redibujar()
def limpiar_filas():
    global tablero, puntuacion
    nuevas_filas = [fila for fila in tablero if any(valor == 0 for valor in fila)]
    filas_eliminadas = FILAS - len(nuevas_filas)
    if filas_eliminadas > 0:
        filas_vacias = [[0 for _ in range(COLUMNAS)] for _ in range(filas_eliminadas)]
        tablero = filas_vacias + nuevas_filas
        puntuacion += filas_eliminadas * 100
        reproducir_sonido("limpiar")

def bajar_rapido():
    global pos_y
    if es_valido(pieza_actual, pos_x, pos_y + 1):
        pos_y += 1
        redibujar()

redibujar()
caer()
root.mainloop()











