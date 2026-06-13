import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from openai import OpenAI
from datetime import datetime
import json

def get_weather(city, api_key):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}
    current = requests.get(url, params=params).json()
    return {
        "city": current["name"],
        "temperature": round(current["main"]["temp"]),
        "feels_like": round(current["main"]["feels_like"]),
        "description": current["weather"][0]["description"].title(),
        "humidity": current["main"]["humidity"],
        "wind_speed": round(current["wind"]["speed"]),
    }

def get_forecast(city, api_key):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city, "appid": api_key, "units": "metric", "cnt": 8}
    data = requests.get(url, params=params).json()
    slots = []
    for item in data["list"]:
        dt = datetime.fromtimestamp(item["dt"])
        hour = dt.hour
        label = dt.strftime("%I%p").lstrip("0").lower()
        slots.append({
            "label": label,
            "hour": hour,
            "temp": round(item["main"]["temp"]),
            "feels": round(item["main"]["feels_like"]),
            "rain": int(item.get("pop", 0) * 100),
            "hum": item["main"]["humidity"],
            "wind": round(item["wind"]["speed"]),
            "desc": item["weather"][0]["description"].title(),
        })
    return slots

def get_namaz_times(city):
    url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Pakistan&method=1"
    response = requests.get(url).json()
    timings = response['data']['timings']
    for key, value in timings.items():
        clean_time = value.split(" ")[0]
        try:
            time_obj = datetime.strptime(clean_time, "%H:%M")
            timings[key] = time_obj.strftime("%I:%M %p").lstrip("0")
        except Exception:
            pass
    return timings

def get_groq_advice(weather, forecast, groq_key):
    client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
    temps = [s['temp'] for s in forecast]
    rains = [s['rain'] for s in forecast]
    prompt = f"""
You are a concise morning weather assistant for {weather['city']}, Pakistan.
Write exactly 3 sections separated by ###. No titles. Plain text only. 2-3 sentences each.

Current: {weather['temperature']}C, {weather['description']}, humidity {weather['humidity']}%
Today's temp range: {min(temps)}C to {max(temps)}C
Max rain chance: {max(rains)}%

1. Weather summary for the full day.
2. What to wear and prep.
3. One powerful motivational sentence.

Example:
Today starts cool but heats up fast...
###
Wear a light cotton shirt...
###
Every hour is a chance to do something great.
"""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def build_html_email(weather, forecast, namaz, advice, sender_email):
    today_full  = datetime.now().strftime("%A, %B %d · %Y")
    today_short = datetime.now().strftime("%d %b %Y")
    current_hour = datetime.now().hour

    sections   = [s.strip() for s in advice.split('###')]
    summary    = sections[0] if len(sections) > 0 else "Enjoy the weather today!"
    outfit     = sections[1] if len(sections) > 1 else "Dress comfortably."
    motivation = sections[2] if len(sections) > 2 else "Have a great day!"

    desc = weather['description'].lower()
    if   'rain'    in desc: w_icon = "&#127783;"
    elif 'thunder' in desc: w_icon = "&#9928;"
    elif 'cloud'   in desc: w_icon = "&#9729;"
    elif 'clear'   in desc: w_icon = "&#9728;"
    elif 'snow'    in desc: w_icon = "&#10052;"
    elif 'haze'    in desc or 'fog' in desc: w_icon = "&#127787;"
    else:                   w_icon = "&#127780;"

    mailto = "mailto:" + sender_email + "?subject=Re%3A%20Your%20Daily%20Weather%20%26%20Schedule%20App"
    forecast_json = json.dumps(forecast)
    current_hour_js = str(current_hour)

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{background:#f5f5f7;font-family:'Inter',-apple-system,sans-serif;-webkit-font-smoothing:antialiased;padding:24px 12px 48px;color:#111;}
.wrap{max-width:560px;margin:0 auto;}
.meta{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;padding:0 2px;}
.meta-l{font-size:11px;color:#999;font-weight:500;letter-spacing:.08em;text-transform:uppercase;}
.meta-r{font-size:11px;color:#999;}
.card{background:#fff;border-radius:20px;border:1px solid #e8e8e8;overflow:hidden;box-shadow:0 2px 24px rgba(0,0,0,0.06);}
.divider{height:1px;background:#f0f0f0;}
.sec-label{font-size:10px;color:#aaa;font-weight:600;letter-spacing:.14em;text-transform:uppercase;margin-bottom:14px;}

/* HERO */
.hero{padding:28px 24px 20px;display:flex;justify-content:space-between;align-items:flex-start;}
.hero-left{}
.city{font-size:13px;color:#999;margin-bottom:8px;font-weight:400;}
.temp{font-size:72px;font-weight:600;color:#111;line-height:1;letter-spacing:-3px;}
.temp sup{font-size:28px;color:#aaa;font-weight:300;vertical-align:super;}
.desc{font-size:15px;color:#555;margin-top:10px;font-weight:400;}
.feels{font-size:12px;color:#aaa;margin-top:3px;}
.hero-icon{font-size:48px;opacity:.6;padding-top:6px;}

/* PILLS */
.pills{padding:0 24px 20px;display:flex;gap:8px;flex-wrap:wrap;}
.pill{display:inline-flex;align-items:center;gap:6px;background:#f7f7f7;border:1px solid #ebebeb;border-radius:20px;padding:6px 12px;font-size:12px;color:#444;}
.pill-lbl{color:#aaa;font-size:11px;}

/* CHART */
.chart-wrap{padding:20px 24px 8px;}
canvas{display:block;width:100%;cursor:pointer;}
.hour-detail{margin-top:12px;padding:14px 16px;background:#f7f7f7;border-radius:12px;display:flex;gap:20px;align-items:center;}
.hd-time{font-size:22px;font-weight:600;color:#6366F1;min-width:48px;}
.hd-grid{display:grid;grid-template-columns:1fr 1fr;gap:4px 20px;flex:1;}
.hd-item{display:flex;gap:5px;align-items:center;}
.hd-lbl{font-size:11px;color:#aaa;}
.hd-val{font-size:13px;font-weight:500;color:#111;}
.chart-hint{font-size:10px;color:#ccc;text-align:center;margin:8px 0 20px;}

/* PRAYER */
.prayer-wrap{padding:20px 24px;}
.prayer-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px 8px;}
.prayer-cell{}
.p-name{font-size:10px;color:#aaa;text-transform:uppercase;letter-spacing:.1em;margin-bottom:3px;}
.p-time{font-size:15px;font-weight:500;color:#111;}

/* AI BRIEF */
.brief-wrap{padding:20px 24px;}
.brief-row{display:flex;gap:12px;align-items:flex-start;margin-bottom:14px;}
.brief-row:last-child{margin-bottom:0;}
.b-icon{width:28px;height:28px;background:#f3f3f3;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0;}
.b-inner{}
.b-lbl{font-size:10px;color:#aaa;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px;}
.b-text{font-size:14px;color:#444;line-height:1.65;font-weight:300;}
.motivate{background:#fafafa;border-left:2px solid #6366F1;border-radius:0 10px 10px 0;padding:12px 16px;font-size:13px;color:#555;font-style:italic;line-height:1.6;}

/* CTA */
.cta-wrap{padding:8px 24px 24px;text-align:center;}
.cta-btn{display:inline-block;background:#6366F1;color:#fff !important;text-decoration:none !important;font-size:13px;font-weight:500;padding:12px 32px;border-radius:10px;letter-spacing:.01em;}
.cta-hint{font-size:11px;color:#bbb;margin-top:8px;}

/* FOOTER */
.footer{padding:14px 24px;border-top:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center;}
.f-left{font-size:10px;color:#ccc;font-family:monospace;}
.f-right{font-size:11px;color:#bbb;}
.f-right span{color:#6366F1;font-weight:500;}
.bottom{text-align:center;margin-top:16px;font-size:10px;color:#ccc;letter-spacing:.12em;text-transform:uppercase;}
</style>
</head>
<body>
<div class="wrap">
  <div class="meta">
    <span class="meta-l">TOPBAR_DATE</span>
    <span class="meta-r">Islamabad &middot; Pakistan</span>
  </div>

  <div class="card">

    <!-- HERO -->
    <div class="hero">
      <div class="hero-left">
        <div class="city">Islamabad</div>
        <div class="temp">TEMPERATURE<sup>&deg;</sup></div>
        <div class="desc">DESCRIPTION</div>
        <div class="feels">feels like FEELS_LIKE&deg;C</div>
      </div>
      <div class="hero-icon">WEATHER_ICON</div>
    </div>

    <!-- PILLS -->
    <div class="pills">
      <div class="pill"><span class="pill-lbl">Humidity</span>HUMIDITY%</div>
      <div class="pill"><span class="pill-lbl">Wind</span>WIND m/s</div>
      <div class="pill"><span class="pill-lbl">Rain</span>RAIN_MAX%</div>
    </div>

    <div class="divider"></div>

    <!-- CHART -->
    <div class="chart-wrap">
      <div class="sec-label">Hourly forecast &mdash; drag to explore</div>
      <canvas id="chart" height="110"></canvas>
      <div class="hour-detail" id="hour-detail">
        <div class="hd-time" id="hd-time">--</div>
        <div class="hd-grid">
          <div class="hd-item"><span class="hd-lbl">Temp</span><span class="hd-val" id="hd-temp">--</span></div>
          <div class="hd-item"><span class="hd-lbl">Rain</span><span class="hd-val" id="hd-rain">--</span></div>
          <div class="hd-item"><span class="hd-lbl">Humidity</span><span class="hd-val" id="hd-hum">--</span></div>
          <div class="hd-item"><span class="hd-lbl">Wind</span><span class="hd-val" id="hd-wind">--</span></div>
        </div>
      </div>
      <div class="chart-hint">click or drag any bar &bull; rain % shown below each hour</div>
    </div>

    <div class="divider"></div>

    <!-- PRAYER -->
    <div class="prayer-wrap">
      <div class="sec-label">Prayer &amp; sun schedule</div>
      <div class="prayer-grid">
        <div class="prayer-cell"><div class="p-name">Fajr</div><div class="p-time">FAJR</div></div>
        <div class="prayer-cell"><div class="p-name">Sunrise</div><div class="p-time">SUNRISE</div></div>
        <div class="prayer-cell"><div class="p-name">Dhuhr</div><div class="p-time">DHUHR</div></div>
        <div class="prayer-cell"><div class="p-name">Asr</div><div class="p-time">ASR</div></div>
        <div class="prayer-cell"><div class="p-name">Maghrib</div><div class="p-time">MAGHRIB</div></div>
        <div class="prayer-cell"><div class="p-name">Isha</div><div class="p-time">ISHA</div></div>
      </div>
    </div>

    <div class="divider"></div>

    <!-- AI BRIEF -->
    <div class="brief-wrap">
      <div class="sec-label">AI briefing</div>
      <div class="brief-row">
        <div class="b-icon">&#9728;</div>
        <div class="b-inner"><div class="b-lbl">Weather</div><div class="b-text">SUMMARY</div></div>
      </div>
      <div class="brief-row">
        <div class="b-icon">&#128085;</div>
        <div class="b-inner"><div class="b-lbl">Outfit</div><div class="b-text">OUTFIT</div></div>
      </div>
      <div class="brief-row">
        <div class="b-icon">&#10024;</div>
        <div class="b-inner"><div class="motivate">MOTIVATION</div></div>
      </div>
    </div>

    <div class="divider"></div>

    <!-- CTA -->
    <div class="cta-wrap">
      <a href="MAILTO_LINK" class="cta-btn">&#128172;&nbsp; Ask a question</a>
      <div class="cta-hint">AI responds within 1 minute</div>
    </div>

    <!-- FOOTER -->
    <div class="footer">
      <span class="f-left">auto-delivered &middot; islamabad &middot; pkt</span>
      <span class="f-right">by <span>Abdullah Adnan</span></span>
    </div>

  </div>

  <div class="bottom">Powered by Groq &amp; OpenWeather &middot; Built by Abdullah</div>
</div>

<script>
(function(){
  var slots = FORECAST_JSON;
  var currentHour = CURRENT_HOUR;
  var selected = 0;

  // find closest slot to current hour
  var minDiff = 999;
  slots.forEach(function(s,i){
    var d = Math.abs(s.hour - currentHour);
    if(d < minDiff){ minDiff=d; selected=i; }
  });

  var canvas = document.getElementById('chart');
  var ctx = canvas.getContext('2d');

  function draw(){
    var W = canvas.parentElement.clientWidth;
    canvas.width = W; canvas.height = 110;
    var n = slots.length;
    var PAD = 8;
    var total_w = W - PAD*2;
    var BAR_W = Math.floor(total_w/n) - 6;
    var GAP = Math.floor((total_w - n*BAR_W)/(n-1));
    var CHART_H = 72;
    var MIN_BH = 12; var MAX_BH = 52;

    var temps = slots.map(function(s){return s.temp;});
    var lo = Math.min.apply(null,temps);
    var hi = Math.max.apply(null,temps);
    var rng = Math.max(hi-lo,1);
    function bh(t){return MIN_BH+(t-lo)/rng*(MAX_BH-MIN_BH);}

    ctx.clearRect(0,0,W,110);

    // bezier line
    var pts=[];
    slots.forEach(function(s,i){
      var x=PAD+i*(BAR_W+GAP);
      pts.push([x+BAR_W/2, CHART_H-bh(s.temp)]);
    });
    ctx.beginPath();
    ctx.moveTo(pts[0][0],pts[0][1]);
    for(var i=1;i<pts.length;i++){
      var mx=(pts[i-1][0]+pts[i][0])/2;
      ctx.bezierCurveTo(mx,pts[i-1][1],mx,pts[i][1],pts[i][0],pts[i][1]);
    }
    ctx.strokeStyle='rgba(99,102,241,0.15)';
    ctx.lineWidth=1.5;
    ctx.stroke();

    slots.forEach(function(s,i){
      var x = PAD+i*(BAR_W+GAP);
      var h = bh(s.temp);
      var y = CHART_H-h;
      var cx = x+BAR_W/2;
      var isSel = i===selected;
      var isNow = s.hour===currentHour;

      // bar
      var r=5;
      ctx.beginPath();
      ctx.moveTo(x+r,y);ctx.lineTo(x+BAR_W-r,y);
      ctx.quadraticCurveTo(x+BAR_W,y,x+BAR_W,y+r);
      ctx.lineTo(x+BAR_W,CHART_H);ctx.lineTo(x,CHART_H);
      ctx.lineTo(x,y+r);ctx.quadraticCurveTo(x,y,x+r,y);
      ctx.closePath();
      ctx.fillStyle = isSel ? '#6366F1' : (isNow ? '#818cf8' : '#f0f0f0');
      ctx.fill();

      // temp label
      ctx.fillStyle = isSel ? '#fff' : '#333';
      ctx.font = '500 11px Inter,-apple-system,sans-serif';
      ctx.textAlign='center';
      ctx.fillText(s.temp+'°', cx, y-4);

      // hour label
      ctx.fillStyle = isSel ? '#6366F1' : '#aaa';
      ctx.font = '11px Inter,-apple-system,sans-serif';
      ctx.fillText(s.label, cx, CHART_H+13);

      // rain label
      ctx.fillStyle = '#bbb';
      ctx.font = '10px Inter,-apple-system,sans-serif';
      ctx.fillText(s.rain+'%', cx, CHART_H+26);
    });
  }

  function updateDetail(i){
    var s=slots[i];
    document.getElementById('hd-time').textContent  = s.label;
    document.getElementById('hd-temp').textContent  = s.temp+'°C';
    document.getElementById('hd-rain').textContent  = s.rain+'%';
    document.getElementById('hd-hum').textContent   = s.hum+'%';
    document.getElementById('hd-wind').textContent  = s.wind+' m/s';
  }

  function getIdx(e){
    var rect=canvas.getBoundingClientRect();
    var cx=(e.touches?e.touches[0].clientX:e.clientX)-rect.left;
    var W=canvas.width; var n=slots.length; var PAD=8;
    var BAR_W=Math.floor((W-PAD*2)/n)-6;
    var GAP=Math.floor((W-PAD*2-n*BAR_W)/(n-1));
    for(var i=0;i<n;i++){
      var bx=PAD+i*(BAR_W+GAP);
      if(cx>=bx && cx<=bx+BAR_W+GAP) return i;
    }
    return -1;
  }

  var drag=false;
  canvas.addEventListener('mousedown',function(e){drag=true;var i=getIdx(e);if(i>=0){selected=i;draw();updateDetail(i);}});
  canvas.addEventListener('mousemove',function(e){if(!drag)return;var i=getIdx(e);if(i>=0){selected=i;draw();updateDetail(i);}});
  canvas.addEventListener('mouseup',function(){drag=false;});
  canvas.addEventListener('mouseleave',function(){drag=false;});
  canvas.addEventListener('touchstart',function(e){e.preventDefault();var i=getIdx(e);if(i>=0){selected=i;draw();updateDetail(i);}},{passive:false});
  canvas.addEventListener('touchmove',function(e){e.preventDefault();var i=getIdx(e);if(i>=0){selected=i;draw();updateDetail(i);}},{passive:false});

  draw();
  updateDetail(selected);
  window.addEventListener('resize',function(){draw();});
})();
</script>
</body>
</html>"""

    # Current rain max across forecast
    rain_max = max(s['rain'] for s in forecast)

    html = html.replace("TOPBAR_DATE",   today_short)
    html = html.replace("TEMPERATURE",   str(weather['temperature']))
    html = html.replace("DESCRIPTION",   weather['description'])
    html = html.replace("FEELS_LIKE",    str(weather['feels_like']))
    html = html.replace("WEATHER_ICON",  w_icon)
    html = html.replace("HUMIDITY",      str(weather['humidity']))
    html = html.replace("WIND",          str(weather['wind_speed']))
    html = html.replace("RAIN_MAX",      str(rain_max))
    html = html.replace("SUMMARY",       summary)
    html = html.replace("OUTFIT",        outfit)
    html = html.replace("MOTIVATION",    motivation)
    html = html.replace("FAJR",          namaz['Fajr'])
    html = html.replace("SUNRISE",       namaz['Sunrise'])
    html = html.replace("DHUHR",         namaz['Dhuhr'])
    html = html.replace("ASR",           namaz['Asr'])
    html = html.replace("MAGHRIB",       namaz['Maghrib'])
    html = html.replace("ISHA",          namaz['Isha'])
    html = html.replace("MAILTO_LINK",   mailto)
    html = html.replace("FORECAST_JSON", forecast_json)
    html = html.replace("CURRENT_HOUR",  current_hour_js)

    return html

def send_email(sender_email, sender_password, recipient_email, weather, forecast, namaz, advice):
    subject = "&#127780; Your Daily Weather & Schedule — Islamabad"
    html_content = build_html_email(weather, forecast, namaz, advice, sender_email)
    msg = MIMEMultipart('alternative')
    msg["Subject"] = "Your Daily Weather & Schedule — Islamabad"
    msg["From"]    = sender_email
    msg["To"]      = recipient_email
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)

def main():
    email       = os.environ["EMAIL_ADDRESS"]
    password    = os.environ["EMAIL_PASSWORD"]
    weather_key = os.environ["WEATHER_API_KEY"]
    groq_key    = os.environ["GROQ_API_KEY"]
    recipient   = os.environ.get("EMAIL_RECIPIENT", "adspk243@gmail.com")

    city = "Islamabad"

    weather_data  = get_weather(city, weather_key)
    forecast_data = get_forecast(city, weather_key)
    namaz_data    = get_namaz_times(city)
    daily_advice  = get_groq_advice(weather_data, forecast_data, groq_key)

    send_email(email, password, recipient, weather_data, forecast_data, namaz_data, daily_advice)

if __name__ == "__main__":
    main()
