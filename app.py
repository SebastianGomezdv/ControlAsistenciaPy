from flask import Flask, render_template, Response, jsonify, request, send_from_directory, redirect, url_for
import cv2
import csv
import os
from datetime import datetime, time
import pandas as pd

app = Flask(__name__)

CSV_FILE = "registro.csv"
REGISTROS_FOLDER = "registros"
EMPLEADO_ID = "Empleado1"

# Crear CSV si no existe
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["empleado_id", "fecha", "hora_entrada", "hora_salida", "horas_trabajadas"])

# Crear carpeta registros si no existe
if not os.path.exists(REGISTROS_FOLDER):
    os.makedirs(REGISTROS_FOLDER)

# Usuario y contraseña de prueba
USUARIOS = {"admin": "1234"}

# ------------------ LOGIN ------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]
        if usuario in USUARIOS and USUARIOS[usuario] == clave:
            return redirect(url_for("seleccionar_fecha"))
        else:
            error = "Usuario o contraseña incorrectos"
    return render_template("login.html", error=error)

# ------------------ SELECCIONAR FECHA ------------------
@app.route("/fecha", methods=["GET", "POST"])
def seleccionar_fecha():
    if request.method == "POST":
        fecha = request.form["fecha"]
        return redirect(url_for("index", fecha=fecha))
    return render_template("fecha.html")

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
    fecha = request.args.get("fecha", datetime.now().date().isoformat())
    return render_template('index.html', fecha=fecha)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ------------------ REGISTRAR ENTRADA/SALIDA ------------------
def registrar_evento():
    ahora = datetime.now()
    fecha = ahora.date().isoformat()
    hora_actual = ahora.strftime("%H:%M:%S")

    filas = []
    encontrado = False
    tipo = "entrada"

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

    if not encontrado:
        filas.append({
            "empleado_id": EMPLEADO_ID,
            "fecha": fecha,
            "hora_entrada": hora_actual,
            "hora_salida": "",
            "horas_trabajadas": ""
        })

    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["empleado_id", "fecha", "hora_entrada", "hora_salida", "horas_trabajadas"])
        writer.writeheader()
        writer.writerows(filas)

    return tipo

@app.route('/registrar', methods=["POST"])
def registrar():
    tipo = registrar_evento()
    return jsonify({"status": "ok", "tipo": tipo})

# ------------------ GUARDAR CSV A EXCEL ------------------
@app.route('/guardar_excel', methods=["POST"])
def guardar_excel():
    if not os.path.exists(CSV_FILE):
        return jsonify({"status": "error", "msg": "No hay registros para guardar"})

    df = pd.read_csv(CSV_FILE)
    fecha_hoy = datetime.now().date().isoformat()
    archivo_excel = f"Registro Empleados {fecha_hoy}.xlsx"
    ruta_excel = os.path.join(REGISTROS_FOLDER, archivo_excel)
    df.to_excel(ruta_excel, index=False)

    return jsonify({"status": "ok", "archivo": archivo_excel})

# ------------------ REGISTROS ------------------
@app.route('/registros')
def registros():
    archivos = sorted(os.listdir(REGISTROS_FOLDER), reverse=True)
    return render_template('registros.html', archivos=archivos)

@app.route('/registros/<archivo>')
def descargar_archivo(archivo):
    return send_from_directory(REGISTROS_FOLDER, archivo, as_attachment=True)

# ------------------ VERIFICAR SALIDAS AL FINAL DEL DÍA ------------------
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

# ------------------ LOGOUT ------------------
@app.route('/logout')
def logout():
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)
