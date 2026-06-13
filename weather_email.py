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
        "city":        current["name"],
        "temperature": round(current["main"]["temp"]),
        "feels_like":  round(current["main"]["feels_like"]),
        "description": current["weather"][0]["description"].title(),
        "humidity":    current["main"]["humidity"],
        "wind_speed":  round(current["wind"]["speed"]),
    }

def get_forecast(city, api_key):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city, "appid": api_key, "units": "metric", "cnt": 8}
    data = requests.get(url, params=params).json()
    slots = []
    for item in data["list"]:
        dt = datetime.fromtimestamp(item["dt"])
        label = dt.strftime("%I%p").lstrip("0").lower()
        slots.append({
            "label": label,
            "hour":  dt.hour,
            "temp":  round(item["main"]["temp"]),
            "feels": round(item["main"]["feels_like"]),
            "rain":  int(item.get("pop", 0) * 100),
            "hum":   item["main"]["humidity"],
            "wind":  round(item["wind"]["speed"]),
            "desc":  item["weather"][0]["description"].title(),
        })
    return slots

def get_namaz_times(city):
    url = "http://api.aladhan.com/v1/timingsByCity?city=" + city + "&country=Pakistan&method=1"
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
    prompt = (
        "You are a concise morning weather assistant for " + weather['city'] + ", Pakistan.\n"
        "Write exactly 3 sections separated by ###. No titles. Plain text only. 2-3 sentences each.\n\n"
        "Current: " + str(weather['temperature']) + "C, " + weather['description'] + ", humidity " + str(weather['humidity']) + "%\n"
        "Today temp range: " + str(min(temps)) + "C to " + str(max(temps)) + "C\n"
        "Max rain chance: " + str(max(rains)) + "%\n\n"
        "1. Weather summary for the full day.\n"
        "2. What to wear and prep.\n"
        "3. One powerful motivational sentence.\n\n"
        "Format:\nSummary text here\n###\nOutfit advice here\n###\nMotivation here"
    )
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def get_weather_icon(desc):
    d = desc.lower()
    if   'rain'    in d: return "&#127783;"
    elif 'thunder' in d: return "&#9928;"
    elif 'cloud'   in d: return "&#9729;"
    elif 'clear'   in d: return "&#9728;"
    elif 'snow'    in d: return "&#10052;"
    elif 'haze'    in d or 'fog' in d: return "&#127787;"
    else:                return "&#127780;"

def build_html_email(weather, forecast, namaz, advice, sender_email):
    today_short  = datetime.now().strftime("%A, %B %d · %Y")
    current_hour = datetime.now().hour

    sections   = [s.strip() for s in advice.split('###')]
    summary    = sections[0] if len(sections) > 0 else "Enjoy the weather today!"
    outfit     = sections[1] if len(sections) > 1 else "Dress comfortably."
    motivation = sections[2] if len(sections) > 2 else "Have a great day!"

    w_icon       = get_weather_icon(weather['description'])
    forecast_js  = json.dumps(forecast)
    rain_max     = max(s['rain'] for s in forecast)
    mailto       = "mailto:" + sender_email + "?subject=Re%3A%20Your%20Daily%20Weather%20%26%20Schedule%20App"

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{background:#111;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;-webkit-font-smoothing:antialiased;padding:24px 12px 48px;color:#f0f0f0;}
.wrap{max-width:560px;margin:0 auto;}
.toprow{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;padding:0 2px;}
.toplbl{font-size:11px;color:#555;font-weight:500;letter-spacing:.1em;text-transform:uppercase;}
.card{background:#1a1a1a;border-radius:18px;border:1px solid #2a2a2a;overflow:hidden;}
.hr{height:1px;background:#242424;}
.sec-lbl{font-size:10px;color:#555;font-weight:500;letter-spacing:.14em;text-transform:uppercase;margin-bottom:14px;}
.pill{display:inline-flex;align-items:center;gap:5px;background:#222;border:1px solid #2e2e2e;border-radius:20px;padding:5px 12px;font-size:12px;color:#ccc;margin-right:6px;margin-bottom:6px;}
.pill-lbl{color:#555;font-size:11px;}
.hero{padding:28px 24px 16px;display:flex;justify-content:space-between;align-items:flex-start;}
.temp-big{font-size:68px;font-weight:600;color:#fff;line-height:1;letter-spacing:-2px;}
.temp-deg{font-size:24px;color:#555;font-weight:300;}
.city-lbl{font-size:12px;color:#555;margin-bottom:8px;}
.desc-lbl{font-size:14px;color:#888;margin-top:10px;}
.feels-lbl{font-size:12px;color:#555;margin-top:3px;}
.hero-icon{font-size:44px;padding-top:4px;opacity:.5;}
.pills-row{padding:0 24px 18px;}
.chart-wrap{padding:20px 24px 6px;}
canvas{display:block;}
.det-box{margin-top:12px;padding:12px 16px;background:#222;border-radius:10px;display:flex;gap:20px;align-items:center;}
.det-time-lbl{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.1em;margin-bottom:3px;}
.det-time{font-size:20px;font-weight:600;color:#6366F1;}
.det-grid{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:5px 16px;}
.det-item{font-size:12px;}
.det-key{color:#555;}
.det-val{font-weight:500;color:#eee;}
.chart-hint{font-size:10px;color:#333;text-align:center;margin:8px 0 18px;}
.prayer-wrap{padding:20px 24px;}
.prayer-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px 8px;}
.p-name{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px;}
.p-time{font-size:15px;font-weight:500;color:#eee;}
.brief-wrap{padding:20px 24px;}
.brief-row{display:flex;gap:12px;align-items:flex-start;margin-bottom:14px;}
.brief-ico{width:28px;height:28px;background:#222;border:1px solid #2e2e2e;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0;}
.brief-lbl{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px;}
.brief-txt{font-size:13px;color:#888;line-height:1.65;font-weight:300;}
.motivate{background:#1e1e1e;border-left:2px solid #6366F1;padding:12px 16px;border-radius:0 8px 8px 0;font-size:13px;color:#777;font-style:italic;line-height:1.6;}
.cta-wrap{padding:16px 24px 22px;text-align:center;}
.cta-btn{display:inline-block;background:#6366F1;color:#fff !important;text-decoration:none !important;font-size:13px;font-weight:500;padding:11px 28px;border-radius:8px;}
.cta-hint{font-size:11px;color:#444;margin-top:8px;}
.footer{padding:12px 24px;border-top:1px solid #242424;display:flex;justify-content:space-between;align-items:center;}
.f-l{font-size:10px;color:#333;font-family:monospace;}
.f-r{font-size:11px;color:#444;}
.f-r span{color:#6366F1;font-weight:500;}
.bottom{text-align:center;margin-top:16px;font-size:10px;color:#2a2a2a;letter-spacing:.12em;text-transform:uppercase;}
</style>
</head>
<body>
<div class="wrap">
  <div class="toprow">
    <span class="toplbl">TODAY_DATE</span>
    <span style="font-size:11px;color:#555;">Islamabad &middot; Pakistan</span>
  </div>
  <div class="card">
    <div class="hero">
      <div>
        <div class="city-lbl">CITY_NAME</div>
        <div class="temp-big">TEMPERATURE<span class="temp-deg">&deg;C</span></div>
        <div class="desc-lbl">DESCRIPTION</div>
        <div class="feels-lbl">feels like FEELS_LIKE&deg;C</div>
      </div>
      <div class="hero-icon">WEATHER_ICON</div>
    </div>
    <div class="pills-row">
      <span class="pill"><span class="pill-lbl">Humidity</span>HUMIDITY%</span>
      <span class="pill"><span class="pill-lbl">Wind</span>WIND m/s</span>
      <span class="pill"><span class="pill-lbl">Rain</span>RAIN_MAX%</span>
    </div>
    <div class="hr"></div>
    <div class="chart-wrap">
      <div class="sec-lbl">Hourly forecast &mdash; drag to explore</div>
      <canvas id="ch" height="120"></canvas>
      <div class="det-box">
        <div style="min-width:44px;">
          <div class="det-time-lbl">Hour</div>
          <div class="det-time" id="d-time">--</div>
        </div>
        <div class="det-grid">
          <div class="det-item"><span class="det-key">Temp&nbsp;</span><span class="det-val" id="d-temp">--</span></div>
          <div class="det-item"><span class="det-key">Rain&nbsp;</span><span class="det-val" id="d-rain">--</span></div>
          <div class="det-item"><span class="det-key">Humidity&nbsp;</span><span class="det-val" id="d-hum">--</span></div>
          <div class="det-item"><span class="det-key">Wind&nbsp;</span><span class="det-val" id="d-wind">--</span></div>
        </div>
      </div>
      <div class="chart-hint">click or drag any bar &bull; rain % shown below</div>
    </div>
    <div class="hr"></div>
    <div class="prayer-wrap">
      <div class="sec-lbl">Prayer &amp; sun schedule</div>
      <div class="prayer-grid">
        <div><div class="p-name">Fajr</div><div class="p-time">FAJR</div></div>
        <div><div class="p-name">Sunrise</div><div class="p-time">SUNRISE</div></div>
        <div><div class="p-name">Dhuhr</div><div class="p-time">DHUHR</div></div>
        <div><div class="p-name">Asr</div><div class="p-time">ASR</div></div>
        <div><div class="p-name">Maghrib</div><div class="p-time">MAGHRIB</div></div>
        <div><div class="p-name">Isha</div><div class="p-time">ISHA</div></div>
      </div>
    </div>
    <div class="hr"></div>
    <div class="brief-wrap">
      <div class="sec-lbl">AI briefing</div>
      <div class="brief-row">
        <div class="brief-ico">&#9728;</div>
        <div><div class="brief-lbl">Weather</div><div class="brief-txt">SUMMARY</div></div>
      </div>
      <div class="brief-row">
        <div class="brief-ico">&#128085;</div>
        <div><div class="brief-lbl">Outfit</div><div class="brief-txt">OUTFIT</div></div>
      </div>
      <div class="brief-row">
        <div class="brief-ico">&#10024;</div>
        <div><div class="motivate">MOTIVATION</div></div>
      </div>
    </div>
    <div class="hr"></div>
    <div class="cta-wrap">
      <a href="MAILTO_LINK" class="cta-btn">&#128172;&nbsp; Ask a question</a>
      <div class="cta-hint">AI responds within 1 minute</div>
    </div>
    <div class="footer">
      <span class="f-l">auto-delivered &middot; islamabad &middot; pkt</span>
      <span class="f-r">by <span>Abdullah Adnan</span></span>
    </div>
  </div>
  <div class="bottom">Powered by Groq &amp; OpenWeather &middot; Built by Abdullah</div>
</div>
<script>
(function(){
var slots=FORECAST_JSON;
var curH=CURRENT_HOUR;
var sel=0,drag=false;
var minD=999;
slots.forEach(function(s,i){var d=Math.abs(s.hour-curH);if(d<minD){minD=d;sel=i;}});
var canvas=document.getElementById('ch'),ctx=canvas.getContext('2d');
function draw(){
  var W=canvas.parentElement.clientWidth;
  canvas.width=W;canvas.height=120;
  var n=slots.length,PAD=10;
  var BW=Math.floor((W-PAD*2)/n)-6;
  var GAP=Math.floor((W-PAD*2-n*BW)/(n-1));
  var CH=76,MIN_BH=10,MAX_BH=50;
  var temps=slots.map(function(s){return s.temp;});
  var lo=Math.min.apply(null,temps),hi=Math.max.apply(null,temps),rng=Math.max(hi-lo,1);
  function bh(t){return MIN_BH+(t-lo)/rng*(MAX_BH-MIN_BH);}
  ctx.clearRect(0,0,W,120);
  var pts=[];
  slots.forEach(function(s,i){pts.push([PAD+i*(BW+GAP)+BW/2,CH-bh(s.temp)]);});
  ctx.beginPath();ctx.moveTo(pts[0][0],pts[0][1]);
  for(var i=1;i<pts.length;i++){
    var mx=(pts[i-1][0]+pts[i][0])/2;
    ctx.bezierCurveTo(mx,pts[i-1][1],mx,pts[i][1],pts[i][0],pts[i][1]);
  }
  ctx.strokeStyle='rgba(99,102,241,0.2)';ctx.lineWidth=1.5;ctx.stroke();
  slots.forEach(function(s,i){
    var x=PAD+i*(BW+GAP),h=bh(s.temp),y=CH-h,cx=x+BW/2;
    var isSel=i===sel;
    var r=4;
    ctx.beginPath();
    ctx.moveTo(x+r,y);ctx.lineTo(x+BW-r,y);
    ctx.quadraticCurveTo(x+BW,y,x+BW,y+r);
    ctx.lineTo(x+BW,CH);ctx.lineTo(x,CH);
    ctx.lineTo(x,y+r);ctx.quadraticCurveTo(x,y,x+r,y);
    ctx.closePath();
    ctx.fillStyle=isSel?'#6366F1':'#2a2a2a';ctx.fill();
    ctx.fillStyle=isSel?'#fff':'#888';
    ctx.font='500 11px -apple-system,sans-serif';ctx.textAlign='center';
    ctx.fillText(s.temp+'deg',cx,y-4);
    ctx.fillStyle=isSel?'#818cf8':'#555';
    ctx.font='11px -apple-system,sans-serif';
    ctx.fillText(s.label,cx,CH+13);
    ctx.fillStyle='#3a3a3a';ctx.font='10px -apple-system,sans-serif';
    ctx.fillText(s.rain+'%',cx,CH+26);
  });
}
function upd(i){
  var s=slots[i];
  document.getElementById('d-time').textContent=s.label;
  document.getElementById('d-temp').textContent=s.temp+'C';
  document.getElementById('d-rain').textContent=s.rain+'%';
  document.getElementById('d-hum').textContent=s.hum+'%';
  document.getElementById('d-wind').textContent=s.wind+' m/s';
}
function getIdx(e){
  var rect=canvas.getBoundingClientRect();
  var cx=(e.touches?e.touches[0].clientX:e.clientX)-rect.left;
  var W=canvas.width,n=slots.length,PAD=10;
  var BW=Math.floor((W-PAD*2)/n)-6;
  var GAP=Math.floor((W-PAD*2-n*BW)/(n-1));
  for(var i=0;i<n;i++){var bx=PAD+i*(BW+GAP);if(cx>=bx&&cx<=bx+BW+GAP)return i;}
  return -1;
}
canvas.addEventListener('mousedown',function(e){drag=true;var i=getIdx(e);if(i>=0){sel=i;draw();upd(i);}});
canvas.addEventListener('mousemove',function(e){if(!drag)return;var i=getIdx(e);if(i>=0){sel=i;draw();upd(i);}});
canvas.addEventListener('mouseup',function(){drag=false;});
canvas.addEventListener('mouseleave',function(){drag=false;});
canvas.addEventListener('touchstart',function(e){e.preventDefault();var i=getIdx(e);if(i>=0){sel=i;draw();upd(i);}},{passive:false});
canvas.addEventListener('touchmove',function(e){e.preventDefault();var i=getIdx(e);if(i>=0){sel=i;draw();upd(i);}},{passive:false});
draw();upd(sel);
window.addEventListener('resize',draw);
})();
</script>
</body>
</html>"""

    html = html.replace("TODAY_DATE",    today_short)
    html = html.replace("CITY_NAME",     weather['city'])
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
    html = html.replace("FORECAST_JSON", forecast_js)
    html = html.replace("CURRENT_HOUR",  str(current_hour))

    return html

def send_email(sender_email, sender_password, recipient_email, weather, forecast, namaz, advice):
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
    city        = "Islamabad"
    weather_data  = get_weather(city, weather_key)
    forecast_data = get_forecast(city, weather_key)
    namaz_data    = get_namaz_times(city)
    daily_advice  = get_groq_advice(weather_data, forecast_data, groq_key)
    send_email(email, password, recipient, weather_data, forecast_data, namaz_data, daily_advice)

if __name__ == "__main__":
    main()
