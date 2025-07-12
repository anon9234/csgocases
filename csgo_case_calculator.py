#!/usr/bin/env python3
"""
CS:GO Case Calculator – HTML+JS‑Frontend + Flask‑API
(rev. 2025‑07‑11‑DMY‑IMG‑FIX‑STATS)

Adds prominent investment/return KPIs next to the hero image
------------------------------------------------------------
* **Investiert** – constant 269 ,56 €
* **Kursgewinn** – *dynamic*: (current grand_total − 269 ,56 €)
  *bold & green*
* **Realisiert** – constant 3 935 ,02 € (smaller but also green)

The JS now calculates and updates *Kursgewinn* on every refresh.
All other behaviour unchanged.
"""

from __future__ import annotations

import glob
import json
import os
import time
from datetime import datetime
from urllib.parse import quote

import requests
from flask import Flask, Response, jsonify, render_template_string, request

app = Flask(__name__)  # Flask serves files under /static automatically

# ----------------------------- CONFIG -----------------------------
INVENTORY: dict[str, int] = {
    "Horizon Case": 1000,
    "Danger Zone Case": 1000,
    "Prisma Case": 1000,
    "Spectrum 2 Case": 150,
    "Clutch Case": 649,
    "Falchion Case": 142,
    "Operation Breakout Weapon Case": 100,
}

SNAPSHOT_DIR   = "snapshots"  
CACHE_FILE = "price_cache.json"
CACHE_TTL = 3600  # seconds
SNAPSHOT_GLOB  = os.path.join(SNAPSHOT_DIR, "csgo_snapshot_*.json")

# Static KPI values (EUR)
INVESTED_EUR = 269.56
REALIZED_EUR = 3935.02

# ----------------------------- CACHE -----------------------------

def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache: dict) -> None:
    tmp = f"{CACHE_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CACHE_FILE)

# ----------------------------- PRICE FETCH -----------------------------

def fetch_price_eur(item_name: str, cache: dict) -> float | None:
    now = time.time()
    if (entry := cache.get(item_name)) and now - entry["ts"] < CACHE_TTL:
        return entry["price_eur"]

    url = (
        "https://steamcommunity.com/market/priceoverview/"
        f"?currency=3&appid=730&market_hash_name={quote(item_name)}"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        price_raw = data.get("lowest_price") or data.get("median_price")
        if not price_raw:
            raise ValueError("keine Preisangabe von Steam erhalten")
        price_eur = float(price_raw.replace("€", "").replace(" ", "").replace(",", "."))
        cache[item_name] = {"price_eur": price_eur, "ts": now}
        return price_eur
    except Exception as exc:
        print(f"[warn] {item_name}: {exc}")
        return None

# ----------------------------- API ENDPOINTS -----------------------------

@app.route("/api/prices")
def api_prices():
    cache = _load_cache()
    items: list[dict] = []
    grand_total = 0.0

    for name, count in INVENTORY.items():
        price = fetch_price_eur(name, cache)
        total = round(price * count, 2) if price is not None else None
        if total is not None:
            grand_total += total
        items.append({"name": name, "count": count, "price": price, "total": total})

    _save_cache(cache)

    resp_data = {"items": items, "grand_total": round(grand_total, 2)}
    if request.args.get("store") == "1":
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        filename  = f"csgo_snapshot_{time.strftime('%Y%m%d_%H%M%S')}.json"
        filepath  = os.path.join(SNAPSHOT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(resp_data, f, ensure_ascii=False, indent=2)
        resp_data.update({"saved": True, "filename": filename})

    return jsonify(resp_data)


@app.route("/api/history")
def api_history():
    history: list[dict] = []
    for path in sorted(glob.glob(SNAPSHOT_GLOB)):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ts_str = os.path.basename(path)[len("csgo_snapshot_"):-5]
            ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            history.append({"ts": ts.strftime("%Y-%m-%d %H:%M"), "grand_total": data["grand_total"]})
        except Exception as exc:
            print(f"[warn] history: {path}: {exc}")
    return jsonify({"history": history})

# ----------------------------- FRONTEND -----------------------------
HTML_TEMPLATE = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>CS:GO Case Calculator</title>
  <link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css\" rel=\"stylesheet\">
  <script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>
  <script src=\"https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns/dist/chartjs-adapter-date-fns.bundle.min.js\"></script>
  <style>
    body { background:#1e1e1e; color:#ddd; }
    h1, h3 { color:#fff; text-align:center; }
    .table-dark th,.table-dark td{vertical-align:middle}
    #histChart{max-height:300px}
    #histChart {
    background-color: #2c2c2c; /* dunkles Anthrazit */
    border-radius: 1rem;
    box-shadow: 0 0 10px rgba(0,0,0,0.5);
}
  </style>
</head>
<body>
<div class=\"container py-4\">
  <h1 class=\"mb-4\">CS:GO Case Calculator</h1>

  <!-- Hero row with image and KPIs -->
  <div class="row align-items-center g-4 mb-4 text-center text-lg-start">
    
    <!-- Linkes Bild -->
    <div class="col-lg-4 text-center">
      <img src="/static/caseking1.png" alt="Case King of Counter-Strike" class="img-fluid" style="max-height:300px">
    </div>

    <!-- Mittlere Spalte: KPIs -->
    <div class="col-lg-4 d-flex flex-column align-items-center">
      <h2 class="mb-3 text-light text-center">Investiert: <span id="invested" class="text-info">269,56&nbsp;€</span></h2>
      <h2 class="text-center">Realisiert: <span id="realized" class="text-success">3935,02 €</span></h4>    
      <h2 class="fw-bold mb-3 text-center">Kursgewinn: <span id="gain" class="text-success">…</span></h2>
    </div>

    <!-- Rechtes Bild -->
    <div class="col-lg-4 text-center">
      <img src="/static/caseking2.png" alt="Anderes Bild" class="img-fluid" style="max-height:300px">
    </div>

  </div>


  <table class=\"table table-dark table-hover rounded overflow-hidden shadow\" id=\"casesTbl\">
    <thead class=\"table-secondary text-dark\">
      <tr>
        <th>Case Name</th>
        <th class=\"text-end\">Count</th>
        <th class=\"text-end\">Price (€)</th>
        <th class=\"text-end\">Total (€)</th>
      </tr>
    </thead>
    <tbody></tbody>
    <tfoot>
      <tr>
        <th colspan=\"3\" class=\"text-end\">Grand Total</th>
        <th class=\"text-end\" id=\"grandTot\">…</th>
      </tr>
    </tfoot>
  </table>

  <div class=\"d-flex gap-2 mb-4\">
    <button class=\"btn btn-primary\" onclick=\"loadData()\">🔄 Aktualisieren</button>
    <button class=\"btn btn-success\" onclick=\"saveSnapshot()\">💾 Snapshot speichern</button>
  </div>

  <h3 class=\"mt-5\">Historischer Gesamtwert</h3>
  <canvas id="histChart"></canvas>
</div>

<script>
const INVESTED = 269.56;
const REALIZED = 3935.02;

document.getElementById('invested').textContent = INVESTED.toLocaleString('de-DE', { minimumFractionDigits: 2 }) + ' €';
document.getElementById("realized").innerText = "3.935,02 €";

function fmtEUR(x){
  return x===null? '—' : x.toLocaleString('de-DE', {minimumFractionDigits:2}) + ' €';
}

async function loadData(){
  const res = await fetch('/api/prices');
  const data = await res.json();

  // --- update table ---
  const tbody = document.querySelector('#casesTbl tbody');
  tbody.innerHTML = '';
  data.items.forEach(it => {
    const row = `<tr>
      <td>${it.name}</td>
      <td class='text-end'>${it.count}</td>
      <td class='text-end'>${fmtEUR(it.price)}</td>
      <td class='text-end'>${fmtEUR(it.total)}</td>`;
    tbody.insertAdjacentHTML('beforeend', row);
  });
  document.getElementById('grandTot').textContent = fmtEUR(data.grand_total);

  // --- update KPIs ---
  const gain = data.grand_total - INVESTED;
  document.getElementById('gain').textContent = gain.toLocaleString('de-DE', { minimumFractionDigits: 2 }) + ' €';

  loadHistory();
}

async function saveSnapshot(){
  const res = await fetch('/api/prices?store=1');
  const data = await res.json();
  if(data.saved){
    alert('Snapshot gespeichert als '+data.filename);
    loadHistory();
  }else{
    alert('Fehler beim Speichern des Snapshots');
  }
}

let histChart = null;
async function loadHistory(){
  const res = await fetch('/api/history');
  const data = await res.json();
  if(!data.history.length){return;}

  const labels = data.history.map(h => new Date(h.ts.replace(' ', 'T')+':00'));
  const values = data.history.map(h => h.grand_total);
  const deltas = values.map((v,i)=> i ? v - values[i-1] : null);
  const gaps   = labels.map((ts,i)=> i ? (ts - labels[i-1]) / 60000 : null);

  const canvas = document.getElementById('histChart');
  if(histChart){ histChart.destroy(); }
  const ctx = canvas.getContext('2d');
  const gradient = ctx.createLinearGradient(0,0,0,canvas.clientHeight);
  gradient.addColorStop(0,'rgba(13,110,253,0.4)');
  gradient.addColorStop(1,'rgba(13,110,253,0)');

  histChart = new Chart(ctx, {
    type:'line',
    data:{labels:labels,datasets:[{label:'Grand Total (€)',data:values,fill:true,backgroundColor:gradient,borderColor:'#0d6efd',borderWidth:2,pointRadius:4,pointHoverRadius:5,tension:0.3}]},
    options:{
      maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      plugins:{
        legend:{display:false},
        tooltip:{
          callbacks:{
            label:(ctx)=> '€ '+ctx.formattedValue.replace('.',','),
            afterBody:(items)=>{
              const i = items[0].dataIndex;
              if(i===0) return '';
              const delta = deltas[i];
              const gapMin = gaps[i];
              const sign = delta>=0? '+':'';
              const pct = ((delta/values[i-1])*100).toFixed(2);
              const hrs = Math.floor(gapMin/60);
              const mins = Math.round(gapMin%60);
              return [`Δ: ${sign}${delta.toFixed(2).replace('.',',')} € (${sign}${pct.replace('.',',')}%)`, `Intervall: ${hrs}h ${mins}m`];
            }
          }
        }
      },
      scales:{
        x:{type:'time',time:{unit:'hour',tooltipFormat:'dd.MM.yyyy HH:mm',displayFormats:{hour:'dd.MM'}},grid:{display:false},ticks:{color:'#999'}},
        y:{beginAtZero:false,grid:{color:'rgba(255,255,255,0.1)'},ticks:{callback:(v)=> v.toFixed(0)+' €'}}
      }
    }
  });
}

window.addEventListener('DOMContentLoaded', ()=>{ loadData(); });
</script>
</body>
</html>"""

# ----------------------------- ROUTES -----------------------------

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

# ----------------------------- MAIN -----------------------------
if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5000)))
