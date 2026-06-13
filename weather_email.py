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
    r = requests.get(url, params=params).json()
    return {
        "city":        r["name"],
        "temperature": round(r["main"]["temp"]),
        "feels_like":  round(r["main"]["feels_like"]),
        "description": r["weather"][0]["description"].title(),
        "humidity":    r["main"]["humidity"],
        "wind_speed":  round(r["wind"]["speed"]),
    }


def get_forecast(city, api_key):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city, "appid": api_key, "units": "metric", "cnt": 8}
    data = requests.get(url, params=params).json()
    slots = []
    for item in data["list"]:
        dt = datetime.fromtimestamp(item["dt"])
        hour = dt.hour
        if hour == 0:
            label = "12am"
        elif hour < 12:
            label = str(hour) + "am"
        elif hour == 12:
            label = "12pm"
        else:
            label = str(hour - 12) + "pm"
        slots.append({
            "label": label,
            "hour":  hour,
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
    timings = response["data"]["timings"]
    result = {}
    for key, value in timings.items():
        clean = value.split(" ")[0]
        try:
            t = datetime.strptime(clean, "%H:%M")
            result[key] = t.strftime("%I:%M %p").lstrip("0")
        except Exception:
            result[key] = value
    return result


def get_groq_advice(weather, forecast, groq_key):
    client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
    temps = [s["temp"] for s in forecast]
    rains = [s["rain"] for s in forecast]
    prompt = (
        "You are a concise morning weather assistant for " + weather["city"] + ", Pakistan.\n"
        "Write exactly 3 sections separated by ###. No titles. Plain text only. 2-3 sentences each.\n\n"
        "Current: " + str(weather["temperature"]) + "C, " + weather["description"] + ", humidity " + str(weather["humidity"]) + "%\n"
        "Today temp range: " + str(min(temps)) + "C to " + str(max(temps)) + "C\n"
        "Max rain chance: " + str(max(rains)) + "%\n\n"
        "Section 1: Weather summary for the full day.\n"
        "Section 2: What to wear and how to prep.\n"
        "Section 3: One powerful motivational sentence.\n\n"
        "Output format (no titles, no markdown):\n"
        "Summary text here\n###\nOutfit advice here\n###\nMotivation here"
    )
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def get_weather_icon(desc):
    d = desc.lower()
    if   "rain"    in d: return "&#127783;"
    elif "thunder" in d: return "&#9928;"
    elif "cloud"   in d: return "&#9729;"
    elif "clear"   in d: return "&#9728;"
    elif "snow"    in d: return "&#10052;"
    elif "haze"    in d or "fog" in d: return "&#127787;"
    elif "smoke"   in d or "mist" in d: return "&#127787;"
    else:                return "&#127780;"


def build_html_email(weather, forecast, namaz, advice, sender_email):
    today_label  = datetime.now().strftime("%a, %B %d &#183; %Y")
    current_hour = datetime.now().hour

    sections   = [s.strip() for s in advice.split("###")]
    summary    = sections[0] if len(sections) > 0 else "Enjoy the weather today!"
    outfit     = sections[1] if len(sections) > 1 else "Dress comfortably."
    motivation = sections[2] if len(sections) > 2 else "Make today count."

    w_icon      = get_weather_icon(weather["description"])
    forecast_js = json.dumps(forecast)
    rain_max    = max(s["rain"] for s in forecast)
    mailto      = "mailto:" + sender_email + "?subject=Re%3A%20Your%20Daily%20Weather%20%26%20Schedule"

    # -----------------------------------------------------------------------
    # HTML template — uses .replace() so CSS curly braces never clash with
    # Python f-strings. Every placeholder is ALL_CAPS_UNDERSCORED.
    # -----------------------------------------------------------------------
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Daily Weather</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{background:#111;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;-webkit-font-smoothing:antialiased;padding:20px 10px 40px;color:#f0f0f0;}
.w-wrap{max-width:520px;margin:0 auto;}
.w-toprow{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;padding:0 2px;}
.w-toplbl{font-size:10px;color:#444;font-weight:500;letter-spacing:.12em;text-transform:uppercase;}
.w-toprgt{font-size:10px;color:#333;}
.w-card{background:#1a1a1a;border-radius:18px;border:1px solid #262626;overflow:hidden;}
.w-div{height:1px;background:#222;}
.w-sec{font-size:10px;color:#444;font-weight:500;letter-spacing:.14em;text-transform:uppercase;margin-bottom:14px;}
.w-hero{padding:24px 20px 14px;display:flex;justify-content:space-between;align-items:flex-start;}
.w-city{font-size:11px;color:#444;margin-bottom:6px;}
.w-temp{font-size:64px;font-weight:600;color:#fff;line-height:1;letter-spacing:-2px;}
.w-deg{font-size:22px;font-weight:300;color:#444;vertical-align:super;}
.w-desc{font-size:13px;color:#666;margin-top:8px;}
.w-feels{font-size:11px;color:#333;margin-top:3px;}
.w-icon{font-size:40px;opacity:.45;padding-top:4px;}
.w-pills{padding:0 20px 16px;display:flex;flex-wrap:wrap;gap:6px;}
.w-pill{display:inline-flex;align-items:center;gap:5px;background:#1e1e1e;border:1px solid #2a2a2a;border-radius:20px;padding:5px 11px;font-size:12px;color:#aaa;}
.w-pill-lbl{font-size:10px;color:#333;}
.w-chart{padding:18px 20px 4px;}
canvas{display:block;width:100%;cursor:pointer;}
.w-det{margin-top:10px;padding:12px 14px;background:#202020;border-radius:10px;border:1px solid #282828;display:flex;gap:16px;align-items:center;}
.w-det-lbl{font-size:9px;color:#333;text-transform:uppercase;letter-spacing:.1em;margin-bottom:2px;}
.w-det-time{font-size:18px;font-weight:600;color:#818cf8;min-width:42px;}
.w-det-grid{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:4px 14px;}
.w-det-k{font-size:11px;color:#333;}
.w-det-v{font-size:12px;font-weight:500;color:#ccc;}
.w-hint{font-size:9px;color:#272727;text-align:center;margin:8px 0 16px;letter-spacing:.04em;}
.w-prayer{padding:18px 20px;}
.w-pgrid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px 8px;}
.w-pname{font-size:9px;color:#333;text-transform:uppercase;letter-spacing:.1em;margin-bottom:3px;}
.w-ptime{font-size:14px;font-weight:500;color:#ccc;}
.w-brief{padding:18px 20px;}
.w-brow{display:flex;gap:10px;align-items:flex-start;margin-bottom:12px;}
.w-bico{width:26px;height:26px;background:#1e1e1e;border:1px solid #2a2a2a;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;}
.w-blbl{font-size:9px;color:#333;text-transform:uppercase;letter-spacing:.1em;margin-bottom:3px;}
.w-btxt{font-size:12px;color:#555;line-height:1.65;font-weight:300;}
.w-motiv{background:#1c1c1c;border-left:2px solid #6366F1;border-radius:0 7px 7px 0;padding:10px 14px;font-size:12px;color:#555;font-style:italic;line-height:1.6;}
.w-cta{padding:14px 20px 20px;text-align:center;}
.w-ctabtn{display:inline-block;background:#6366F1;color:#fff!important;text-decoration:none!important;font-size:12px;font-weight:500;padding:10px 26px;border-radius:8px;}
.w-ctahint{font-size:10px;color:#333;margin-top:7px;}
.w-foot{padding:10px 20px;border-top:1px solid #1e1e1e;display:flex;justify-content:space-between;align-items:center;}
.w-fl{font-size:9px;color:#2a2a2a;font-family:monospace;}
.w-fr{font-size:10px;color:#2e2e2e;}
.w-fr span{color:#6366F1;font-weight:500;}
.w-bottom{text-align:center;margin-top:14px;font-size:9px;color:#1e1e1e;letter-spacing:.1em;text-transform:uppercase;}
</style>
</head>
<body>
<div class="w-wrap">
  <div class="w-toprow">
    <span class="w-toplbl">TOPBAR_DATE</span>
    <span class="w-toprgt">Islamabad &middot; Pakistan</span>
  </div>
  <div class="w-card">

    <div class="w-hero">
      <div>
        <div class="w-city">Islamabad</div>
        <div class="w-temp">TEMPERATURE<span class="w-deg">&deg;C</span></div>
        <div class="w-desc">DESCRIPTION</div>
        <div class="w-feels">feels like FEELS_LIKE&deg;C</div>
      </div>
      <div class="w-icon">WEATHER_ICON</div>
    </div>

    <div class="w-pills">
      <span class="w-pill"><span class="w-pill-lbl">Humidity</span>HUMIDITY%</span>
      <span class="w-pill"><span class="w-pill-lbl">Wind</span>WIND m/s</span>
      <span class="w-pill"><span class="w-pill-lbl">Max rain</span>RAIN_MAX%</span>
    </div>

    <div class="w-div"></div>

    <div class="w-chart">
      <div class="w-sec">Hourly forecast &mdash; drag to explore</div>
      <canvas id="wch" height="120"></canvas>
      <div class="w-det">
        <div style="min-width:46px;">
          <div class="w-det-lbl">Hour</div>
          <div class="w-det-time" id="wdt">--</div>
        </div>
        <div class="w-det-grid">
          <div><span class="w-det-k">Temp&nbsp;</span><span class="w-det-v" id="wdtemp">--</span></div>
          <div><span class="w-det-k">Rain&nbsp;</span><span class="w-det-v" id="wdrain">--</span></div>
          <div><span class="w-det-k">Humidity&nbsp;</span><span class="w-det-v" id="wdhum">--</span></div>
          <div><span class="w-det-k">Wind&nbsp;</span><span class="w-det-v" id="wdwind">--</span></div>
        </div>
      </div>
      <div class="w-hint">click or drag any bar &bull; rain % shown below each hour</div>
    </div>

    <div class="w-div"></div>

    <div class="w-prayer">
      <div class="w-sec">Prayer &amp; sun schedule</div>
      <div class="w-pgrid">
        <div><div class="w-pname">Fajr</div><div class="w-ptime">FAJR</div></div>
        <div><div class="w-pname">Sunrise</div><div class="w-ptime">SUNRISE</div></div>
        <div><div class="w-pname">Dhuhr</div><div class="w-ptime">DHUHR</div></div>
        <div><div class="w-pname">Asr</div><div class="w-ptime">ASR</div></div>
        <div><div class="w-pname">Maghrib</div><div class="w-ptime">MAGHRIB</div></div>
        <div><div class="w-pname">Isha</div><div class="w-ptime">ISHA</div></div>
      </div>
    </div>

    <div class="w-div"></div>

    <div class="w-brief">
      <div class="w-sec">AI briefing</div>
      <div class="w-brow">
        <div class="w-bico">&#9728;</div>
        <div><div class="w-blbl">Weather</div><div class="w-btxt">SUMMARY</div></div>
      </div>
      <div class="w-brow">
        <div class="w-bico">&#128085;</div>
        <div><div class="w-blbl">Outfit</div><div class="w-btxt">OUTFIT</div></div>
      </div>
      <div class="w-brow">
        <div class="w-bico">&#10024;</div>
        <div><div class="w-motiv">MOTIVATION</div></div>
      </div>
    </div>

    <div class="w-div"></div>

    <div class="w-cta">
      <a href="MAILTO_LINK" class="w-ctabtn">&#128172;&nbsp; Ask a question</a>
      <div class="w-ctahint">AI responds within 1 minute</div>
    </div>

    <div class="w-foot">
      <span class="w-fl">auto-delivered &middot; islamabad &middot; pkt</span>
      <span class="w-fr">by <span>Abdullah Adnan</span></span>
    </div>

  </div>
  <div class="w-bottom">Powered by Groq &amp; OpenWeather &middot; Built by Abdullah</div>
</div>

<script>
(function(){
var slots=FORECAST_JSON;
var curH=CURRENT_HOUR;
var sel=0,drag=false;
var minD=999;
slots.forEach(function(s,i){var d=Math.abs(s.hour-curH);if(d<minD){minD=d;sel=i;}});
var canvas=document.getElementById('wch');
var ctx=canvas.getContext('2d');

function draw(){
  var W=canvas.parentElement.clientWidth;
  canvas.width=W; canvas.height=120;
  var n=slots.length;
  var PAD=8;
  var totalW=W-PAD*2;
  var BW=Math.floor(totalW/n*0.65);
  var GAP=n>1?Math.floor((totalW-n*BW)/(n-1)):0;
  var CH=72, MIN_BH=10, MAX_BH=48;
  var temps=slots.map(function(s){return s.temp;});
  var lo=Math.min.apply(null,temps);
  var hi=Math.max.apply(null,temps);
  var rng=Math.max(hi-lo,1);
  function bh(t){return MIN_BH+(t-lo)/rng*(MAX_BH-MIN_BH);}
  ctx.clearRect(0,0,W,120);

  var pts=[];
  slots.forEach(function(s,i){
    pts.push([PAD+i*(BW+GAP)+BW/2, CH-bh(s.temp)]);
  });
  ctx.beginPath();
  ctx.moveTo(pts[0][0],pts[0][1]);
  for(var i=1;i<pts.length;i++){
    var mx=(pts[i-1][0]+pts[i][0])/2;
    ctx.bezierCurveTo(mx,pts[i-1][1],mx,pts[i][1],pts[i][0],pts[i][1]);
  }
  ctx.strokeStyle='rgba(99,102,241,0.18)';
  ctx.lineWidth=1.5;
  ctx.stroke();

  slots.forEach(function(s,i){
    var x=PAD+i*(BW+GAP);
    var h=bh(s.temp); var y=CH-h;
    var cx=x+BW/2;
    var isSel=i===sel;
    var r=4;
    ctx.beginPath();
    ctx.moveTo(x+r,y); ctx.lineTo(x+BW-r,y);
    ctx.quadraticCurveTo(x+BW,y,x+BW,y+r);
    ctx.lineTo(x+BW,CH); ctx.lineTo(x,CH);
    ctx.lineTo(x,y+r); ctx.quadraticCurveTo(x,y,x+r,y);
    ctx.closePath();
    ctx.fillStyle=isSel?'#6366F1':'#252525';
    ctx.fill();

    ctx.fillStyle=isSel?'#ffffff':'#555555';
    ctx.font='500 11px -apple-system,BlinkMacSystemFont,sans-serif';
    ctx.textAlign='center';
    ctx.fillText(s.temp+'\u00b0',cx,y-4);

    ctx.fillStyle=isSel?'#a5b4fc':'#333333';
    ctx.font='10px -apple-system,sans-serif';
    ctx.fillText(s.label,cx,CH+13);

    ctx.fillStyle='#2a2a2a';
    ctx.font='9px -apple-system,sans-serif';
    ctx.fillText(s.rain+'%',cx,CH+25);
  });
}

function upd(i){
  var s=slots[i];
  document.getElementById('wdt').textContent=s.label;
  document.getElementById('wdtemp').textContent=s.temp+'\u00b0C';
  document.getElementById('wdrain').textContent=s.rain+'%';
  document.getElementById('wdhum').textContent=s.hum+'%';
  document.getElementById('wdwind').textContent=s.wind+' m/s';
}

function getIdx(e){
  var rect=canvas.getBoundingClientRect();
  var scaleX=canvas.width/rect.width;
  var cx=((e.touches?e.touches[0].clientX:e.clientX)-rect.left)*scaleX;
  var W=canvas.width, n=slots.length, PAD=8;
  var BW=Math.floor((W-PAD*2)/n*0.65);
  var GAP=n>1?Math.floor((W-PAD*2-n*BW)/(n-1)):0;
  var best=-1, bestDist=99999;
  for(var i=0;i<n;i++){
    var mid=PAD+i*(BW+GAP)+BW/2;
    var dist=Math.abs(cx-mid);
    if(dist<bestDist){bestDist=dist;best=i;}
  }
  return best;
}

canvas.addEventListener('mousedown',function(e){drag=true;var i=getIdx(e);if(i>=0){sel=i;draw();upd(i);}});
canvas.addEventListener('mousemove',function(e){if(!drag)return;var i=getIdx(e);if(i>=0){sel=i;draw();upd(i);}});
canvas.addEventListener('mouseup',function(){drag=false;});
canvas.addEventListener('mouseleave',function(){drag=false;});
canvas.addEventListener('touchstart',function(e){e.preventDefault();var i=getIdx(e);if(i>=0){sel=i;draw();upd(i);}},{passive:false});
canvas.addEventListener('touchmove',function(e){e.preventDefault();var i=getIdx(e);if(i>=0){sel=i;draw();upd(i);}},{passive:false});
draw(); upd(sel);
window.addEventListener('resize',function(){draw();});
})();
</script>
</body>
</html>"""

    html = html.replace("TOPBAR_DATE",   today_label)
    html = html.replace("TEMPERATURE",   str(weather["temperature"]))
    html = html.replace("DESCRIPTION",   weather["description"])
    html = html.replace("FEELS_LIKE",    str(weather["feels_like"]))
    html = html.replace("WEATHER_ICON",  w_icon)
    html = html.replace("HUMIDITY",      str(weather["humidity"]))
    html = html.replace("WIND",          str(weather["wind_speed"]))
    html = html.replace("RAIN_MAX",      str(rain_max))
    html = html.replace("SUMMARY",       summary)
    html = html.replace("OUTFIT",        outfit)
    html = html.replace("MOTIVATION",    motivation)
    html = html.replace("FAJR",          namaz.get("Fajr", "--"))
    html = html.replace("SUNRISE",       namaz.get("Sunrise", "--"))
    html = html.replace("DHUHR",         namaz.get("Dhuhr", "--"))
    html = html.replace("ASR",           namaz.get("Asr", "--"))
    html = html.replace("MAGHRIB",       namaz.get("Maghrib", "--"))
    html = html.replace("ISHA",          namaz.get("Isha", "--"))
    html = html.replace("MAILTO_LINK",   mailto)
    html = html.replace("FORECAST_JSON", forecast_js)
    html = html.replace("CURRENT_HOUR",  str(current_hour))

    return html


def send_email(sender_email, sender_password, recipient_email, weather, forecast, namaz, advice):
    html_content = build_html_email(weather, forecast, namaz, advice, sender_email)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your Daily Weather & Schedule \u2014 Islamabad"
    msg["From"]    = sender_email
    msg["To"]      = recipient_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
    print("Email sent successfully.")


def main():
    email       = os.environ["EMAIL_ADDRESS"]
    password    = os.environ["EMAIL_PASSWORD"]
    weather_key = os.environ["WEATHER_API_KEY"]
    groq_key    = os.environ["GROQ_API_KEY"]
    recipient   = os.environ.get("EMAIL_RECIPIENT", "adspk243@gmail.com")
    city        = "Islamabad"

    print("Fetching weather data...")
    weather_data  = get_weather(city, weather_key)
    forecast_data = get_forecast(city, weather_key)
    namaz_data    = get_namaz_times(city)

    print("Generating AI advice...")
    daily_advice = get_groq_advice(weather_data, forecast_data, groq_key)

    print("Sending email...")
    send_email(email, password, recipient, weather_data, forecast_data, namaz_data, daily_advice)


if __name__ == "__main__":
    main()
