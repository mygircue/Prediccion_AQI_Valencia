# Prediccion_AQI_Valencia
DISPOSITIVO AUTONOMO - PREDICCION AQI EN PICO W

## Hardware

| Componente | Modelo |
|------------|--------|
| Microcontrolador | Raspberry Pi Pico WH (RP2040) |
| Pantalla | LCD 1602 con módulo I2C |
| Sensor ambiental | BME280 (I2C) |
| GPS | LC79D (UART) |
| Alimentación | Batería solar 10.000 mAh |

### Conexiones

| Componente | Pin Pico W |
|------------|------------|
| LCD SDA | GP0 |
| LCD SCL | GP1 |
| GPS TX | GP5 |
| GPS RX | GP4 |
| BME280 SDA | GP0 |
| BME280 SCL | GP1 |

## Fuentes de datos

- **GVA**: 40 estaciones oficiales de la Generalitat Valenciana
- **WAQI**: 35 estaciones globales (incluye sensor.community)
- **Open-Meteo**: modelo CAMS europeo para forecast y respaldo

## Modelo de IA

- **Tipo**: Regresión polinómica de grado 2
- **Dataset**: 90.528 registros históricos (2016-2026)
- **Variables**: PM2.5, PM10, O3, NO2, temperatura, humedad, viento
- **R²**: 0.72
- **Tamaño**: 3 KB (ejecutable en microcontrolador)

## Instalación y uso

### Pico W

1. Instalar MicroPython 1.28.0 en la Pico W
2. Cargar los archivos de la carpeta `pico/` en la Pico
3. Configurar SSID y password del WiFi en `main.py`
4. Ejecutar como `main.py` para arranque automático

### Servidor Flask

```bash
pip install flask pandas openpyxl numpy
python servidor_pico.py
