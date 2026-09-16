# Prediccion_AQI_Valencia

Dispositivo de predicción de calidad del aire basado en Raspberry Pi Pico WH.

## Descripción

Sistema embebido que obtiene datos de calidad del aire de múltiples fuentes (GVA, WAQI, Open-Meteo), los procesa con un modelo de IA y los envía a un servidor Flask para su visualización.

## Archivos

- `main.py` - Programa principal de la Pico W
- `servidor_pico.py` - Servidor Flask + panel web

## Hardware

| Componente | Modelo |
|------------|--------|
| Microcontrolador | Raspberry Pi Pico WH (RP2040) |
| Pantalla | LCD 1602 con módulo I2C |
| Sensor ambiental | BME280 (I2C) |
| GPS | LC79D (UART) |
| Alimentación | Batería solar 10.000 mAh |

## Conexiones

| Componente | Pin Pico W |
|------------|------------|
| LCD SDA | GP0 |
| LCD SCL | GP1 |
| GPS TX | GP5 |
| GPS RX | GP4 |
| BME280 SDA | GP0 |
| BME280 SCL | GP1 |

## Fuentes de datos

- **GVA**: estaciones oficiales de la Generalitat Valenciana
- **WAQI**: estaciones globales (incluye sensor.community)
- **Open-Meteo**: modelo CAMS europeo para forecast y respaldo

## Modelo de IA

- Regresión polinómica de grado 2
- Dataset: 90.528 registros (2016-2026)
- R²: 0.72
- Tamaño: 3 KB

## Uso

### Pico W

1. Instalar MicroPython 1.28.0
2. Cargar `main.py` en la Pico
3. Configurar SSID y password del WiFi en `main.py`

### Servidor Flask

```bash
pip install flask pandas openpyxl numpy
python servidor_pico.py
