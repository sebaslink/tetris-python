from flask import Flask, jsonify, request, send_from_directory
import time
import os

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
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tetris Online</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Outfit', sans-serif; user-select: none; }
        body { background: #0c0c12; color: #ffffff; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 15px; }
        header { text-align: center; margin-bottom: 15px; }
        h1 { font-size: 2rem; font-weight: 800; background: linear-gradient(135deg, #00e5ff, #ff007f); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-transform: uppercase; letter-spacing: 2px; }
        p.subtitle { color: #8a8aa3; font-size: 0.9rem; margin-top: 4px; }
        
        .main-container { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; align-items: flex-start; max-width: 900px; width: 100%; }
        
        .game-card { background: rgba(22, 22, 34, 0.85); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); display: flex; gap: 15px; position: relative; }
        
        .canvas-container { position: relative; border-radius: 8px; overflow: hidden; border: 2px solid #2a2a3e; background: #09090e; }
        canvas#tetris { display: block; }
        
        .side-panel { display: flex; flex-direction: column; gap: 12px; min-width: 140px; }
        .stat-box { background: rgba(14, 14, 22, 0.9); border: 1px solid rgba(0, 229, 255, 0.2); border-radius: 10px; padding: 10px; text-align: center; }
        .stat-label { font-size: 0.75rem; color: #8a8aa3; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
        .stat-value { font-size: 1.3rem; font-weight: 800; color: #ffd700; margin-top: 2px; }
        
        .mini-canvas { display: block; margin: 6px auto 0 auto; background: transparent; }
        
        .leaderboard-card { background: rgba(22, 22, 34, 0.85); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 16px; width: 280px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .leaderboard-title { font-size: 1.1rem; font-weight: 700; color: #00e5ff; display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px; }
        .score-list { list-style: none; display: flex; flex-direction: column; gap: 8px; max-height: 380px; overflow-y: auto; }
        .score-item { display: flex; justify-content: space-between; align-items: center; background: rgba(10, 10, 16, 0.6); padding: 8px 12px; border-radius: 8px; border-left: 3px solid #ff007f; font-size: 0.85rem; }
        .score-item:nth-child(1) { border-left-color: #ffd700; background: rgba(255, 215, 0, 0.1); }
        .score-item:nth-child(2) { border-left-color: #c0c0c0; }
        .score-item:nth-child(3) { border-left-color: #cd7f32; }
        .player-name { font-weight: 600; color: #ffffff; }
        .player-score { font-weight: 800; color: #00e5ff; }

        .touch-controls { display: none; width: 100%; max-width: 400px; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 15px; }
        .btn-touch { background: #1c1c2b; border: 1px solid #33334d; color: #fff; padding: 14px; border-radius: 12px; font-size: 1.2rem; font-weight: bold; text-align: center; cursor: pointer; }
        .btn-touch:active { background: #00e5ff; color: #000; }

        .overlay { position: absolute; inset: 0; background: rgba(9, 9, 14, 0.88); backdrop-filter: blur(6px); display: flex; flex-direction: column; align-items: center; justify-content: center; border-radius: 14px; padding: 20px; text-align: center; }
        .overlay h2 { font-size: 1.8rem; color: #ff007f; margin-bottom: 8px; font-weight: 800; }
        .overlay p { font-size: 0.9rem; color: #cccccc; margin-bottom: 15px; }
        .name-input { background: #12121c; border: 1px solid #00e5ff; color: #fff; padding: 10px 14px; border-radius: 8px; outline: none; font-size: 1rem; width: 80%; text-align: center; margin-bottom: 12px; }
        .btn-action { background: linear-gradient(135deg, #00e5ff, #0088ff); color: #000; font-weight: 800; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 0.95rem; text-transform: uppercase; transition: transform 0.1s; }
        .btn-action:hover { transform: scale(1.05); }

        @media (max-width: 600px) {
            .touch-controls { display: grid; }
            .leaderboard-card { width: 100%; }
        }
    </style>
</head>
<body>
    <header>
        <h1>🎮 Tetris Online</h1>
        <p class="subtitle">Servidor activo en Render — Sincronizado en tiempo real</p>
        <div style="margin-top: 10px;">
            <a href="/download" style="background: linear-gradient(135deg, #00ff88, #00b359); color: #000; font-weight: 800; padding: 10px 20px; border-radius: 10px; text-decoration: none; display: inline-block; font-size: 0.95rem; box-shadow: 0 4px 15px rgba(0,255,136,0.3); transition: transform 0.2s;">📥 DESCARGAR APLICACIÓN DE ESCRITORIO (.EXE)</a>
        </div>
    </header>

    <div class="main-container">
        <div class="game-card">
            <div class="canvas-container">
                <canvas id="tetris" width="240" height="480"></canvas>
                <div id="game-overlay" class="overlay">
                    <h2 id="overlay-title">⚡ TETRIS ⚡</h2>
                    <p id="overlay-desc">Presiona el botón para iniciar</p>
                    <input type="text" id="player-input" class="name-input" placeholder="Tu Nombre" maxlength="12" value="Jugador Web" style="display:none;">
                    <button id="overlay-btn" class="btn-action">JUGAR AHORA</button>
                </div>
            </div>

            <div class="side-panel">
                <div class="stat-box">
                    <div class="stat-label">Puntos</div>
                    <div id="score" class="stat-value">0</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Líneas</div>
                    <div id="lines" class="stat-value">0</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Nivel</div>
                    <div id="level" class="stat-value">1</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Siguiente</div>
                    <canvas id="next" class="mini-canvas" width="80" height="80"></canvas>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Guardada [C]</div>
                    <canvas id="hold" class="mini-canvas" width="80" height="80"></canvas>
                </div>
            </div>
        </div>

        <div class="leaderboard-card">
            <div class="leaderboard-title">
                🏆 Top Récords Globales
                <span style="font-size:0.75rem; color:#8a8aa3; cursor:pointer;" onclick="fetchLeaderboard()">🔄</span>
            </div>
            <ul id="leaderboard-list" class="score-list">
                <li class="score-item"><span class="player-name">Cargando...</span></li>
            </ul>
        </div>

        <div class="touch-controls">
            <div class="btn-touch" onclick="handleTouch('hold')">📦 HOLD</div>
            <div class="btn-touch" onclick="handleTouch('rotate')">🔄 ROTAR</div>
            <div class="btn-touch" onclick="handleTouch('drop')">⚡ CAÍDA</div>
            <div class="btn-touch" onclick="handleTouch('left')">⬅️ IZQ</div>
            <div class="btn-touch" onclick="handleTouch('down')">⬇️ BAJAR</div>
            <div class="btn-touch" onclick="handleTouch('right')">➡️ DER</div>
        </div>
    </div>

    <script>
        const canvas = document.getElementById('tetris');
        const ctx = canvas.getContext('2d');
        const nextCanvas = document.getElementById('next');
        const nextCtx = nextCanvas.getContext('2d');
        const holdCanvas = document.getElementById('hold');
        const holdCtx = holdCanvas.getContext('2d');

        const COLS = 10, ROWS = 20, BLOCK = 24;

        const SHAPES = {
            'I': [[1,1,1,1]],
            'O': [[1,1],[1,1]],
            'T': [[0,1,0],[1,1,1]],
            'S': [[0,1,1],[1,1,0]],
            'Z': [[1,1,0],[0,1,1]],
            'J': [[1,0,0],[1,1,1]],
            'L': [[0,0,1],[1,1,1]]
        };

        const COLORS = {
            'I': '#00e5ff',
            'O': '#ffd700',
            'T': '#a000ff',
            'S': '#00ff88',
            'Z': '#ff0055',
            'J': '#0066ff',
            'L': '#ff8800'
        };

        let board = Array.from({length: ROWS}, () => Array(COLS).fill(0));
        let score = 0, lines = 0, level = 1;
        let piece = null, nextPiece = null, holdPiece = null, canHold = true;
        let posX = 0, posY = 0;
        let gameLoop = null, isPaused = false, isGameOver = false, isPlaying = false;

        function getRandomPieceKey() {
            const keys = Object.keys(SHAPES);
            return keys[Math.floor(Math.random() * keys.length)];
        }

        function createPiece(key) {
            return { key, shape: SHAPES[key], color: COLORS[key] };
        }

        function resetGame() {
            board = Array.from({length: ROWS}, () => Array(COLS).fill(0));
            score = 0; lines = 0; level = 1;
            holdPiece = null; canHold = true;
            isGameOver = false; isPaused = false;
            updateStats();
            nextPiece = createPiece(getRandomPieceKey());
            spawnPiece();
            isPlaying = true;
            hideOverlay();
            if (gameLoop) clearInterval(gameLoop);
            gameLoop = setInterval(drop, getSpeed());
        }

        function getSpeed() {
            return Math.max(80, 500 - (level - 1) * 45);
        }

        function spawnPiece() {
            piece = nextPiece;
            nextPiece = createPiece(getRandomPieceKey());
            posX = Math.floor(COLS / 2) - Math.floor(piece.shape[0].length / 2);
            posY = 0;
            canHold = true;
            drawNext();
            drawHold();

            if (!isValid(piece.shape, posX, posY)) {
                gameOver();
            }
        }

        function isValid(shape, px, py) {
            for (let r = 0; r < shape.length; r++) {
                for (let c = 0; c < shape[r].length; c++) {
                    if (shape[r][c]) {
                        let nx = px + c;
                        let ny = py + r;
                        if (nx < 0 || nx >= COLS || ny >= ROWS) return false;
                        if (ny >= 0 && board[ny][nx]) return false;
                    }
                }
            }
            return true;
        }

        function rotate(shape) {
            return shape[0].map((_, i) => shape.map(row => row[i]).reverse());
        }

        function tryRotate() {
            if (!isPlaying || isPaused || isGameOver) return;
            const newShape = rotate(piece.shape);
            if (isValid(newShape, posX, posY)) {
                piece.shape = newShape;
            } else if (isValid(newShape, posX - 1, posY)) {
                piece.shape = newShape; posX--;
            } else if (isValid(newShape, posX + 1, posY)) {
                piece.shape = newShape; posX++;
            }
            draw();
        }

        function move(dx) {
            if (!isPlaying || isPaused || isGameOver) return;
            if (isValid(piece.shape, posX + dx, posY)) {
                posX += dx;
                draw();
            }
        }

        function drop() {
            if (!isPlaying || isPaused || isGameOver) return;
            if (isValid(piece.shape, posX, posY + 1)) {
                posY++;
            } else {
                lockPiece();
            }
            draw();
        }

        function hardDrop() {
            if (!isPlaying || isPaused || isGameOver) return;
            while (isValid(piece.shape, posX, posY + 1)) {
                posY++;
                score += 2;
            }
            lockPiece();
            draw();
        }

        function hold() {
            if (!isPlaying || isPaused || isGameOver || !canHold) return;
            if (!holdPiece) {
                holdPiece = createPiece(piece.key);
                nextPiece = createPiece(getRandomPieceKey());
                spawnPiece();
            } else {
                const temp = holdPiece.key;
                holdPiece = createPiece(piece.key);
                piece = createPiece(temp);
                posX = Math.floor(COLS / 2) - Math.floor(piece.shape[0].length / 2);
                posY = 0;
            }
            canHold = false;
            drawHold();
            draw();
        }

        function lockPiece() {
            for (let r = 0; r < piece.shape.length; r++) {
                for (let c = 0; c < piece.shape[r].length; c++) {
                    if (piece.shape[r][c]) {
                        board[posY + r][posX + c] = piece.color;
                    }
                }
            }
            clearLines();
            spawnPiece();
        }

        function clearLines() {
            let cleared = 0;
            for (let r = ROWS - 1; r >= 0; r--) {
                if (board[r].every(val => val !== 0)) {
                    board.splice(r, 1);
                    board.unshift(Array(COLS).fill(0));
                    cleared++;
                    r++;
                }
            }
            if (cleared > 0) {
                lines += cleared;
                const pts = [0, 100, 300, 500, 800];
                score += pts[cleared] * level;
                level = Math.floor(lines / 10) + 1;
                updateStats();
                if (gameLoop) {
                    clearInterval(gameLoop);
                    gameLoop = setInterval(drop, getSpeed());
                }
            }
        }

        function updateStats() {
            document.getElementById('score').innerText = score;
            document.getElementById('lines').innerText = lines;
            document.getElementById('level').innerText = level;
        }

        function drawBlock(cCtx, x, y, color, size = BLOCK) {
            cCtx.fillStyle = color;
            cCtx.fillRect(x * size, y * size, size, size);
            cCtx.strokeStyle = 'rgba(255,255,255,0.2)';
            cCtx.strokeRect(x * size, y * size, size, size);
        }

        function draw() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            for (let r = 0; r < ROWS; r++) {
                for (let c = 0; c < COLS; c++) {
                    if (board[r][c]) {
                        drawBlock(ctx, c, r, board[r][c]);
                    } else {
                        ctx.strokeStyle = '#141420';
                        ctx.strokeRect(c * BLOCK, r * BLOCK, BLOCK, BLOCK);
                    }
                }
            }

            if (piece) {
                let shadowY = posY;
                while (isValid(piece.shape, posX, shadowY + 1)) shadowY++;
                if (shadowY !== posY) {
                    for (let r = 0; r < piece.shape.length; r++) {
                        for (let c = 0; c < piece.shape[r].length; c++) {
                            if (piece.shape[r][c]) {
                                ctx.strokeStyle = piece.color;
                                ctx.strokeRect((posX + c) * BLOCK, (shadowY + r) * BLOCK, BLOCK, BLOCK);
                            }
                        }
                    }
                }

                for (let r = 0; r < piece.shape.length; r++) {
                    for (let c = 0; c < piece.shape[r].length; c++) {
                        if (piece.shape[r][c]) {
                            drawBlock(ctx, posX + c, posY + r, piece.color);
                        }
                    }
                }
            }
        }

        function drawMini(cCtx, pPiece, cCanvas) {
            cCtx.clearRect(0, 0, cCanvas.width, cCanvas.height);
            if (!pPiece) return;
            const bSize = 16;
            const offX = Math.floor((cCanvas.width - pPiece.shape[0].length * bSize) / 2);
            const offY = Math.floor((cCanvas.height - pPiece.shape.length * bSize) / 2);
            for (let r = 0; r < pPiece.shape.length; r++) {
                for (let c = 0; c < pPiece.shape[r].length; c++) {
                    if (pPiece.shape[r][c]) {
                        cCtx.fillStyle = pPiece.color;
                        cCtx.fillRect(offX + c * bSize, offY + r * bSize, bSize, bSize);
                        cCtx.strokeStyle = 'rgba(255,255,255,0.3)';
                        cCtx.strokeRect(offX + c * bSize, offY + r * bSize, bSize, bSize);
                    }
                }
            }
        }

        function drawNext() { drawMini(nextCtx, nextPiece, nextCanvas); }
        function drawHold() { drawMini(holdCtx, holdPiece, holdCanvas); }

        function gameOver() {
            isGameOver = true;
            isPlaying = false;
            if (gameLoop) clearInterval(gameLoop);
            
            document.getElementById('overlay-title').innerText = '🎮 GAME OVER';
            document.getElementById('overlay-desc').innerText = `Puntuación obtenida: ${score}`;
            document.getElementById('player-input').style.display = 'block';
            document.getElementById('overlay-btn').innerText = 'GUARDAR RÉCORD';
            showOverlay();
        }

        function showOverlay() {
            document.getElementById('game-overlay').style.display = 'flex';
        }

        function hideOverlay() {
            document.getElementById('game-overlay').style.display = 'none';
        }

        document.getElementById('overlay-btn').addEventListener('click', () => {
            if (isGameOver) {
                const name = document.getElementById('player-input').value.trim() || 'Jugador Web';
                saveScore(name, score);
            } else {
                resetGame();
            }
        });

        function saveScore(jugador, puntuacion) {
            if (puntuacion <= 0) {
                resetGame();
                return;
            }
            fetch('/api/scores', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jugador, puntuacion })
            })
            .then(res => res.json())
            .then(() => {
                fetchLeaderboard();
                document.getElementById('player-input').style.display = 'none';
                resetGame();
            })
            .catch(() => resetGame());
        }

        function fetchLeaderboard() {
            fetch('/api/scores')
                .then(res => res.json())
                .then(data => {
                    const list = document.getElementById('leaderboard-list');
                    list.innerHTML = '';
                    if (data.scores && data.scores.length > 0) {
                        data.scores.forEach(s => {
                            const li = document.createElement('li');
                            li.className = 'score-item';
                            li.innerHTML = `<span class="player-name">${s.jugador}</span><span class="player-score">${s.puntuacion} pts</span>`;
                            list.appendChild(li);
                        });
                    } else {
                        list.innerHTML = '<li class="score-item"><span class="player-name">Sin récords aún</span></li>';
                    }
                })
                .catch(() => {});
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') move(-1);
            else if (e.key === 'ArrowRight') move(1);
            else if (e.key === 'ArrowUp') tryRotate();
            else if (e.key === 'ArrowDown') drop();
            else if (e.code === 'Space') hardDrop();
            else if (e.key === 'c' || e.key === 'C') hold();
            else if (e.key === 'p' || e.key === 'P' || e.key === 'Escape') {
                if (isPlaying) {
                    isPaused = !isPaused;
                    if (isPaused) {
                        document.getElementById('overlay-title').innerText = '⏸️ PAUSA';
                        document.getElementById('overlay-desc').innerText = 'Presiona P para continuar';
                        document.getElementById('overlay-btn').innerText = 'REANUDAR';
                        document.getElementById('player-input').style.display = 'none';
                        showOverlay();
                    } else {
                        hideOverlay();
                    }
                }
            }
        });

        function handleTouch(action) {
            if (action === 'left') move(-1);
            if (action === 'right') move(1);
            if (action === 'rotate') tryRotate();
            if (action === 'down') drop();
            if (action === 'drop') hardDrop();
            if (action === 'hold') hold();
        }

        fetchLeaderboard();
        draw();
    </script>
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

"""
API para Gestion de Salas Online
"""
@app.route("/api/salas/crear", methods=["POST"])
def crear_sala_api():
    data = request.get_json() or {}
    codigo = str(data.get("codigo", ""))
    if codigo:
        salas[codigo] = {
            "codigo": codigo,
            "estado": "ESPERANDO",
            "p1_tablero": [[0]*10 for _ in range(20)],
            "p1_puntuacion": 0,
            "p1_basura": 0,
            "p1_terminado": False,
            "p2_tablero": [[0]*10 for _ in range(20)],
            "p2_puntuacion": 0,
            "p2_basura": 0,
            "p2_terminado": False
        }
        return jsonify({"status": "created", "codigo": codigo})
    return jsonify({"status": "error"}), 400

@app.route("/api/salas/unirse", methods=["POST"])
def unirse_sala_api():
    data = request.get_json() or {}
    codigo = str(data.get("codigo", ""))
    if codigo in salas:
        salas[codigo]["estado"] = "JUGANDO"
        return jsonify({"status": "joined", "codigo": codigo})
    return jsonify({"status": "not_found"}), 404

@app.route("/api/salas/<codigo>", methods=["GET"])
def obtener_sala_api(codigo):
    if codigo in salas:
        return jsonify({"status": "ok", "sala": salas[codigo]})
    return jsonify({"status": "not_found"}), 404

@app.route("/api/salas/actualizar", methods=["POST"])
def actualizar_sala_api():
    data = request.get_json() or {}
    codigo = str(data.get("codigo", ""))
    rol = data.get("rol", "p1")
    if codigo in salas:
        s = salas[codigo]
        if rol == "p1":
            if "tablero" in data: s["p1_tablero"] = data["tablero"]
            if "puntuacion" in data: s["p1_puntuacion"] = data["puntuacion"]
            if "basura" in data: s["p2_basura"] += data["basura"]
            if "terminado" in data: s["p1_terminado"] = data["terminado"]
            res = {"tablero_rival": s["p2_tablero"], "puntuacion_rival": s["p2_puntuacion"], "basura": s["p1_basura"], "estado": s["estado"]}
            s["p1_basura"] = 0
        else:
            if "tablero" in data: s["p2_tablero"] = data["tablero"]
            if "puntuacion" in data: s["p2_puntuacion"] = data["puntuacion"]
            if "basura" in data: s["p1_basura"] += data["basura"]
            if "terminado" in data: s["p2_terminado"] = data["terminado"]
            res = {"tablero_rival": s["p1_tablero"], "puntuacion_rival": s["p1_puntuacion"], "basura": s["p2_basura"], "estado": s["estado"]}
            s["p2_basura"] = 0
        return jsonify({"status": "ok", "datos": res})
    return jsonify({"status": "not_found"}), 404

@app.route("/download", methods=["GET"])
def download_game():
    dist_dir = os.path.join(app.root_path, "dist")
    return send_from_directory(dist_dir, "Tetris-Online-Setup.zip", as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
