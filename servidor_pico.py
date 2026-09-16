"""
SERVIDOR PARA RECIBIR DATOS DE LA PICO W

"""

from flask import Flask, request, jsonify, render_template_string
import pandas as pd
from datetime import datetime, timedelta
import os
import threading
import webbrowser
import socket
import numpy as np
import json

app = Flask(__name__)

CARPETA_ACTUAL = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_CSV = os.path.join(CARPETA_ACTUAL, "datos_historicos_pico.csv")
ARCHIVO_EXCEL = os.path.join(CARPETA_ACTUAL, "datos_historicos_pico.xlsx")
ultimo_registro = None

print("=" * 60)
print("SERVIDOR - PREDICCION CALIDAD DEL AIRE")
print("=" * 60)
print(f"Carpeta: {CARPETA_ACTUAL}")
print(f"Datos: {ARCHIVO_CSV}")
print("=" * 60)


def buscar_prediccion_24h_anterior(timestamp_actual):
    """Busca en el CSV la prediccion que se hizo hace ~24 horas."""
    if not os.path.exists(ARCHIVO_CSV):
        return None
    
    try:
        df = pd.read_csv(ARCHIVO_CSV, encoding='utf-8-sig')
        
        if isinstance(timestamp_actual, str):
            ts_actual = pd.to_datetime(timestamp_actual, errors='coerce')
        else:
            ts_actual = timestamp_actual
        
        if pd.isna(ts_actual):
            return None
        
        hace_24h = ts_actual - pd.Timedelta(hours=24)
        
        for col in ['timestamp_servidor', 'timestamp_str']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                df = df.dropna(subset=[col])
                
                if len(df) == 0:
                    continue
                
                dif = abs(df[col] - hace_24h)
                df['dif_tiempo'] = dif
                cercano = df[df['dif_tiempo'] <= pd.Timedelta(hours=3)].nsmallest(1, 'dif_tiempo')
                
                if len(cercano) > 0:
                    reg = cercano.iloc[0]
                    return {
                        "aqi_predicho_ayer": round(float(reg.get('aqi_predicho', 0)), 1),
                        "fecha_pred_ayer": str(reg[col])[:16] if pd.notna(reg[col]) else None,
                        "dif_horas_ayer": round(float(reg['dif_tiempo'].total_seconds() / 3600), 1)
                    }
        return None
    except Exception as e:
        print(f"   [WARN] Error buscando prediccion 24h: {e}")
        return None


def limpiar_valor(valor, default=0):
    """Limpia valores problematicos para JSON y HTML"""
    if valor is None:
        return default
    if isinstance(valor, float) and (pd.isna(valor) if hasattr(pd, 'isna') else np.isnan(valor) or np.isinf(valor)):
        return default
    return valor


def parsear_predicciones_24h(valor):
    """Parsea el campo predicciones_24h"""
    if valor is None or valor == '' or valor == '[]':
        return []
    if isinstance(valor, list):
        return valor
    if isinstance(valor, str):
        try:
            return json.loads(valor)
        except:
            return []
    return []


# ==================== PLANTILLA HTML ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prediccion AQI - Pico W</title>
    <meta http-equiv="refresh" content="30">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        :root {
            --bg: #0f172a;
            --card: #1e293b;
            --accent: #e94560;
            --green: #00ff88;
            --yellow: #ffcc00;
            --orange: #ff8c00;
            --red: #ff4444;
            --purple: #a78bfa;
            --text: #e2e8f0;
            --text-muted: #94a3b8;
            --border: rgba(255,255,255,0.06);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body { 
            font-family: 'Inter', 'Segoe UI', system-ui, sans-serif; 
            background: linear-gradient(165deg, #0f172a 0%, #1a1a2e 50%, #16213e 100%);
            color: var(--text); 
            min-height: 100vh;
            padding: 16px;
        }
        
        .container { max-width: 1500px; margin: 0 auto; }
        
        .header {
            text-align: center;
            margin-bottom: 24px;
            padding: 20px 0;
            border-bottom: 1px solid var(--border);
        }
        
        .header h1 { 
            font-size: clamp(1.3rem, 3vw, 1.8rem);
            font-weight: 700;
            background: linear-gradient(135deg, var(--green), var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 4px;
        }
        
        .header .subtitle {
            font-size: 0.8rem;
            color: var(--text-muted);
            letter-spacing: 0.5px;
        }
        
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }
        
        .stat-card {
            background: var(--card);
            border-radius: 16px;
            padding: 16px 20px;
            text-align: center;
            border: 1px solid var(--border);
            transition: transform 0.2s;
        }
        
        .stat-card:hover { transform: translateY(-2px); }
        
        .stat-card .label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            color: var(--text-muted);
            margin-bottom: 6px;
        }
        
        .stat-card .value {
            font-size: clamp(1.2rem, 2.5vw, 1.8rem);
            font-weight: 700;
            color: var(--green);
        }
        
        .stat-card .value.accent { color: var(--accent); }
        .stat-card .value.warning { color: var(--yellow); }
        .stat-card .value.purple { color: var(--purple); }
        
        .panel {
            background: var(--card);
            border-radius: 16px;
            padding: 20px 24px;
            margin-bottom: 20px;
            border: 1px solid var(--border);
        }
        
        .panel h2 {
            font-size: 1rem;
            font-weight: 600;
            color: var(--accent);
            margin-bottom: 16px;
            letter-spacing: 0.5px;
        }
        
        .panel.pred-panel h2 { color: var(--purple); }
        
        .chart-wrapper {
            position: relative;
            height: 400px;
            width: 100%;
        }
        
        .chart-wrapper canvas {
            width: 100% !important;
            height: 100% !important;
        }
        
        .table-wrapper {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.78rem;
            min-width: 950px;
        }
        
        th {
            background: rgba(233, 69, 96, 0.15);
            padding: 10px 6px;
            text-align: center;
            font-weight: 600;
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            border-bottom: 2px solid rgba(233, 69, 96, 0.3);
            white-space: nowrap;
        }
        
        td {
            padding: 9px 6px;
            text-align: center;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
            font-size: 0.75rem;
        }
        
        tr:hover td { background: rgba(255,255,255,0.02); }
        
        .aqi-buena { color: var(--green); font-weight: 700; }
        .aqi-moderada { color: var(--yellow); font-weight: 700; }
        .aqi-mala { color: var(--orange); font-weight: 700; }
        .aqi-muy-mala { color: var(--red); font-weight: 700; }
        .aqi-peligrosa { color: #ff00ff; font-weight: 700; }
        
        .acierto-exacto { color: #00ff88; font-weight: 600; }
        .acierto-aprox { color: #ffcc00; font-weight: 600; }
        .acierto-regular { color: #ff8c00; font-weight: 600; }
        .acierto-fallo { color: #ff4444; font-weight: 600; }
        .acierto-sin-dato { color: #666666; }
        
        .pred-ayer { color: var(--purple); font-weight: 600; }
        .ubicacion-gps { color: #00ff88; font-weight: 600; }
        .ubicacion-ip { color: #ffcc00; }
        
        .leyenda-barras {
            display: flex;
            gap: 20px;
            justify-content: center;
            margin-bottom: 12px;
            font-size: 0.75rem;
            flex-wrap: wrap;
        }
        
        .leyenda-item { display: flex; align-items: center; gap: 6px; }
        
        .leyenda-color {
            width: 14px;
            height: 14px;
            border-radius: 3px;
            display: inline-block;
        }
        
        .footer {
            text-align: center;
            padding: 20px;
            font-size: 0.7rem;
            color: var(--text-muted);
            letter-spacing: 0.5px;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: var(--text-muted);
        }
        
        /* Predicciones futuras */
        .resumen-pred {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
            margin-bottom: 15px;
        }
        
        .resumen-item {
            background: rgba(167, 139, 250, 0.1);
            padding: 10px;
            border-radius: 8px;
            text-align: center;
        }
        
        .resumen-item .valor {
            font-size: 1.3rem;
            font-weight: 700;
            color: #a78bfa;
            display: block;
        }
        
        .resumen-item .label {
            font-size: 0.65rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .tabla-pred-24h {
            background: rgba(167, 139, 250, 0.05);
            border: 1px solid rgba(167, 139, 250, 0.2);
            border-radius: 12px;
            padding: 12px;
            margin-top: 15px;
        }
        
        .tabla-pred-24h h3 {
            font-size: 0.9rem;
            color: #a78bfa;
            margin-bottom: 10px;
        }
        
        .tabla-pred-24h table { min-width: 700px; }
        
        .tabla-pred-24h th {
            background: rgba(167, 139, 250, 0.15);
            border-bottom-color: rgba(167, 139, 250, 0.3);
        }
        
        .chart-pred-wrapper {
            position: relative;
            height: 300px;
            width: 100%;
            margin-top: 15px;
        }
        
        @media (max-width: 768px) {
            body { padding: 8px; }
            .panel { padding: 12px; }
            table { font-size: 0.7rem; }
            th, td { padding: 6px 4px; }
            .chart-wrapper { height: 300px; }
            .chart-pred-wrapper { height: 220px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Sistema Predictivo de Calidad del Aire</h1>
            <p class="subtitle">Raspberry Pi Pico WH + IA + BME280 + GPS | Actualizacion cada 30s</p>
        </div>
        
        <div class="status-grid">
            <div class="stat-card">
                <div class="label">AQI Predicho Ayer</div>
                <div class="value purple" id="aqiAyer">--</div>
            </div>
            <div class="stat-card">
                <div class="label">AQI Real Hoy</div>
                <div class="value" id="aqiReal">--</div>
            </div>
            <div class="stat-card">
                <div class="label">AQI Proximas 24h</div>
                <div class="value accent" id="aqiPred">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Dif. Ayer (Pred-Real)</div>
                <div class="value" id="difAyer" style="font-size:1.2rem;">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Ubicacion</div>
                <div class="value" id="ubiDato" style="font-size:1rem;">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Total Registros</div>
                <div class="value" id="totalReg">--</div>
            </div>
        </div>
        
        <!-- PANEL DE PREDICCIONES FUTURAS -->
        <div class="panel pred-panel">
            <h2>Predicciones para las proximas 24 horas</h2>
            <div class="resumen-pred" id="resumenPred">
                <div class="resumen-item">
                    <span class="valor">--</span>
                    <span class="label">Cargando...</span>
                </div>
            </div>
            
            <div class="chart-pred-wrapper">
                <canvas id="predChart"></canvas>
            </div>
            
            <div class="tabla-pred-24h">
                <h3 id="tituloPred24h">Predicciones hora a hora</h3>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Hora</th>
                                <th>AQI Predicho</th>
                                <th>PM2.5</th>
                                <th>PM10</th>
                                <th>NO2</th>
                                <th>O3</th>
                                <th>Categoria</th>
                            </tr>
                        </thead>
                        <tbody id="tablaPred24hBody">
                            <tr><td colspan="7" class="empty-state">Cargando predicciones...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- GRAFICO COMPARATIVO (MANTENIDO) -->
        <div class="panel">
            <h2>Comparativa AQI: Predicho Ayer vs Real Hoy vs Proximas 24h</h2>
            <div class="leyenda-barras">
                <div class="leyenda-item">
                    <span class="leyenda-color" style="background:rgba(167,139,250,0.85);"></span>
                    <span>Predicho Ayer</span>
                </div>
                <div class="leyenda-item">
                    <span class="leyenda-color" style="background:rgba(0,255,136,0.85);"></span>
                    <span>Real Hoy</span>
                </div>
                <div class="leyenda-item">
                    <span class="leyenda-color" style="background:rgba(233,69,96,0.85);"></span>
                    <span>Proximas 24h</span>
                </div>
            </div>
            <div class="chart-wrapper">
                <canvas id="aqiChart"></canvas>
            </div>
        </div>
        
        <!-- TABLA DE DATOS ORIGINAL (14 COLUMNAS) -->
        <div class="panel">
            <h2>Tabla de Datos</h2>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Hora</th>
                            <th>Fuente</th>
                            <th>Estacion</th>
                            <th>Ubicacion</th>
                            <th>PM2.5</th>
                            <th>PM10</th>
                            <th>T</th>
                            <th>H%</th>
                            <th>AQI Ayer Pred</th>
                            <th>AQI Real Hoy</th>
                            <th>AQI Prox 24h</th>
                            <th>Dif. Ayer</th>
                            <th>Acerto?</th>
                            <th>Categoria</th>
                        </tr>
                    </thead>
                    <tbody id="tablaBody">
                        <tr><td colspan="14" class="empty-state">Esperando datos del sensor...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="footer">
            TFM Sistema Predictivo de Contaminacion Atmosferica | Datos: WAQI + Open-Meteo + BME280 | GPS: LC79D
        </div>
    </div>
    
    <script>
        let chart = null;
        let predChart = null;
        
        function getAQIClass(valor) {
            if (valor === null || valor === undefined || valor === '-') return '';
            const v = parseFloat(valor);
            if (isNaN(v)) return '';
            if (v <= 50) return 'aqi-buena';
            if (v <= 100) return 'aqi-moderada';
            if (v <= 150) return 'aqi-mala';
            if (v <= 200) return 'aqi-muy-mala';
            return 'aqi-peligrosa';
        }
        
        function getCategoria(aqi) {
            const v = parseFloat(aqi);
            if (isNaN(v)) return '--';
            if (v <= 50) return 'Buena';
            if (v <= 100) return 'Moderada';
            if (v <= 150) return 'Mala';
            if (v <= 200) return 'Muy mala';
            return 'Peligrosa';
        }
        
        function getAciertoHTML(difAyer) {
            if (difAyer === null || difAyer === undefined || difAyer === '' || difAyer === '--') {
                return '<span class="acierto-sin-dato">Sin dato</span>';
            }
            const dif = parseFloat(difAyer);
            if (isNaN(dif)) return '<span class="acierto-sin-dato">--</span>';
            
            const absDif = Math.abs(dif);
            if (absDif <= 5) return '<span class="acierto-exacto">Excelente (' + (dif >= 0 ? '+' : '') + dif.toFixed(1) + ')</span>';
            if (absDif <= 10) return '<span class="acierto-aprox">Bueno (' + (dif >= 0 ? '+' : '') + dif.toFixed(1) + ')</span>';
            if (absDif <= 20) return '<span class="acierto-regular">Regular (' + (dif >= 0 ? '+' : '') + dif.toFixed(1) + ')</span>';
            return '<span class="acierto-fallo">Desviado (' + (dif >= 0 ? '+' : '') + dif.toFixed(1) + ')</span>';
        }
        
        function actualizarPanelPredicciones(ultimo) {
            const tbody = document.getElementById('tablaPred24hBody');
            const titulo = document.getElementById('tituloPred24h');
            const resumenDiv = document.getElementById('resumenPred');
            
            let predicciones = [];
            if (ultimo.predicciones_24h) {
                if (typeof ultimo.predicciones_24h === 'string') {
                    try { predicciones = JSON.parse(ultimo.predicciones_24h); } catch(e) { predicciones = []; }
                } else if (Array.isArray(ultimo.predicciones_24h)) {
                    predicciones = ultimo.predicciones_24h;
                }
            }
            
            if (predicciones.length === 0) {
                titulo.textContent = 'Sin predicciones disponibles';
                tbody.innerHTML = '<tr><td colspan="7" class="empty-state">El Pico aun no ha enviado predicciones de 24h</td></tr>';
                resumenDiv.innerHTML = '<div class="resumen-item"><span class="valor">--</span><span class="label">Sin datos</span></div>';
                return;
            }
            
            const aqis = predicciones.map(p => parseFloat(p.aqi));
            const aqiMax = Math.max(...aqis);
            const aqiMin = Math.min(...aqis);
            const aqiMedia = aqis.reduce((a, b) => a + b, 0) / aqis.length;
            const horaInicio = predicciones[0].hora ? predicciones[0].hora.substring(11, 16) : '--';
            const horaFin = predicciones[predicciones.length - 1].hora ? predicciones[predicciones.length - 1].hora.substring(11, 16) : '--';
            
            resumenDiv.innerHTML = 
                '<div class="resumen-item"><span class="valor">' + predicciones.length + '</span><span class="label">Horas</span></div>' +
                '<div class="resumen-item"><span class="valor">' + aqiMedia.toFixed(1) + '</span><span class="label">Media</span></div>' +
                '<div class="resumen-item"><span class="valor" style="color:#ff4444;">' + aqiMax.toFixed(1) + '</span><span class="label">Maximo</span></div>' +
                '<div class="resumen-item"><span class="valor" style="color:#00ff88;">' + aqiMin.toFixed(1) + '</span><span class="label">Minimo</span></div>' +
                '<div class="resumen-item"><span class="valor" style="font-size:0.9rem;">' + horaInicio + '</span><span class="label">Inicio</span></div>' +
                '<div class="resumen-item"><span class="valor" style="font-size:0.9rem;">' + horaFin + '</span><span class="label">Fin</span></div>';
            
            titulo.textContent = predicciones.length + ' horas de prediccion (' + horaInicio + ' a ' + horaFin + ')';
            
            let html = '';
            predicciones.forEach(p => {
                const hora = p.hora ? p.hora.substring(11, 16) : '--';
                const aqi = parseFloat(p.aqi).toFixed(1);
                const pm25 = parseFloat(p.pm25 || 0).toFixed(1);
                const pm10 = parseFloat(p.pm10 || 0).toFixed(1);
                const no2 = parseFloat(p.no2 || 0).toFixed(1);
                const o3 = parseFloat(p.o3 || 0).toFixed(1);
                const cat = getCategoria(aqi);
                
                html += '<tr>' +
                    '<td><strong>' + hora + '</strong></td>' +
                    '<td class="' + getAQIClass(aqi) + '">' + aqi + '</td>' +
                    '<td>' + pm25 + '</td>' +
                    '<td>' + pm10 + '</td>' +
                    '<td>' + no2 + '</td>' +
                    '<td>' + o3 + '</td>' +
                    '<td class="' + getAQIClass(aqi) + '">' + cat + '</td>' +
                    '</tr>';
            });
            tbody.innerHTML = html;
            
            // Grafico de predicciones
            const labels = predicciones.map(p => p.hora ? p.hora.substring(11, 16) : '--');
            const aqiData = predicciones.map(p => parseFloat(p.aqi));
            const pm25Data = predicciones.map(p => parseFloat(p.pm25 || 0));
            const pm10Data = predicciones.map(p => parseFloat(p.pm10 || 0));
            const o3Data = predicciones.map(p => parseFloat(p.o3 || 0));
            
            if (predChart) {
                predChart.data.labels = labels;
                predChart.data.datasets[0].data = aqiData;
                predChart.data.datasets[1].data = pm25Data;
                predChart.data.datasets[2].data = pm10Data;
                predChart.data.datasets[3].data = o3Data;
                predChart.update('none');
            } else {
                const ctx = document.getElementById('predChart').getContext('2d');
                predChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            { label: 'AQI Predicho', data: aqiData, borderColor: '#a78bfa', backgroundColor: 'rgba(167, 139, 250, 0.2)', borderWidth: 3, tension: 0.4, fill: true, yAxisID: 'y' },
                            { label: 'PM2.5', data: pm25Data, borderColor: '#00ff88', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5], tension: 0.4, yAxisID: 'y1' },
                            { label: 'PM10', data: pm10Data, borderColor: '#ffcc00', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5], tension: 0.4, yAxisID: 'y1' },
                            { label: 'O3', data: o3Data, borderColor: '#e94560', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5], tension: 0.4, yAxisID: 'y1' }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { intersect: false, mode: 'index' },
                        plugins: {
                            legend: { position: 'top', labels: { color: '#e2e8f0', font: { size: 10 }, usePointStyle: true, padding: 15 } }
                        },
                        scales: {
                            y: { type: 'linear', display: true, position: 'left', beginAtZero: true, title: { display: true, text: 'AQI', color: '#a78bfa' }, grid: { color: 'rgba(255,255,255,0.06)' }, ticks: { color: '#a78bfa', font: { size: 9 } } },
                            y1: { type: 'linear', display: true, position: 'right', beginAtZero: true, title: { display: true, text: 'Concentracion', color: '#94a3b8' }, grid: { drawOnChartArea: false }, ticks: { color: '#94a3b8', font: { size: 9 } } },
                            x: { grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#94a3b8', font: { size: 9 }, maxRotation: 45 } }
                        }
                    }
                });
            }
        }
        
        function actualizar() {
            fetch('/api/ultimos')
                .then(r => r.json())
                .then(d => {
                    if (!d || !d.ultimo || d.ultimo.length === 0) {
                        document.getElementById('tablaBody').innerHTML = 
                            '<tr><td colspan="14" class="empty-state">No hay datos todavia...</td></tr>';
                        return;
                    }
                    
                    const ultimo = d.ultimo[0];
                    
                    // Tarjetas superiores
                    const aqiAyerVal = (ultimo.aqi_predicho_ayer !== null && ultimo.aqi_predicho_ayer !== undefined) ? parseFloat(ultimo.aqi_predicho_ayer).toFixed(1) : '--';
                    const aqiRealVal = ultimo.aqi_real ? parseFloat(ultimo.aqi_real).toFixed(1) : '--';
                    const aqiPredVal = ultimo.aqi_predicho ? parseFloat(ultimo.aqi_predicho).toFixed(1) : '--';
                    const difAyerVal = (ultimo.diferencia_ayer !== null && ultimo.diferencia_ayer !== undefined) ? parseFloat(ultimo.diferencia_ayer).toFixed(1) : '--';
                    const ubiVal = (ultimo.ubicacion || ultimo.region || '--');
                    
                    document.getElementById('aqiAyer').textContent = aqiAyerVal;
                    document.getElementById('aqiReal').textContent = aqiRealVal;
                    document.getElementById('aqiPred').textContent = aqiPredVal;
                    document.getElementById('difAyer').textContent = difAyerVal !== '--' ? (parseFloat(difAyerVal) >= 0 ? '+' : '') + difAyerVal : '--';
                    document.getElementById('ubiDato').textContent = ubiVal;
                    document.getElementById('totalReg').textContent = d.total || 0;
                    
                    const ubiEl = document.getElementById('ubiDato');
                    if (ubiVal === 'GPS') ubiEl.className = 'value ubicacion-gps';
                    else ubiEl.className = 'value ubicacion-ip';
                    
                    const difAyerNum = parseFloat(difAyerVal);
                    const difAyerEl = document.getElementById('difAyer');
                    if (!isNaN(difAyerNum)) {
                        if (Math.abs(difAyerNum) <= 5) difAyerEl.style.color = '#00ff88';
                        else if (Math.abs(difAyerNum) <= 10) difAyerEl.style.color = '#ffcc00';
                        else if (Math.abs(difAyerNum) <= 20) difAyerEl.style.color = '#ff8c00';
                        else difAyerEl.style.color = '#ff4444';
                    }
                    
                    document.getElementById('aqiReal').className = 'value ' + getAQIClass(ultimo.aqi_real);
                    document.getElementById('aqiPred').className = 'value accent ' + getAQIClass(ultimo.aqi_predicho);
                    
                    // TABLA PRINCIPAL (14 columnas - VERSION ORIGINAL)
                    let tablaHtml = '';
                    d.ultimo.forEach(r => {
                        const hora = (r.timestamp_str || r.timestamp_servidor || '--').substring(11, 16);
                        const aqiAyer = (r.aqi_predicho_ayer !== null && r.aqi_predicho_ayer !== undefined) ? parseFloat(r.aqi_predicho_ayer).toFixed(1) : '--';
                        const aqiReal = r.aqi_real || 0;
                        const aqiPred = parseFloat(r.aqi_predicho || 0).toFixed(1);
                        const difAyer = (r.diferencia_ayer !== null && r.diferencia_ayer !== undefined) ? parseFloat(r.diferencia_ayer).toFixed(1) : '--';
                        const temp = parseFloat(r.temperatura || 0).toFixed(1);
                        const hum = parseFloat(r.humedad || 0).toFixed(0);
                        const ubicacion = r.ubicacion || '--';
                        const aciertoHTML = getAciertoHTML(difAyer);
                        
                        let difAyerColor = '#ffffff';
                        const difAyerNum = parseFloat(difAyer);
                        if (!isNaN(difAyerNum)) {
                            if (Math.abs(difAyerNum) <= 5) difAyerColor = '#00ff88';
                            else if (Math.abs(difAyerNum) <= 10) difAyerColor = '#ffcc00';
                            else if (Math.abs(difAyerNum) <= 20) difAyerColor = '#ff8c00';
                            else difAyerColor = '#ff4444';
                        }
                        
                        let ubiClass = ubicacion === 'GPS' ? 'ubicacion-gps' : 'ubicacion-ip';
                        
                        tablaHtml += '<tr>' +
                            '<td>' + hora + '</td>' +
                            '<td>' + (r.fuente || '--') + '</td>' +
                            '<td style="max-width:100px;overflow:hidden;text-overflow:ellipsis;">' + ((r.estacion || '--').substring(0, 14)) + '</td>' +
                            '<td class="' + ubiClass + '">' + ubicacion + '</td>' +
                            '<td>' + (r.pm25 || 0) + '</td>' +
                            '<td>' + (r.pm10 || 0) + '</td>' +
                            '<td>' + temp + 'C</td>' +
                            '<td>' + hum + '%</td>' +
                            '<td class="pred-ayer">' + aqiAyer + '</td>' +
                            '<td class="' + getAQIClass(aqiReal) + '">' + aqiReal + '</td>' +
                            '<td class="' + getAQIClass(aqiPred) + '">' + aqiPred + '</td>' +
                            '<td style="color:' + difAyerColor + ';font-weight:600;">' + (difAyer !== '--' ? (parseFloat(difAyer) >= 0 ? '+' : '') + difAyer : '--') + '</td>' +
                            '<td>' + aciertoHTML + '</td>' +
                            '<td class="' + getAQIClass(aqiReal) + '">' + (r.categoria || '--') + '</td>' +
                            '</tr>';
                    });
                    document.getElementById('tablaBody').innerHTML = tablaHtml;
                    
                    // Actualizar panel de predicciones futuras
                    actualizarPanelPredicciones(ultimo);
                    
                    // GRAFICO COMPARATIVO DE BARRAS
                    const datos = [...d.ultimo].reverse();
                    const labels = datos.map(r => {
                        const ts = r.timestamp_str || r.timestamp_servidor || '';
                        return ts.substring(11, 16);
                    });
                    const aqiRealArr = datos.map(r => r.aqi_real || 0);
                    const aqiPredArr = datos.map(r => r.aqi_predicho || 0);
                    const aqiAyerArr = datos.map(r => 
                        (r.aqi_predicho_ayer !== null && r.aqi_predicho_ayer !== undefined) ? r.aqi_predicho_ayer : null);
                    
                    if (chart) {
                        chart.data.labels = labels;
                        chart.data.datasets[0].data = aqiAyerArr;
                        chart.data.datasets[1].data = aqiRealArr;
                        chart.data.datasets[2].data = aqiPredArr;
                        chart.update('none');
                    } else {
                        const ctx = document.getElementById('aqiChart').getContext('2d');
                        chart = new Chart(ctx, {
                            type: 'bar',
                            data: {
                                labels: labels,
                                datasets: [
                                    { label: 'AQI Predicho Ayer', data: aqiAyerArr, backgroundColor: 'rgba(167, 139, 250, 0.85)', borderColor: '#a78bfa', borderWidth: 1, borderRadius: 6, borderSkipped: false },
                                    { label: 'AQI Real Hoy', data: aqiRealArr, backgroundColor: 'rgba(0, 255, 136, 0.85)', borderColor: '#00ff88', borderWidth: 1, borderRadius: 6, borderSkipped: false },
                                    { label: 'AQI Proximas 24h', data: aqiPredArr, backgroundColor: 'rgba(233, 69, 96, 0.85)', borderColor: '#e94560', borderWidth: 1, borderRadius: 6, borderSkipped: false }
                                ]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                interaction: { intersect: false, mode: 'index' },
                                plugins: {
                                    legend: { position: 'top', labels: { color: '#e2e8f0', font: { size: 10 }, usePointStyle: true, padding: 20 } },
                                    tooltip: { callbacks: { label: function(ctx) { if (ctx.raw === null) return ctx.dataset.label + ': Sin dato'; return ctx.dataset.label + ': ' + ctx.raw.toFixed(1); } } }
                                },
                                scales: {
                                    y: { beginAtZero: true, max: 120, title: { display: true, text: 'AQI', color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.06)' }, ticks: { color: '#94a3b8', font: { size: 9 } } },
                                    x: { title: { display: true, text: 'Hora', color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#94a3b8', font: { size: 9 }, maxRotation: 45 } }
                                }
                            }
                        });
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('tablaBody').innerHTML = 
                        '<tr><td colspan="14" class="empty-state">Error al cargar datos</td></tr>';
                });
        }
        
        actualizar();
        setInterval(actualizar, 30000);
    </script>
</body>
</html>
"""

# ==================== RUTAS ====================

@app.route('/')
def panel():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/ultimos', methods=['GET'])
def obtener_ultimos():
    """Devuelve los ultimos 20 registros con predicciones de 24h"""
    try:
        if os.path.exists(ARCHIVO_CSV):
            df = pd.read_csv(ARCHIVO_CSV, encoding='utf-8-sig')
            print(f"[API] CSV leido: {len(df)} registros")
        elif os.path.exists(ARCHIVO_EXCEL):
            df = pd.read_excel(ARCHIVO_EXCEL, engine='openpyxl')
            print(f"[API] Excel leido: {len(df)} registros")
        else:
            return jsonify({"ultimo": [], "total": 0, "success": True})
        
        if len(df) == 0:
            return jsonify({"ultimo": [], "total": 0, "success": True})
        
        col_fecha = 'timestamp_str' if 'timestamp_str' in df.columns else 'timestamp_servidor'
        df['fecha_orden'] = pd.to_datetime(df[col_fecha], errors='coerce')
        df = df.dropna(subset=['fecha_orden'])
        df = df.sort_values('fecha_orden', ascending=False)
        
        ultimos = df.head(20).to_dict(orient='records')
        
        for reg in ultimos:
            if 'aqi_predicho_ayer' in reg and reg['aqi_predicho_ayer'] is not None and pd.notna(reg.get('aqi_predicho_ayer')):
                if 'diferencia_ayer' not in reg or reg.get('diferencia_ayer') is None or pd.isna(reg.get('diferencia_ayer')):
                    reg['diferencia_ayer'] = round(float(reg.get('aqi_real', 0)) - float(reg['aqi_predicho_ayer']), 1)
            else:
                ts = reg.get('timestamp_servidor') or reg.get('timestamp_str')
                if ts and pd.notna(ts):
                    pred_anterior = buscar_prediccion_24h_anterior(ts)
                    if pred_anterior:
                        reg['aqi_predicho_ayer'] = pred_anterior['aqi_predicho_ayer']
                        reg['fecha_pred_ayer'] = pred_anterior['fecha_pred_ayer']
                        reg['dif_horas_ayer'] = pred_anterior['dif_horas_ayer']
                        reg['diferencia_ayer'] = round(float(reg.get('aqi_real', 0)) - pred_anterior['aqi_predicho_ayer'], 1)
                    else:
                        reg['aqi_predicho_ayer'] = None
                        reg['fecha_pred_ayer'] = None
                        reg['dif_horas_ayer'] = None
                        reg['diferencia_ayer'] = None
                else:
                    reg['aqi_predicho_ayer'] = None
                    reg['fecha_pred_ayer'] = None
                    reg['dif_horas_ayer'] = None
                    reg['diferencia_ayer'] = None
            
            for key in list(reg.keys()):
                if key not in ['fecha_pred_ayer', 'fecha_orden', 'predicciones_24h']:
                    reg[key] = limpiar_valor(reg[key], 0 if key not in ['categoria', 'fuente', 'estacion', 'ubicacion', 'region'] else '')
            
            if 'predicciones_24h' in reg:
                reg['predicciones_24h'] = parsear_predicciones_24h(reg['predicciones_24h'])
            else:
                reg['predicciones_24h'] = []
        
        print(f"[API] {len(ultimos)} registros devueltos")
        
        return jsonify({
            "ultimo": ultimos, 
            "total": len(df), 
            "success": True
        })
    except Exception as e:
        print(f"[API] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ultimo": [], "total": 0, "success": False})

@app.route('/api/datos', methods=['POST'])
def recibir_datos():
    global ultimo_registro
    
    raw = request.get_data(as_text=True)
    
    try:
        datos = request.get_json(force=True, silent=True)
        if datos is None:
            datos = json.loads(raw)
        
        if datos is None:
            return jsonify({"status": "error", "msg": "JSON invalido"}), 400
        
        datos['timestamp_servidor'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for key, value in list(datos.items()):
            if key == 'predicciones_24h':
                continue
            if value is None or value == 'None' or value == '':
                datos[key] = 0 if key not in ['categoria', 'fuente', 'estacion', 'ubicacion', 'region'] else ''
            elif isinstance(value, float) and (pd.isna(value) or np.isinf(value)):
                datos[key] = 0
        
        # Convertir predicciones_24h a string JSON para el CSV
        if 'predicciones_24h' in datos and isinstance(datos['predicciones_24h'], list):
            datos['predicciones_24h'] = json.dumps(datos['predicciones_24h'])
        
        # Filtrar AQI Real extremo
        aqi_real_val = float(datos.get('aqi_real', 0) or 0)
        if aqi_real_val > 200:
            print(f"   [WARN] AQI real anomalo ({aqi_real_val}), limitando a 200")
            datos['aqi_real'] = 200
            if datos.get('categoria'):
                datos['categoria'] = 'Muy mala' if aqi_real_val > 150 else 'Moderada'
        
        ts_actual = datos.get('timestamp_str') or datos.get('timestamp_servidor')
        if ts_actual:
            pred_ayer = buscar_prediccion_24h_anterior(ts_actual)
            if pred_ayer:
                datos['aqi_predicho_ayer'] = pred_ayer['aqi_predicho_ayer']
                datos['fecha_pred_ayer'] = pred_ayer.get('fecha_pred_ayer', '')
                datos['dif_horas_ayer'] = pred_ayer.get('dif_horas_ayer', 0)
                datos['diferencia_ayer'] = round(float(datos.get('aqi_real', 0)) - pred_ayer['aqi_predicho_ayer'], 1)
                print(f"   [PRED AYER] Ayer predijo: {pred_ayer['aqi_predicho_ayer']} | Hoy real: {datos.get('aqi_real')} | Dif: {datos['diferencia_ayer']}")
            else:
                datos['aqi_predicho_ayer'] = None
                datos['fecha_pred_ayer'] = None
                datos['dif_horas_ayer'] = None
                datos['diferencia_ayer'] = None
        else:
            datos['aqi_predicho_ayer'] = None
            datos['fecha_pred_ayer'] = None
            datos['dif_horas_ayer'] = None
            datos['diferencia_ayer'] = None
        
        ultimo_registro = datos
        df_nuevo = pd.DataFrame([datos])
        
        if os.path.exists(ARCHIVO_CSV):
            df_existente = pd.read_csv(ARCHIVO_CSV, encoding='utf-8-sig')
            df_existente = df_existente.dropna(axis=1, how='all')
            df_nuevo = df_nuevo.dropna(axis=1, how='all')
            df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
        else:
            df_final = df_nuevo
        
        df_final.to_csv(ARCHIVO_CSV, index=False, encoding='utf-8-sig')
        df_final.to_excel(ARCHIVO_EXCEL, index=False, engine='openpyxl')
        
        pred_count = 0
        if 'predicciones_24h' in datos:
            try:
                pred_count = len(json.loads(datos['predicciones_24h']) if isinstance(datos['predicciones_24h'], str) else datos['predicciones_24h'])
            except:
                pred_count = 0
        
        print(f"[POST] {datos.get('timestamp_str','?')} | {datos.get('fuente','?')} | AQI:{datos.get('aqi_real')} | Pred:{pred_count}")
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        print(f"[POST] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "msg": str(e)}), 500

@app.route('/api/estado', methods=['GET'])
def estado():
    return jsonify({"ultimo_registro": ultimo_registro})

@app.route('/api/todos', methods=['GET'])
def ver_todos():
    if os.path.exists(ARCHIVO_CSV):
        df = pd.read_csv(ARCHIVO_CSV, encoding='utf-8-sig')
        return jsonify(df.to_dict(orient='records'))
    return jsonify([])

if __name__ == '__main__':
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip_pc = s.getsockname()[0]
        print(f"IP del PC: {ip_pc}")
        print(f"En la Pico usa: PC_IP = \"{ip_pc}\"")
    except:
        pass
    s.close()
    
    print("=" * 60)
    print("Panel web: http://localhost:5001")
    print("=" * 60)
    print("Servidor iniciado - Esperando datos del Pico W...")
    print("=" * 60)
    
    threading.Thread(target=lambda: webbrowser.open('http://localhost:5001'), daemon=True).start()
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)