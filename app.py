from flask import Flask, jsonify, request
import time

app = Flask(__name__)

# Base de datos en memoria para puntuaciones y salas online
puntuaciones = [
    {"jugador": "Zodiaco", "puntuacion": 2500, "fecha": "2026-08-13"},
    {"jugador": "Player 1", "puntuacion": 1800, "fecha": "2026-08-13"}
]
salas = {}

@app.route("/")
def home():
    return """
    <html>
    <head><title>Tetris Online API</title></head>
    <body style="font-family:sans-serif; background:#121218; color:#00e5ff; text-align:center; padding:40px;">
        <h1>🎮 Tetris Python Online Server</h1>
        <p style="color:#ffffff;">Servidor activo en Render para sincronización de puntuaciones y multijugador.</p>
        <hr style="border-color:#333;">
        <p><a href="/api/scores" style="color:#ffd700;">Ver Récords Globales (/api/scores)</a></p>
    </body>
    </html>
    """

@app.route("/api/scores", methods=["GET"])
def get_scores():
    sorted_scores = sorted(puntuaciones, key=lambda x: x["puntuacion"], reverse=True)[:10]
    return jsonify({"status": "ok", "scores": sorted_scores})

@app.route("/api/scores", methods=["POST"])
def add_score():
    data = request.get_json() or {}
    jugador = data.get("jugador", "Jugador")
    puntuacion = int(data.get("puntuacion", 0))
    if puntuacion > 0:
        puntuaciones.append({
            "jugador": jugador,
            "puntuacion": puntuacion,
            "fecha": time.strftime("%Y-%m-%d %H:%M")
        })
    return jsonify({"status": "success", "total": len(puntuaciones)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
