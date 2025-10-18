from flask import Flask, render_template, Response, jsonify, request, send_from_directory, redirect, url_for, flash
import cv2
import csv
import os
from datetime import datetime, time
import pandas as pd

app = Flask(__name__)
# Se agrega una clave secreta para poder usar mensajes flash (alertas)
app.secret_key = 'tu_clave_secreta_aqui'

CSV_FILE = "registro.csv"
REGISTROS_FOLDER = "registros"
EMPLEADO_ID = "Empleado1" # ID de empleado para pruebas

# Crear CSV si no existe
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["empleado_id", "fecha", "hora_entrada", "hora_salida", "horas_trabajadas"])

# Crear carpeta de registros si no existe
if not os.path.exists(REGISTROS_FOLDER):
    os.makedirs(REGISTROS_FOLDER)

# Usuario y contraseña de prueba
USUARIOS = {"admin": "1234"}

# ------------------ LOGIN ------------------
@app.route("/", methods=["GET", "POST"])
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
        fecha_seleccionada_str = request.form["fecha"]
        fecha_seleccionada = datetime.strptime(fecha_seleccionada_str, "%Y-%m-%d").date()
        fecha_actual = datetime.now().date()

        if fecha_seleccionada == fecha_actual:
            # Si es el día actual, va al registro de asistencia
            return redirect(url_for("asistencia", fecha=fecha_seleccionada_str))
        else:
            # Si es un día anterior, va a los registros de empleados filtrando por esa fecha
            return redirect(url_for("registros", fecha=fecha_seleccionada_str))
            
    return render_template("fecha.html")

# ------------------ STREAM DE CÁMARA ------------------
def gen_frames():
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        print("Error: No se puede abrir la cámara")
        return

    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# ------------------ PÁGINA DE REGISTRO DE ASISTENCIA ------------------
@app.route('/asistencia')
def asistencia():
    fecha = request.args.get("fecha", datetime.now().date().isoformat())
    return render_template('index.html', fecha=fecha)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ------------------ REGISTRAR ENTRADA/SALIDA (LÓGICA) ------------------
def registrar_evento(fecha_registro):
    ahora = datetime.now()
    hora_actual = ahora.strftime("%H:%M:%S")

    filas = []
    encontrado = False
    tipo = "entrada"

    # Leer el CSV actual para modificarlo
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        with open(CSV_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Busca un registro de entrada sin salida para el mismo empleado en la misma fecha
                if row["empleado_id"] == EMPLEADO_ID and row["fecha"] == fecha_registro and not row["hora_salida"]:
                    row["hora_salida"] = hora_actual
                    try:
                        h_entrada = datetime.strptime(row["hora_entrada"], "%H:%M:%S")
                        h_salida = datetime.strptime(hora_actual, "%H:%M:%S")
                        row["horas_trabajadas"] = str(h_salida - h_entrada)
                    except ValueError:
                        row["horas_trabajadas"] = "Error de cálculo"
                    encontrado = True
                    tipo = "salida"
                filas.append(row)

    # Si no se encontró un registro de entrada previo, se crea uno nuevo
    if not encontrado:
        filas.append({
            "empleado_id": EMPLEADO_ID,
            "fecha": fecha_registro,
            "hora_entrada": hora_actual,
            "hora_salida": "",
            "horas_trabajadas": ""
        })

    # Escribir todos los datos de nuevo en el CSV
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["empleado_id", "fecha", "hora_entrada", "hora_salida", "horas_trabajadas"])
        writer.writeheader()
        writer.writerows(filas)

    return tipo

@app.route('/registrar', methods=["POST"])
def registrar():
    fecha_str = request.args.get('fecha', datetime.now().date().isoformat())
    tipo = registrar_evento(fecha_str)
    return jsonify({"status": "ok", "tipo": tipo})

# ------------------ GUARDAR REGISTROS DEL DÍA EN EXCEL ------------------
@app.route('/guardar_registros_dia', methods=["POST"])
def guardar_registros_dia():
    fecha_hoy_str = datetime.now().date().isoformat()
    
    if not os.path.exists(CSV_FILE):
        return jsonify({"status": "error", "msg": "No hay un archivo de registros (CSV) para procesar."})

    df = pd.read_csv(CSV_FILE)
    
    # Filtrar los registros que corresponden solo al día de hoy
    df_hoy = df[df['fecha'] == fecha_hoy_str]

    if df_hoy.empty:
        return jsonify({"status": "error", "msg": "No hay registros de asistencia para el día de hoy."})

    # Crear el nombre del archivo Excel
    archivo_excel = f"Registro de Asistencia ({fecha_hoy_str}).xlsx"
    ruta_excel = os.path.join(REGISTROS_FOLDER, archivo_excel)
    
    # Usar XlsxWriter como motor para poder aplicar estilos
    writer = pd.ExcelWriter(ruta_excel, engine='xlsxwriter')
    df_hoy.to_excel(writer, index=False, sheet_name='Registros')
    
    workbook = writer.book
    worksheet = writer.sheets['Registros']

    # Definir formatos de estilo
    header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#5468ff', 'font_color': 'white', 'border': 1})
    cell_format_par = workbook.add_format({'bg_color': '#F5F6FA', 'border': 1})
    cell_format_impar = workbook.add_format({'bg_color': '#FFFFFF', 'border': 1})
    
    # Aplicar formato a las celdas de la cabecera
    for col_num, value in enumerate(df_hoy.columns.values):
        worksheet.write(0, col_num, value, header_format)
        # Ajustar ancho de columna
        column_len = max(df_hoy[value].astype(str).map(len).max(), len(value)) + 2
        worksheet.set_column(col_num, col_num, column_len)

    # Aplicar formato a las filas de datos con colores alternados (solo columnas existentes)
    ncols = len(df_hoy.columns)
    for row_num in range(len(df_hoy)):
        fmt = cell_format_par if (row_num + 1) % 2 == 0 else cell_format_impar
        for col_num in range(ncols):
            value = df_hoy.iat[row_num, col_num]
            worksheet.write(row_num + 1, col_num, value, fmt)
# ...existing code...

    writer.close()

    return jsonify({"status": "ok", "msg": f"Registro del día guardado como '{archivo_excel}'."})

# ------------------ PÁGINA DE REGISTROS DE EMPLEADOS ------------------
@app.route('/registros')
def registros():
    # Obtener la fecha del filtro, si existe
    fecha_filtro = request.args.get('fecha')
    
    archivos = sorted(os.listdir(REGISTROS_FOLDER), reverse=True)
    
    # Si hay una fecha para filtrar, se muestran solo los archivos que coincidan
    if fecha_filtro:
        archivos = [a for a in archivos if fecha_filtro in a]

    return render_template('registros.html', archivos=archivos, fecha_filtro=fecha_filtro)

@app.route('/registros/<archivo>')
def descargar_archivo(archivo):
    return send_from_directory(REGISTROS_FOLDER, archivo, as_attachment=True)

# ------------------ LOGOUT ------------------
@app.route('/logout')
def logout():
    # Aquí podrías manejar la lógica de sesión si la tuvieras
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)

