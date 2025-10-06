from flask import Flask, render_template, Response, jsonify
import cv2
import csv
import os
from datetime import datetime, time

app = Flask(__name__)

CSV_FILE = "registro.csv"
EMPLEADO_ID = "Empleado1"

# Crear CSV si no existe
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["empleado_id", "fecha", "hora_entrada", "hora_salida", "horas_trabajadas"])

def registrar_evento():
    """Registra entrada o salida según el último estado."""
    ahora = datetime.now()
    fecha = ahora.date().isoformat()
    hora_actual = ahora.strftime("%H:%M:%S")

    filas = []
    encontrado = False
    tipo = "entrada"

    # Leer registros actuales
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["empleado_id"] == EMPLEADO_ID and row["fecha"] == fecha and row["hora_salida"] == "":
                    # Registrar salida
                    row["hora_salida"] = hora_actual
                    try:
                        h_entrada = datetime.strptime(row["hora_entrada"], "%H:%M:%S")
                        h_salida = datetime.strptime(hora_actual, "%H:%M:%S")
                        row["horas_trabajadas"] = str(h_salida - h_entrada)
                    except:
                        row["horas_trabajadas"] = ""
                    encontrado = True
                    tipo = "salida"
                filas.append(row)

    # Si no había registro pendiente, crear nueva entrada
    if not encontrado:
        filas.append({
            "empleado_id": EMPLEADO_ID,
            "fecha": fecha,
            "hora_entrada": hora_actual,
            "hora_salida": "",
            "horas_trabajadas": ""
        })

    # Guardar cambios
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["empleado_id", "fecha", "hora_entrada", "hora_salida", "horas_trabajadas"])
        writer.writeheader()
        writer.writerows(filas)

    return tipo

# ------------------ STREAM DE CÁMARA ------------------
def gen_frames():
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        return

    while True:
        success, frame = camera.read()
        if not success:
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/registrar', methods=["POST"])
def registrar():
    tipo = registrar_evento()  # Solo se llama una vez
    return jsonify({"status": "ok", "tipo": tipo})

@app.before_request
def verificar_salidas():
    ahora = datetime.now()
    hora_limite = time(20, 0)
    fecha = ahora.date().isoformat()

    if not os.path.exists(CSV_FILE):
        return

    filas = []
    cambios = False
    with open(CSV_FILE, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["fecha"] == fecha and row["hora_salida"] == "" and ahora.time() >= hora_limite:
                row["hora_salida"] = "NO MARCÓ SALIDA"
                row["horas_trabajadas"] = ""
                cambios = True
            filas.append(row)

    if cambios:
        with open(CSV_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["empleado_id", "fecha", "hora_entrada", "hora_salida", "horas_trabajadas"])
            writer.writeheader()
            writer.writerows(filas)

if __name__ == "__main__":
    app.run(debug=True)
