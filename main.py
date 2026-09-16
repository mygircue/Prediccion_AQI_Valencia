"""
DISPOSITIVO AUTONOMO - PREDICCION AQI EN PICO W
FUNCIONAMIENTO 24/7 CON TOLERANCIA A FALLOS
Con sensor BME280 para temperatura, humedad y presion locales
GPS LC79D integrado como fuente primaria de ubicacion
GVA (3 estaciones mas cercanas) -> WAQI (3 mas cercanas) -> Open-Meteo
Calculo del ICA oficial espanol (RD 102/2011) para TODAS las fuentes

"""

from machine import I2C, Pin, UART
from lcd_api import LcdApi
from pico_i2c_lcd import I2cLcd
import network, urequests, time, gc, math, socket, ssl, ntptime
import ujson
import os
from modelo_polinomico import predecir_aqi
from bme280 import *

# ==================== VERIFICACION DEL MODELO ====================
try:
    test = predecir_aqi(10, 20, 50, 20, 20, 50, 3)
    print(f"Modelo cargado correctamente. Test AQI: {test:.1f}")
except Exception as e:
    print(f"Error cargando modelo: {e}")

# ==================== CONFIGURACION ====================
REDES_WIFI = [
    {"ssid": "vodafoneXXXXXX", "password": "XXXXXXXXXXXXXXX"},
    {"ssid": "myXXXXXXX", "password": "XXXXXXXXXX"},
]

LAT_DEFAULT, LON_DEFAULT = "39.4796", "-0.3374"
TOKEN_WAQI = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

PC_IP = "111.111.1.11"
PUERTO_PC = 5001
URL_SERVIDOR = f"http://{PC_IP}:{PUERTO_PC}/api/datos"
INTERVALO_ENVIO_SEGUNDOS = 1800
ultimo_envio = -INTERVALO_ENVIO_SEGUNDOS
ARCHIVO_BUFFER = "buffer_datos.csv"

# ============ ZONA HORARIA ============
OFFSET_TZ = 2  # Se actualiza al arrancar con obtener_offset_utc()
zona_horaria = "UTC"  # Se actualiza al arrancar

# ==================== PARAMETRO CONFIGURABLE ====================
DISTANCIA_MAX_KM = 65

ultimo_valido = {
    "pm25": 0, "pm10": 0, "no2": 0, "o3": 0,
    "temperatura": 0, "humedad": 0, "viento": 0, "aqi_real": 0
}

ultima_lat_valida = LAT_DEFAULT
ultima_lon_valida = LON_DEFAULT
ultima_ubicacion_valida = "Valencia"
ultima_region_valida = "C.Valenciana"
ultima_distancia_valida = 0

LAT_MIN, LAT_MAX = 37.8, 40.8
LON_MIN, LON_MAX = -0.8, 0.5

ESTACIONES_GVA = {
    "03014009": {"nombre": "Alacant-Rabassa",        "lat": 38.3677, "lon": -0.5142},
    "03014012": {"nombre": "Alacant_AP_ISM",          "lat": 38.3370, "lon": -0.4920},
    "03014013": {"nombre": "Alacant_AP_T_Frutero",    "lat": 38.3368, "lon": -0.4966},
    "03014014": {"nombre": "Alacant_AP_D_Pesquera",   "lat": 38.3312, "lon": -0.5052},
    "03066003": {"nombre": "Elda-Lacy",               "lat": 38.4454, "lon": -0.8061},
    "03133002": {"nombre": "Torrevieja",              "lat": 37.9931, "lon": -0.6906},
    "03140001": {"nombre": "Villena",                 "lat": 38.6395, "lon": -0.8725},
    "12009302": {"nombre": "Almassora_Platja",        "lat": 39.9440, "lon": -0.0029},
    "12032001": {"nombre": "Borriana",                "lat": 39.9077, "lon": -0.0661},
    "12032005": {"nombre": "Borriana-Residencia",     "lat": 39.8946, "lon": -0.0897},
    "12040008": {"nombre": "Castello-Penyeta",        "lat": 40.0129, "lon": -0.0581},
    "12040010": {"nombre": "Castello-Grau",           "lat": 39.9835, "lon": 0.0090},
    "12040020": {"nombre": "Castello-CEIP_Marina",    "lat": 39.9694, "lon": 0.0089},
    "12040301": {"nombre": "Castello_AP_Tramuntana",  "lat": 39.9750, "lon": 0.0164},
    "12040302": {"nombre": "Castello_AP_Gregal",      "lat": 39.9697, "lon": 0.0136},
    "12040303": {"nombre": "Castello_AP_Llevant",     "lat": 39.9667, "lon": 0.0089},
    "12040304": {"nombre": "Castello_AP_Ponent",      "lat": 39.9631, "lon": 0.0069},
    "12040305": {"nombre": "Castello_AP_Xaloc",       "lat": 39.9503, "lon": 0.0050},
    "12040306": {"nombre": "Castello_AP_Mestral",     "lat": 39.9774, "lon": 0.0251},
    "12140002": {"nombre": "Viver",                   "lat": 39.9264, "lon": -0.6032},
    "12141002": {"nombre": "Zorita",                  "lat": 40.7331, "lon": -0.1703},
    "46010001": {"nombre": "Albalat_Tarongers",       "lat": 39.7051, "lon": -0.3362},
    "46028001": {"nombre": "Algar_Palancia",          "lat": 39.7823, "lon": -0.3592},
    "46062001": {"nombre": "Beniganim",               "lat": 38.9375, "lon": -0.4416},
    "46077006": {"nombre": "Bunyol_CIMSA",            "lat": 39.4246, "lon": -0.7854},
    "46095001": {"nombre": "Caudete",                 "lat": 39.5600, "lon": -1.2827},
    "46102002": {"nombre": "Quart_Poblet",            "lat": 39.4814, "lon": -0.4466},
    "46220003": {"nombre": "Sagunt-Port",             "lat": 39.6650, "lon": -0.2312},
    "46220010": {"nombre": "Sagunt-CEA",              "lat": 39.6330, "lon": -0.2667},
    "46230001": {"nombre": "Silla",                   "lat": 39.3624, "lon": -0.3165},
    "46244003": {"nombre": "Torrent-El_Vedat",        "lat": 39.4254, "lon": -0.4824},
    "46250030": {"nombre": "Valencia-Pista_Silla",    "lat": 39.4581, "lon": -0.3767},
    "46250046": {"nombre": "Valencia-Politecnic",     "lat": 39.4796, "lon": -0.3374},
    "46250047": {"nombre": "Valencia-Av_Franca",      "lat": 39.4575, "lon": -0.3427},
    "46250048": {"nombre": "Valencia-Moli_Sol",       "lat": 39.4811, "lon": -0.4086},
    "46250054": {"nombre": "Valencia-Centre",         "lat": 39.4707, "lon": -0.3765},
    "46250055": {"nombre": "Valencia-Olivereta",      "lat": 39.4692, "lon": -0.4060},
    "46250301": {"nombre": "Valencia_Port_Moll_Ponent","lat": 39.4593, "lon": -0.3232},
    "46250302": {"nombre": "Valencia_Port_llit_Turia","lat": 39.4505, "lon": -0.3289},
    "46258001": {"nombre": "Villar_Arzobispo",        "lat": 39.7080, "lon": -0.8320},
}

ESTACIONES_WAQI = {
    "A58504": {"nombre": "Cl Pp Cds Kalmias", "lat": 38.7060, "lon": 0.1520},
    "A229000": {"nombre": "Cr Fuente San Luis", "lat": 39.4500, "lon": -0.3700},
    "A373816": {"nombre": "Placa Ajuntament", "lat": 39.4700, "lon": -0.3760},
    "A166009": {"nombre": "Avinguda Condomina", "lat": 38.3634, "lon": -0.4264},
    "6640": {"nombre": "Politècnic UPV", "lat": 39.4803, "lon": -0.3364},
    "6639": {"nombre": "Avd. Francia", "lat": 39.4575, "lon": -0.3428},
    "6637": {"nombre": "Pista de Silla", "lat": 39.4561, "lon": -0.3758},
    "6638": {"nombre": "Molí del Sol", "lat": 39.4811, "lon": -0.4083},
    "6644": {"nombre": "Quart de Poblet", "lat": 39.4811, "lon": -0.4472},
    "6645": {"nombre": "Sagunt-CEA", "lat": 39.6342, "lon": -0.2657},
    "6643": {"nombre": "Albalat Tarongers", "lat": 39.7053, "lon": -0.3367},
    "6646": {"nombre": "Villar del Arzobispo", "lat": 39.7081, "lon": -0.8319},
    "6642": {"nombre": "Caudete de las Fuentes", "lat": 39.5586, "lon": -1.2814},
    "6641": {"nombre": "Buñol", "lat": 39.4272, "lon": -0.7839},
    "8387": {"nombre": "Penyeta Castelló", "lat": 40.0128, "lon": -0.0572},
    "8386": {"nombre": "Vivers València", "lat": 39.7081, "lon": -0.8319},
    "6634": {"nombre": "Burriana", "lat": 39.8922, "lon": -0.0650},
    "6633": {"nombre": "Benicassim", "lat": 40.0622, "lon": 0.0728},
    "6632": {"nombre": "Almassora", "lat": 39.9453, "lon": -0.0564},
    "6636": {"nombre": "Vinaròs Planta", "lat": 40.5461, "lon": -0.4250},
    "6635": {"nombre": "Vinaròs Plataforma", "lat": 40.3833, "lon": -0.7092},
    "5263": {"nombre": "L'Alcora", "lat": 40.0519, "lon": -0.1897},
    "5264": {"nombre": "Viver", "lat": 39.9306, "lon": -0.6033},
    "5265": {"nombre": "Zorita del Maestrazgo", "lat": 40.7350, "lon": -0.1694},
    "6630": {"nombre": "Rabassa Alacant", "lat": 38.3511, "lon": -0.5139},
    "6631": {"nombre": "Elda", "lat": 38.4547, "lon": -0.8033},
    "10531": {"nombre": "Algar de Palància", "lat": 39.7822, "lon": -0.3592},
    "5183": {"nombre": "San Basilio Murcia", "lat": 37.9940, "lon": -1.1446},
    "5184": {"nombre": "Aljorra Litoral", "lat": 37.6942, "lon": -1.0646},
    "5185": {"nombre": "Alumbres Cartagena", "lat": 37.6049, "lon": -0.9140},
    "5186": {"nombre": "Mompean Cartagena", "lat": 37.6034, "lon": -0.9749},
    "5187": {"nombre": "Valle Escombreras", "lat": 37.5744, "lon": -0.9266},
}

# ==================== FUNCIONES ====================

def leer_gps():
    try:
        gps = UART(1, baudrate=115200, tx=Pin(4), rx=Pin(5), timeout=2000)
        inicio = time.time()
        while time.time() - inicio < 5:
            if gps.any():
                linea = gps.readline()
                if linea and (b'$GPRMC' in linea or b'$GNRMC' in linea):
                    partes = linea.decode('utf-8', 'ignore').split(',')
                    if len(partes) >= 7 and partes[2] == 'A':
                        try:
                            lat = float(partes[3][:2]) + float(partes[3][2:]) / 60.0
                            lon = float(partes[5][:3]) + float(partes[5][3:]) / 60.0
                            if partes[4] == 'S': lat = -lat
                            if partes[6] == 'W': lon = -lon
                            gps.deinit()
                            return str(lat), str(lon)
                        except:
                            pass
            time.sleep(0.1)
        gps.deinit()
    except Exception as e:
        print(f"   [GPS] Error: {e}")
    return None, None

def obtener_offset_utc():
    """Obtiene el offset UTC actual consultando ip-api.com.
    Devuelve offset en horas (ej: 2 para UTC+2, 1 para UTC+1).
    Si falla, devuelve 2 (España verano) por defecto."""
    global zona_horaria
    try:
        resp = urequests.get("http://ip-api.com/json/?fields=timezone,offset")
        if resp.status_code == 200 and resp.text and resp.text.startswith('{'):
            datos = ujson.loads(resp.text)
            resp.close()
            
            offset_segundos = int(datos.get('offset', 7200))
            offset_horas = offset_segundos // 3600
            zona_horaria = datos.get('timezone', 'Europe/Madrid')
            
            print(f"   [TZ] Zona horaria: {zona_horaria} (UTC{offset_horas:+d})")
            return offset_horas
        else:
            resp.close()
    except Exception as e:
        print(f"   [TZ] Error: {e}")
    
    zona_horaria = "Europe/Madrid"
    return 2

def completar_datos_faltantes(temp, hum, pres, viento, ubicacion, region, dist_mostrar, LAT, LON):
    if temp is None or temp == 0: temp = 20
    if hum is None or hum == 0: hum = 50
    if pres is None or pres == 0: pres = 1013.25
    if viento is None or viento == 0: viento = 3
    if ubicacion is None or ubicacion == "": ubicacion = ultima_ubicacion_valida
    if region is None or region == "": region = ultima_region_valida
    if dist_mostrar is None or dist_mostrar == 0: dist_mostrar = ultima_distancia_valida

    if temp == 20 or hum == 50 or viento == 3:
        try:
            t_om, h_om, v_om = descargar_meteo(LAT, LON)
            if t_om is not None and t_om != 20: temp = t_om
            if h_om is not None and h_om != 50: hum = h_om
            if v_om is not None and v_om != 3: viento = v_om
        except:
            pass

    return temp, hum, pres, viento, ubicacion, region, dist_mostrar

def validar_y_propagar(valor, clave):
    global ultimo_valido
    if valor is not None:
        try:
            num_val = float(valor)
            if clave in ["pm25","pm10","no2","o3","aqi_real"] and 0 <= num_val <= 500: ultimo_valido[clave] = valor; return valor
            elif clave in ["temperatura"] and -20 <= num_val <= 50: ultimo_valido[clave] = valor; return valor
            elif clave in ["humedad"] and 0 <= num_val <= 100: ultimo_valido[clave] = valor; return valor
            elif clave in ["viento"] and 0 <= num_val <= 50: ultimo_valido[clave] = valor; return valor
        except: pass
    return ultimo_valido[clave]

def verificar_modelo(pm25, pm10, o3, no2, temp, hum, viento, aqi_real):
    try:
        aqi_pred = predecir_aqi(pm25, pm10, o3, no2, temp, hum, viento)
        error = abs(aqi_real - aqi_pred) if aqi_real > 0 else 0
        error_pct = (error / aqi_real * 100) if aqi_real > 0 else 0
        print(f"   [DIAGNOSTICO] AQI real: {aqi_real:.1f} | Pred: {aqi_pred:.1f} | Error: {error:.1f} pts ({error_pct:.1f}%)")
        if error_pct > 30:
            print(f"   [AVISO] Error alto (>30%)")
        return aqi_pred
    except Exception as e:
        print(f"   [DIAGNOSTICO] Error: {e}")
        return aqi_real

def calcular_ica_oficial(pm25, pm10, o3, no2, so2=0):
    t = [(0,10,0,50),(10,20,50,100),(20,25,100,150),(25,50,150,200),(50,75,200,300),(75,800,300,500)]
    def ip(c, tab):
        if c is None or c < 0: return 0
        for Cl, Ch, Il, Ih in tab:
            if Cl <= c <= Ch: return round(((Ih-Il)/(Ch-Cl))*(c-Cl)+Il)
        return 500
    return max(ip(pm25,t), ip(pm10,[(0,20,0,50),(20,35,50,100),(35,50,100,150),(50,100,150,200),(100,200,200,300),(200,600,300,500)]),
               ip(o3,[(0,80,0,50),(80,120,50,100),(120,180,100,150),(180,240,150,200),(240,400,200,300),(400,600,300,500)]),
               ip(no2,[(0,40,0,50),(40,100,50,100),(100,200,100,150),(200,400,150,200),(400,600,200,300),(600,800,300,500)]),
               ip(so2,[(0,100,0,50),(100,200,50,100),(200,350,100,150),(350,500,150,200),(500,750,200,300),(750,1250,300,500)]))

def descargar_forecast_24h(lat, lon):
    """Descarga forecast de contaminantes de Open-Meteo.
    Devuelve lista de 24 predicciones a partir de hora_actual + 24."""
    for intento in range(2):
        try:
            gc.collect()
            url_aq = (
                f"https://air-quality-api.open-meteo.com/v1/air-quality"
                f"?latitude={lat}&longitude={lon}"
                f"&hourly=pm2_5,pm10,nitrogen_dioxide,ozone"
                f"&timezone=Europe/Madrid"
                f"&forecast_days=3"
            )
            resp = urequests.get(url_aq)
            texto = resp.text
            resp.close()
            datos = ujson.loads(texto)

            hourly = datos.get('hourly', {})
            tiempos = hourly.get('time', [])
            pm25_f = hourly.get('pm2_5', [])
            pm10_f = hourly.get('pm10', [])
            no2_f = hourly.get('nitrogen_dioxide', [])
            o3_f = hourly.get('ozone', [])

            gc.collect()
            url_meteo = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                f"&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m"
                f"&timezone=Europe/Madrid"
                f"&forecast_days=3"
            )
            resp_m = urequests.get(url_meteo)
            texto_m = resp_m.text
            resp_m.close()
            datos_m = ujson.loads(texto_m)

            meteo = datos_m.get('hourly', {})
            temp_f = meteo.get('temperature_2m', [])
            hum_f = meteo.get('relative_humidity_2m', [])
            viento_f = meteo.get('wind_speed_10m', [])

            del datos
            del datos_m
            del texto
            del texto_m
            gc.collect()

            if tiempos and len(tiempos) > 0:
                hora_actual = time.localtime()[3]
                idx_inicio = hora_actual + 24
                if idx_inicio >= len(tiempos):
                    idx_inicio = len(tiempos) - 1
                if idx_inicio < 0:
                    idx_inicio = 0

                predicciones = []
                for offset in range(24):
                    idx = idx_inicio + offset
                    if idx >= len(tiempos):
                        break

                    pm25_m = pm25_f[idx] if idx < len(pm25_f) and pm25_f[idx] is not None else 10
                    pm10_m = pm10_f[idx] if idx < len(pm10_f) and pm10_f[idx] is not None else 20
                    no2_m = no2_f[idx] if idx < len(no2_f) and no2_f[idx] is not None else 10
                    o3_m = o3_f[idx] if idx < len(o3_f) and o3_f[idx] is not None else 50
                    temp_m = temp_f[idx] if idx < len(temp_f) and temp_f[idx] is not None else 20
                    hum_m = hum_f[idx] if idx < len(hum_f) and hum_f[idx] is not None else 50
                    viento_m = viento_f[idx] if idx < len(viento_f) and viento_f[idx] is not None else 3

                    aqi_hora = predecir_aqi(pm25_m, pm10_m, o3_m, no2_m, temp_m, hum_m, viento_m)

                    predicciones.append({
                        "hora": tiempos[idx][:16],
                        "aqi": round(aqi_hora, 1),
                        "pm25": round(pm25_m, 1),
                        "pm10": round(pm10_m, 1),
                        "no2": round(no2_m, 1),
                        "o3": round(o3_m, 1)
                    })

                return predicciones
        except Exception as e:
            if intento == 0:
                print(f"   [FORECAST] Reintentando... ({e})")
                time.sleep(2)
                gc.collect()
            else:
                print(f"   [FORECAST] Error final: {e}")
                gc.collect()
    return None

def conectar_wifi():
    wlan = network.WLAN(network.STA_IF); wlan.active(False); time.sleep(0.5); wlan.active(True); time.sleep(1)
    if wlan.isconnected(): return True
    for red in REDES_WIFI:
        try:
            wlan.connect(red["ssid"], red["password"])
            for _ in range(30):
                if wlan.isconnected(): return True
                time.sleep(0.5)
            wlan.active(False); time.sleep(0.5); wlan.active(True); time.sleep(1)
        except: pass
    return False

def sincronizar_hora():
    for _ in range(3):
        try: ntptime.settime(); return True
        except: time.sleep(1)
    return False

def distancia_km(lat1, lon1, lat2, lon2):
    try:
        lat1,lon1,lat2,lon2 = map(float,[lat1,lon1,lat2,lon2])
        dlat,dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
        return 6371*2*math.atan2(math.sqrt(a),math.sqrt(1-a))
    except: return 9999

def estaciones_ordenadas_por_cercania(lat, lon, est_dict):
    r = [(distancia_km(lat,lon,d["lat"],d["lon"]),uid,d["nombre"]) for uid,d in est_dict.items()]
    r.sort(); return r

def categoria_eu_aqi(valor):
    try:
        v = int(valor)
        if v <= 50: return "Buena"
        elif v <= 100: return "Moderada"
        elif v <= 150: return "Mala"
        elif v <= 200: return "Muy mala"
        else: return "Peligrosa"
    except: return "Error"

def mostrar(linea1, linea2, segundos):
    try: print(f"[LCD] {str(linea1)[:16]} | {str(linea2)[:16]}")
    except: pass
    try: lcd.clear(); lcd.putstr(str(linea1)[:16]); lcd.move_to(0,1); lcd.putstr(str(linea2)[:16])
    except: pass
    time.sleep(segundos)

def obtener_ubicacion():
    lat_gps, lon_gps = leer_gps()
    if lat_gps and lon_gps:
        print(f"   [GPS] Fix obtenido: {lat_gps[:8]}, {lon_gps[:8]}")
        return lat_gps, lon_gps, "GPS", "GPS"

    try:
        resp = urequests.get("http://ip-api.com/json/?fields=lat,lon,city,district,zip,regionName")
        if resp.text and resp.text.startswith('{'):
            d = ujson.loads(resp.text); resp.close()
            ubi = d.get("city","Valencia")
            if d.get("district"): ubi += f",{d['district'][:8]}"
            if d.get("zip"): ubi += f",CP{d['zip']}"
            return str(d.get("lat",LAT_DEFAULT)), str(d.get("lon",LON_DEFAULT)), ubi, d.get("regionName","C.Valenciana")
        resp.close()
    except: pass

    return LAT_DEFAULT, LON_DEFAULT, "Valencia", "C.Valenciana"

def descargar_gva(uid):
    """
    Descarga datos de GVA con descarte INMEDIATO si no tiene PM2.5.
    Solo reintenta si hay ERROR DE CONEXION (no si falta PM2.5).
    """
    hoy = time.localtime(); fecha = f"{hoy[0]}-{hoy[1]:02d}-{hoy[2]:02d}"
    host = "rvvcca.pica.gva.es"
    path = (f"/downloadformat/hourly/cda/json?file=https://bi.pica.gva.es/pentaho/plugin/cda/api/doQuery"
            f"?_TRUST_USER_=opendata_gva&path=/public/gva/verticals/sql/hourlyAverage.cda"
            f"&dataAccessId=HourlyAverage&paramstart={fecha}%2000%3A00%3A00"
            f"&paramfinish={fecha}%2023%3A59%3A59&paramidStation={uid}")
    gc.collect()

    for intento in range(3):
        try:
            addr = socket.getaddrinfo(host,443)[0][-1]
            s = socket.socket()
            s.settimeout(15)
            s.connect(addr)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname=False
            ctx.verify_mode=ssl.CERT_NONE
            s = ctx.wrap_socket(s, server_hostname=host)
            s.write(f"GET {path} HTTP/1.0\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
            resp=b""
            for _ in range(150):
                chunk=s.read(512)
                if chunk: resp+=chunk
                if b'"PM2.5":' in resp and b']' in resp: break
            s.close()
            texto=resp.decode('utf-8')
            pos=texto.find('[')

            # ===== DESCARTE INMEDIATO SI NO TIENE PM2.5 =====
            if pos <= 0 or '"PM2.5":' not in texto:
                print(f"   [GVA] Sin PM2.5 en respuesta, descartando estacion")
                return None

            cuerpo=texto[pos:]
            def ex(tag,default=0):
                p=cuerpo.rfind(f'"{tag}":')
                if p>0:
                    i=p+len(tag)+3
                    f1=cuerpo.find(',',i)
                    f2=cuerpo.find('}',i)
                    try: return float(cuerpo[i:(f1 if f1>0 else f2)].strip())
                    except: pass
                return default

            pm25 = ex("PM2.5", 0)
            pm10 = ex("PM10", 0)

            if not pm25 or pm25 <= 0:
                print(f"   [GVA] PM2.5 invalido ({pm25}), descartando estacion")
                return None

            if pm25 and pm10:
                o3_val = ex("O3",50)
                no2_val = ex("NO2",10)
                so2_val = ex("SO2",0)
                resultado = {"pm25":pm25,"pm10":pm10,"o3":o3_val,"no2":no2_val,"so2":so2_val,
                        "aqi":calcular_ica_oficial(pm25,pm10,o3_val,no2_val,so2_val),
                        "temperatura":ex("Temp."),"humedad":ex("H.Rel.")}
                del resp
                del texto
                del cuerpo
                gc.collect()
                return resultado
            else:
                print(f"   [GVA] Datos incompletos (pm25={pm25}, pm10={pm10}), descartando")
                return None

        except Exception as e:
            print(f"   [GVA] Intento {intento+1}/3 - Error conexion: {type(e).__name__}: {e}")
            gc.collect()
        time.sleep(2)
    return None

def descargar_waqi(uid):
    try:
        resp=urequests.get(f"https://api.waqi.info/feed/@{uid}/?token={TOKEN_WAQI}")
        texto = resp.text
        resp.close()
        d=ujson.loads(texto)
        del texto
        if d.get("status")=="ok":
            i=d["data"].get("iaqi",{})
            resultado = {"pm25":i.get("pm25",{}).get("v")or 9,
                    "pm10":i.get("pm10",{}).get("v")or 19,
                    "no2":i.get("no2",{}).get("v")or 10,
                    "o3":i.get("o3",{}).get("v")or 50,
                    "temperatura":i.get("t",{}).get("v"),
                    "humedad":i.get("h",{}).get("v"),
                    "viento":i.get("w",{}).get("v")}
            del d
            gc.collect()
            return resultado
    except: pass
    return None

def descargar_om(lat,lon):
    try:
        resp=urequests.get(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm2_5,pm10,nitrogen_dioxide,ozone&timezone=Europe/Madrid")
        texto = resp.text
        resp.close()
        datos = ujson.loads(texto)
        c=datos.get("current",{})
        resultado = {"pm25":c.get("pm2_5",9)or 9,
                "pm10":c.get("pm10",19)or 19,
                "no2":c.get("nitrogen_dioxide",10)or 10,
                "o3":c.get("ozone",50)or 50}
        del texto
        del datos
        gc.collect()
        return resultado
    except: return None

def descargar_meteo(lat,lon):
    try:
        resp=urequests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m&timezone=Europe/Madrid")
        texto = resp.text
        resp.close()
        datos = ujson.loads(texto)
        c=datos.get("current",{})
        resultado = (c.get("temperature_2m",20)or 20,c.get("relative_humidity_2m",50)or 50,c.get("wind_speed_10m",3)or 3)
        del texto
        del datos
        gc.collect()
        return resultado
    except: return (20,50,3)

def enviar_a_pc(datos):
    try:
        for k,v in list(datos.items()):
            if isinstance(v,float)and(math.isnan(v)or math.isinf(v)): datos[k]=0
        json_str=ujson.dumps(datos)
        addr=socket.getaddrinfo(PC_IP,PUERTO_PC)[0][-1]; s=socket.socket(); s.settimeout(10); s.connect(addr)
        body=json_str.encode()
        request=(f"POST /api/datos HTTP/1.0\r\nHost: {PC_IP}:{PUERTO_PC}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode()+body
        s.write(request)
        resp=b""
        while True:
            chunk=s.read(128)
            if not chunk: break
            resp+=chunk
        s.close()
        del json_str
        del body
        del request
        gc.collect()
        if b"200" in resp: print("   Enviado a PC"); return True
        else: print("   Error servidor"); return False
    except Exception as e: print(f"   No se pudo enviar: {e}"); return False

def guardar_en_buffer(registro):
    """Guarda el registro en el buffer local.
    ANTI-DUPLICADOS: no guarda si ya existe un registro similar en los ultimos 3.
    MAXIMO 100 registros: si se llena elimina los 10 mas antiguos."""
    try:
        MAX_REGISTROS_BUFFER = 100

        # ===== ANTI-DUPLICADOS =====
        try:
            if ARCHIVO_BUFFER in os.listdir():
                with open(ARCHIVO_BUFFER, 'r') as f:
                    lineas = f.readlines()

                if len(lineas) > 1:
                    ultimos = lineas[-3:] if len(lineas) >= 3 else lineas[1:]

                    estacion_nueva = registro.get('estacion', '')
                    pm25_nuevo = float(registro.get('pm25', 0) or 0)
                    pm10_nuevo = float(registro.get('pm10', 0) or 0)
                    aqi_nuevo = float(registro.get('aqi_real', 0) or 0)

                    for linea_ant in ultimos:
                        partes = linea_ant.strip().split(',')
                        if len(partes) >= 15:
                            try:
                                if (partes[4] == estacion_nueva and
                                    abs(float(partes[8] or 0) - pm25_nuevo) < 0.1 and
                                    abs(float(partes[9] or 0) - pm10_nuevo) < 0.1 and
                                    abs(float(partes[14] or 0) - aqi_nuevo) < 0.1):
                                    print(f"   DUPLICADO ({estacion_nueva}, pm25={pm25_nuevo}, aqi={aqi_nuevo}), saltando")
                                    return False
                            except:
                                pass
        except:
            pass
        # ===== FIN ANTI-DUPLICADOS =====

        num_registros = 0
        try:
            if ARCHIVO_BUFFER in os.listdir():
                with open(ARCHIVO_BUFFER, 'r') as f:
                    lineas = f.readlines()
                num_registros = len(lineas) - 1
        except:
            pass

        if num_registros >= MAX_REGISTROS_BUFFER:
            print(f"   BUFFER LLENO ({num_registros}/{MAX_REGISTROS_BUFFER}), eliminando 10 mas antiguos...")
            try:
                with open(ARCHIVO_BUFFER, 'r') as f:
                    lineas = f.readlines()
                lineas_nuevas = [lineas[0]] + lineas[11:]
                with open(ARCHIVO_BUFFER, 'w') as f:
                    f.writelines(lineas_nuevas)
                num_registros = len(lineas_nuevas) - 1
            except Exception as e:
                print(f"   Error reduciendo buffer: {e}")

        ts = registro.get('timestamp_str', '')
        lat = registro.get('lat', '0')
        lon = registro.get('lon', '0')
        fu = registro.get('fuente', 'Desconocida')
        es = registro.get('estacion', 'Desconocida')
        ubi = registro.get('ubicacion', 'Desconocida')
        reg = registro.get('region', 'Desconocida')

        def to_float_str(v):
            try:
                f = float(v) if v is not None else 0
                return "{:.2f}".format(f).replace(',', '.')
            except:
                return "0.00"

        dist_s = to_float_str(registro.get('distancia_km', 0))
        pm25_s = to_float_str(registro.get('pm25', 0))
        pm10_s = to_float_str(registro.get('pm10', 0))
        no2_s  = to_float_str(registro.get('no2', 0))
        o3_s   = to_float_str(registro.get('o3', 0))
        temp_s = to_float_str(registro.get('temperatura', 0))
        hum_s  = to_float_str(registro.get('humedad', 0))
        aqi_r_s = to_float_str(registro.get('aqi_real', 0))
        aqi_p_s = to_float_str(registro.get('aqi_predicho', 0))
        cat = registro.get('categoria', 'Desconocida')

        pred_24h = registro.get('predicciones_24h', [])
        if len(pred_24h) > 12:
            pred_24h = pred_24h[:12]

        pred_24h_str = ujson.dumps(pred_24h).replace(',', ';')

        existe = False
        try:
            if ARCHIVO_BUFFER in os.listdir(): existe = True
        except: pass

        with open(ARCHIVO_BUFFER, 'a') as f:
            if not existe:
                f.write("timestamp_str,lat,lon,fuente,estacion,ubicacion,region,distancia_km,pm25,pm10,no2,o3,temperatura,humedad,aqi_real,aqi_predicho,categoria,predicciones_24h\n")
            linea = f"{ts},{lat},{lon},{fu},{es},{ubi},{reg},{dist_s},{pm25_s},{pm10_s},{no2_s},{o3_s},{temp_s},{hum_s},{aqi_r_s},{aqi_p_s},{cat},{pred_24h_str}\n"
            f.write(linea)

        del pred_24h_str
        gc.collect()
        print(f"   BUFFER ({num_registros+1}/{MAX_REGISTROS_BUFFER}): {ts} | {fu} | AQI:{aqi_r_s}")
        return True
    except Exception as e:
        print(f"   ERROR BUFFER: {type(e).__name__}: {e}")
        return False

def enviar_datos_pendientes():
    try:
        if ARCHIVO_BUFFER not in os.listdir():
            return

        gc.collect()
        time.sleep(0.3)
        gc.collect()

        print("   [BUFFER] Leyendo datos pendientes...")
        with open(ARCHIVO_BUFFER, 'r') as f:
            lineas = f.readlines()

        if len(lineas) == 0:
            print("   [BUFFER] Archivo vacio")
            os.remove(ARCHIVO_BUFFER)
            return

        primera = lineas[0].strip()
        if primera.startswith("timestamp_str"):
            lineas_datos = lineas[1:]
        else:
            lineas_datos = lineas

        if len(lineas_datos) == 0:
            print("   [BUFFER] Solo cabecera, eliminando")
            os.remove(ARCHIVO_BUFFER)
            return

        print(f"   [BUFFER] {len(lineas_datos)} registros pendientes")

        enviados = 0
        lineas_restantes = []

        for i, linea in enumerate(lineas_datos, 1):
            linea = linea.strip()
            if not linea:
                continue

            partes = linea.split(',')
            if len(partes) >= 17:
                try:
                    pred_24h = []
                    if len(partes) >= 18:
                        try:
                            pred_str = partes[17].replace(';', ',')
                            pred_24h = ujson.loads(pred_str)
                        except:
                            pred_24h = []

                    reg = {
                        "timestamp_str": partes[0],
                        "lat": partes[1] or "0",
                        "lon": partes[2] or "0",
                        "fuente": partes[3] or "Desconocida",
                        "estacion": partes[4] or "Desconocida",
                        "ubicacion": partes[5] or "Desconocida",
                        "region": partes[6] or "Desconocida",
                        "distancia_km": float(partes[7] or 0),
                        "pm25": float(partes[8] or 0),
                        "pm10": float(partes[9] or 0),
                        "no2": float(partes[10] or 0),
                        "o3": float(partes[11] or 0),
                        "temperatura": float(partes[12] or 0),
                        "humedad": float(partes[13] or 0),
                        "aqi_real": float(partes[14] or 0),
                        "aqi_predicho": float(partes[15] or 0),
                        "categoria": partes[16] or "Desconocida",
                        "predicciones_24h": pred_24h
                    }
                    if enviar_a_pc(reg):
                        enviados += 1
                        print(f"   [BUFFER] {i}/{len(lineas_datos)} enviado")
                    else:
                        print(f"   [BUFFER] Fallo {i}/{len(lineas_datos)} - se conserva")
                        lineas_restantes.append(linea + "\n")
                    time.sleep(0.3)
                    gc.collect()
                except Exception as e:
                    print(f"   [BUFFER] Error linea {i}: {e}")
                    continue
            else:
                print(f"   [BUFFER] Linea {i} formato invalido ({len(partes)} cols)")

        if len(lineas_restantes) > 0:
            with open(ARCHIVO_BUFFER, 'w') as f:
                f.write("timestamp_str,lat,lon,fuente,estacion,ubicacion,region,distancia_km,pm25,pm10,no2,o3,temperatura,humedad,aqi_real,aqi_predicho,categoria,predicciones_24h\n")
                for linea in lineas_restantes:
                    f.write(linea)
            print(f"   [BUFFER] Quedan {len(lineas_restantes)} registros pendientes")
        else:
            try:
                os.remove(ARCHIVO_BUFFER)
                print(f"   [BUFFER] Todos enviados, buffer eliminado")
            except Exception as e:
                print(f"   [BUFFER] Error eliminando: {e}")

        if enviados > 0:
            print(f"   {enviados} datos enviados, buffer actualizado")
    except Exception as e:
        print(f"   [BUFFER] Error: {e}")

# ==================== INICIALIZAR ====================
try:
    i2c=I2C(0,sda=Pin(0),scl=Pin(1),freq=400000); lcd=I2cLcd(i2c,0x27,2,16)
    mostrar("TFM Valencia","Prediccion AQI",2)
except:
    class LcdFake: pass
    lcd=LcdFake()

try: bme=BME280(i2c=i2c,address=0x77); print("BME280 OK")
except: bme=None; print("BME280 no detectado")

mostrar("Conectando WiFi","",1)
if conectar_wifi():
    mostrar("WiFi OK!","",1)
    sincronizar_hora()
    OFFSET_TZ = obtener_offset_utc()  # ← AÑADIR ESTA LÍNEA
else:
    mostrar("WiFi FALLIDO","Usando offline",2)

# ==================== BUCLE PRINCIPAL ====================
ciclos=0; pres=1013.25

while True:
    ciclos+=1
    gc.collect()
    print(f"\nCICLO {ciclos} | Mem: {gc.mem_free()}B")

    if not network.WLAN(network.STA_IF).isconnected():
        mostrar("WiFi Caido","Reconectando...",1)
        if conectar_wifi(): sincronizar_hora()
        mostrar("WiFi RESTAURADO!","",1)

    if ciclos%21600==0 and network.WLAN(network.STA_IF).isconnected(): sincronizar_hora()

    fuente,nombre_fuente,dist_mostrar="Open-Meteo","CAMS",0
    aqi_om,pm25,pm10=42,9,19; no2,o3=10,50; temp,hum,viento=20,50,3

    mostrar("Descargando info", ".", 0.2)
    mostrar("Descargando info", "..", 0.2)

    LAT,LON,ubicacion,region=obtener_ubicacion()

    try:
        lat_f,lon_f=float(LAT),float(LON)
        if LAT_MIN<=lat_f<=LAT_MAX and LON_MIN<=lon_f<=LON_MAX:
            ultima_lat_valida,ultima_lon_valida=LAT,LON
            ultima_ubicacion_valida,ultima_region_valida=ubicacion,region
        else: LAT,LON,ubicacion,region=ultima_lat_valida,ultima_lon_valida,ultima_ubicacion_valida,ultima_region_valida
    except: pass

    # ===== 1. GVA: 3 estaciones mas cercanas (con descarte inmediato) =====
    intentos_gva = 0
    for dist_gva, uid_gva, nombre_gva in estaciones_ordenadas_por_cercania(LAT, LON, ESTACIONES_GVA):
        if dist_gva < DISTANCIA_MAX_KM and intentos_gva < 3:
            intentos_gva += 1
            mostrar("Descargando GVA", f"{intentos_gva}/3 {nombre_gva[:12]}", 0.5)
            datos = descargar_gva(uid_gva)
            if datos:
                pm25, pm10 = datos["pm25"], datos["pm10"]
                o3, no2 = datos.get("o3", 50), datos.get("no2", 10)
                aqi_om = datos["aqi"]
                fuente, nombre_fuente = "GVA", nombre_gva
                dist_mostrar = dist_gva
                if datos.get("temperatura"): temp = datos["temperatura"]
                if datos.get("humedad"): hum = datos["humedad"]
                print(f"   [GVA] {nombre_gva} ({dist_gva:.1f} km) - AQI={aqi_om}")
                del datos
                gc.collect()
                break
            else:
                print(f"   [GVA] {nombre_gva} sin datos utiles, probando siguiente...")
                gc.collect()
        else:
            break
    if fuente == "Open-Meteo" and intentos_gva > 0:
        print(f"   [INFO] GVA no disponible, pasando a WAQI")

    # ===== 2. WAQI: 3 estaciones mas cercanas =====
    if fuente == "Open-Meteo" and intentos_gva > 0:
        intentos_waqi = 0
        for dist_w, uid_w, nombre_w in estaciones_ordenadas_por_cercania(LAT, LON, ESTACIONES_WAQI):
            if dist_w < DISTANCIA_MAX_KM and intentos_waqi < 3:
                intentos_waqi += 1
                mostrar("Descargando WAQI", f"{intentos_waqi}/3 {nombre_w[:12]}", 0.5)
                datos = descargar_waqi(uid_w)
                if datos:
                    pm25, pm10 = datos["pm25"], datos["pm10"]
                    no2, o3 = datos["no2"], datos["o3"]
                    aqi_om = calcular_ica_oficial(pm25, pm10, o3, no2)
                    if datos.get("temperatura"): temp = datos["temperatura"]
                    if datos.get("humedad"): hum = datos["humedad"]
                    if datos.get("viento"): viento = datos["viento"]
                    fuente, nombre_fuente = "WAQI", nombre_w
                    dist_mostrar = dist_w
                    print(f"   [WAQI] {nombre_w} ({dist_w:.1f} km) - AQI={aqi_om}")
                    del datos
                    gc.collect()
                    break
            else:
                break
        if fuente == "Open-Meteo":
            print(f"   [INFO] WAQI no disponible, usando Open-Meteo")
            datos_om = descargar_om(LAT, LON)
            if datos_om:
                pm25, pm10 = datos_om["pm25"], datos_om["pm10"]
                no2, o3 = datos_om["no2"], datos_om["o3"]
                aqi_om = calcular_ica_oficial(pm25, pm10, o3, no2)
                fuente, nombre_fuente = "Open-Meteo", "CAMS"
                dist_mostrar = 0
                print(f"   [OM] Coordenadas exactas - AQI={aqi_om}")
                del datos_om
                gc.collect()

    if bme:
        try: temp=float(bme.values[0].replace('C','')); hum=float(bme.values[2].replace('%','')); pres=float(bme.values[1].replace('hPa',''))
        except: pass

    temp,hum,pres,viento,ubicacion,region,dist_mostrar=completar_datos_faltantes(temp,hum,pres,viento,ubicacion,region,dist_mostrar,LAT,LON)

    pm25=validar_y_propagar(pm25,"pm25"); pm10=validar_y_propagar(pm10,"pm10")
    no2=validar_y_propagar(no2,"no2"); o3=validar_y_propagar(o3,"o3")
    temp=validar_y_propagar(temp,"temperatura"); hum=validar_y_propagar(hum,"humedad")
    viento=validar_y_propagar(viento,"viento"); aqi_om=validar_y_propagar(aqi_om,"aqi_real")

    # ===== MODELO GRADO 2 COMO PRINCIPAL =====
    aqi_pred = None
    predicciones_24h = []
    fuente_pred = "Modelo"

    try:
        print(f"   [MODELO] Usando modelo grado 2: pm25={pm25}, pm10={pm10}, o3={o3}, no2={no2}")
        aqi_pred = predecir_aqi(pm25, pm10, o3, no2, temp, hum, viento)
        if aqi_pred is None or aqi_pred <= 5 or aqi_pred > 500:
            print(f"   [MODELO] Valor anomalo ({aqi_pred}), usando CAMS")
            aqi_pred = None
        else:
            print(f"   [MODELO] OK: {aqi_pred:.1f}")
            fuente_pred = "Modelo"
    except Exception as e:
        print(f"   [MODELO] Error: {e}")
        aqi_pred = None

    # ===== CAMS FORECAST COMO RESPALDO DEL VALOR PRINCIPAL =====
    if aqi_pred is None:
        print(f"   [CAMS] Descargando forecast CAMS (respaldo)...")
        reserva_memoria = None
        try:
            reserva_memoria = bytearray(6000)
        except:
            pass
        gc.collect()
        predicciones_24h = descargar_forecast_24h(LAT, LON)
        if reserva_memoria:
            del reserva_memoria
            reserva_memoria = None
        gc.collect()

        if predicciones_24h and len(predicciones_24h) > 0:
            aqi_pred = predicciones_24h[0]["aqi"]
            fuente_pred = "CAMS"
            print(f"   [CAMS] Forecast OK: {aqi_pred:.1f} ({len(predicciones_24h)} horas)")
        else:
            print(f"   [CAMS] Forecast fallo, usando AQI real")
            predicciones_24h = []
            aqi_pred = aqi_om
            fuente_pred = "AQI real"

    diferencia = aqi_pred - aqi_om
    cat_pred = categoria_eu_aqi(int(aqi_pred))

    if ciclos % 10 == 0:
        verificar_modelo(pm25, pm10, o3, no2, temp, hum, viento, aqi_om)

    # ===== ENVIO AL PC CADA 30 MIN (CON CAMS FRESCO) =====
    if time.time() - ultimo_envio >= INTERVALO_ENVIO_SEGUNDOS:
        ultimo_envio = time.time()
        gc.collect()
        try:
            # ----- 1. Descargar CAMS fresco si aun no tenemos predicciones -----
            if len(predicciones_24h) == 0:
                print(f"   [CAMS] Descargando forecast 24h antes del envio...")
                reserva_memoria = None
                try:
                    reserva_memoria = bytearray(6000)
                except:
                    pass
                gc.collect()
                predicciones_24h = descargar_forecast_24h(LAT, LON)
                if reserva_memoria:
                    del reserva_memoria
                    reserva_memoria = None
                gc.collect()

                if predicciones_24h and len(predicciones_24h) > 0:
                    print(f"   [CAMS] {len(predicciones_24h)} predicciones generadas")
                    print(f"   [CAMS] AQI a +24h: {predicciones_24h[0]['aqi']}")
                    mostrar("CAMS 24h:", f"AQI: {predicciones_24h[0]['aqi']:.1f}", 2)
                else:
                    print(f"   [CAMS] No disponible, enviando sin predicciones")
                    predicciones_24h = []

            # ----- 2. Construir registro -----
            tm=time.localtime(time.time() + OFFSET_TZ * 3600)
            registro = {
                "timestamp_str": f"{tm[0]}-{tm[1]:02d}-{tm[2]:02d} {tm[3]:02d}:{tm[4]:02d}:{tm[5]:02d}",
                "lat": LAT or "0", "lon": LON or "0",
                "ubicacion": ubicacion or "Desconocida", "region": region or "Desconocida",
                "fuente": fuente or "Desconocida", "estacion": nombre_fuente or "Desconocida",
                "distancia_km": round(dist_mostrar, 1) if dist_mostrar else 0,
                "pm25": pm25, "pm10": pm10, "no2": no2, "o3": o3,
                "temperatura": temp, "humedad": hum, "presion": pres, "viento": viento,
                "aqi_real": aqi_om, "aqi_predicho": aqi_pred,
                "diferencia": diferencia, "categoria": cat_pred,
                "fuente_prediccion": fuente_pred,
                "predicciones_24h": predicciones_24h if predicciones_24h else []
            }

            # ----- 3. Enviar -----
            envio_ok = enviar_a_pc(registro)

            if envio_ok:
                enviar_datos_pendientes()
            else:
                guardar_en_buffer(registro)
                gc.collect()
                time.sleep(0.5)
                enviar_datos_pendientes()

            # ----- 4. Limpiar predicciones para forzar descarga en el proximo envio -----
            predicciones_24h = []
            del registro
            gc.collect()
        except Exception as e:
            print(f"   [ERROR] En envio: {e}")

    # ===== PANTALLAS LCD =====
    mostrar(f"Fuente: {fuente}",f"{nombre_fuente[:16]}",3)
    if dist_mostrar>0: mostrar("Distancia Est.",f"{dist_mostrar:.1f} km",3)
    mostrar("Ubicacion:",f"{ubicacion[:16]}",3)
    mostrar("Region:",f"{region[:16]}",3)
    mostrar("Lat/Lon:",f"{LAT[:8]},{LON[:8]}",3)
    mostrar("PM2.5 / PM10:",f"{pm25} / {pm10}",3)
    mostrar("T:{:.1f}C H:{:.1f}%".format(temp,hum),"P:{:.1f}hPa".format(pres),3)
    mostrar(f"AQI HOY ({fuente}):",f"{aqi_om}",3)
    mostrar("Estimacion IA:",f"AQI: {aqi_pred:.1f}",3)
    mostrar(f"Hoy:{aqi_om:.1f}->IA:{aqi_pred:.1f}",f"Dif: {diferencia:+.1f}",3)
    mostrar("Calidad aire",f"es: {cat_pred}",3)
    
    gc.collect()
