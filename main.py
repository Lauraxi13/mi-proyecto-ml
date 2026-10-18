import os, csv, requests
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Configuración del endpoint de Databricks -------------------------
DATABRICKS_URL = os.environ.get("DATABRICKS_URL", "")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN", "")

if not DATABRICKS_URL or not DATABRICKS_TOKEN:
    raise RuntimeError("Variables DATABRICKS_URL o DATABRICKS_TOKEN no configuradas")

LOG_FILE = "predicciones.csv"

# --- Función auxiliar para contar registros ---------------------------
def _contar_logs():
    """Cuenta cuántas predicciones se han guardado en el archivo CSV."""
    if not os.path.exists(LOG_FILE):
        return 0
    with open(LOG_FILE, mode="r", encoding="utf-8") as f:
        # Restamos 1 para no contar la fila de los encabezados
        return sum(1 for linea in f) - 1

# --- FastAPI ----------------------------------------------------------
app = FastAPI(title="API Predicción Estudiantes", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Schema de entrada ------------------------------------------------
class Estudiante(BaseModel):
    horas_estudio:      float  
    horas_sueno:        float  
    asistencia:         float  
    promedio_previo:    float  
    indice_dedicacion:  float  
    en_riesgo:          int    
    destacado:          int    

# --- Endpoints --------------------------------------------------------
@app.get("/health")
def health():
    return {
        "status":               "ok",
        "version":              "3.0",
        "endpoint_databricks":  DATABRICKS_URL,
        "registros_guardados":  _contar_logs()
    }

@app.post("/predecir")
def predecir(est: Estudiante):
    # 1. Reformatear al formato que exige Databricks
    payload = {
        "dataframe_records": [
            {
                "horas_estudio":      est.horas_estudio,
                "horas_sueno":        est.horas_sueno,
                "asistencia":         est.asistencia,
                "promedio_previo":    est.promedio_previo,
                "indice_dedicacion":  est.indice_dedicacion,
                "en_riesgo":          est.en_riesgo,
                "destacado":          est.destacado,
            }
        ]
    }

    # 2. Configurar cabeceras
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json",
    }

    # 3. Llamar al endpoint de Databricks
    try:
        respuesta = requests.post(DATABRICKS_URL, headers=headers, json=payload)
        respuesta.raise_for_status() # Verifica si hubo error HTTP
        
        # Extraer el valor de la predicción
        datos = respuesta.json()
        prediccion = datos.get("predictions", [None])[0]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error conectando con Databricks: {str(e)}")

    # 4. Guardar un log de la predicción en el CSV
    archivo_existe = os.path.exists(LOG_FILE)
    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not archivo_existe:
            # Escribir encabezados si el archivo es nuevo
            writer.writerow(["fecha", "horas_estudio", "horas_sueno", "asistencia", "promedio_previo", 
                             "indice_dedicacion", "en_riesgo", "destacado", "prediccion"])
        
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                         est.horas_estudio, est.horas_sueno, est.asistencia, est.promedio_previo, 
                         est.indice_dedicacion, est.en_riesgo, est.destacado, prediccion])

    # 5. Devolver el resultado final
    return {
        "mensaje": "Predicción generada con éxito",
        "prediccion": prediccion
    }