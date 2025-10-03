from flask import Flask, render_template, Response, redirect, url_for, request
import cv2
import csv
import os
from datetime import datetime, time

app = Flask(__name__)

# Archivo CSV
CSV_FILE = "registro.csv"

# ID fijo por ahora (luego lo cambiaremos con reconocimiento real)
EMPLEADO_ID = "Empleado1"

# Variable global para congelar cámara
last_frame = None       #  guardara el último frame válido
freeze_camera = False   #  bandera para indicar si la cámara debe congelarse

# inicializamos el archivo CSV si no existe
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["empleado_id", "fecha", "hora_entrada", "hora_salida", "horas_trabajadas"])

# ------------------ logica del registro ------------------

def registrar_evento():
    ahora = datetime.now()
    fecha = ahora.date().isoformat()
    hora_actual = ahora.strftime("%H:%M:%S")

    filas = []
    encontrado = False

    # Leer el CSV
    with open(CSV_FILE, mode="r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # si el empleado ya tiene entrada sin salida, marcar salida
            if row["empleado_id"] == EMPLEADO_ID and row["fecha"] == fecha and row["hora_salida"] == "":
                row["hora_salida"] = hora_actual
                # calcular horas trabajadas
                h_entrada = datetime.strptime(row["hora_entrada"], "%H:%M:%S")
                h_salida = datetime.strptime(hora_actual, "%H:%M:%S")
                row["horas_trabajadas"] = str(h_salida - h_entrada)
                encontrado = True
            filas.append(row)

    # si no había registro de entrada, creamos uno nuevo
    if not encontrado:
        filas.append({
            "empleado_id": EMPLEADO_ID,
            "fecha": fecha,
            "hora_entrada": hora_actual,
            "hora_salida": "",
            "horas_trabajadas": ""
        })

    # Reescribir CSV
    with open(CSV_FILE, mode="w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["empleado_id", "fecha", "hora_entrada", "hora_salida", "horas_trabajadas"])
        writer.writeheader()
        writer.writerows(filas)

# ------------------ camara ------------------

def gen_frames():
    global last_frame, freeze_camera
    camera = cv2.VideoCapture(0)

    while True:
        if freeze_camera and last_frame is not None:
            #  mientras esté congelada, mostrar la última imagen
            frame = last_frame
        else:
            success, frame = camera.read()
            if not success:
                break
            # guardamos el último frame válido
            last_frame = frame  

        # convertimos frame en jpg
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

from flask import jsonify

@app.route('/registrar', methods=["POST"])
def registrar():
    global freeze_camera, last_frame
    freeze_camera = True   #  congelamos
    registrar_evento()
    freeze_camera = False  #  liberamos casi inmediato
    return jsonify({"status": "ok"})


# ------------------ verificación de salida automática ------------------

@app.before_request
def verificar_salidas():
    ahora = datetime.now()
    hora_limite = time(20, 0)  # 8:00 PM
    fecha = ahora.date().isoformat()

    filas = []
    cambios = False

    with open(CSV_FILE, mode="r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["fecha"] == fecha and row["hora_salida"] == "" and ahora.time() >= hora_limite:
                row["hora_salida"] = "NO MARCÓ SALIDA"
                row["horas_trabajadas"] = ""
                cambios = True
            filas.append(row)

    if cambios:
        with open(CSV_FILE, mode="w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["empleado_id", "fecha", "hora_entrada", "hora_salida", "horas_trabajadas"])
            writer.writeheader()
            writer.writerows(filas)

if __name__ == "__main__":
    app.run(debug=True)
