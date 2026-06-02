import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from openai import OpenAI
from datetime import datetime, timezone, timedelta

PKT = timezone(timedelta(hours=5))

def get_weather(city, api_key):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}
    current = requests.get(url, params=params).json()

    forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
    forecast_data = requests.get(forecast_url, params=params).json()

    rain_prob = int(forecast_data['list'][0]['pop'] * 100)

    return {
        "city": current["name"],
        "temperature": round(current["main"]["temp"]),
        "feels_like": round(current["main"]["feels_like"]),
        "description": current["weather"][0]["description"].title(),
        "humidity": current["main"]["humidity"],
        "wind_speed": round(current["wind"]["speed"]),
        "rain_probability": rain_prob,
        "forecast_raw": forecast_data['list']
    }

def get_forecast_slots(forecast_raw):
    """Return up to 24 forecast slots covering today and tomorrow in PKT."""
    slots = []
    now_pkt = datetime.now(PKT)
    today_date = now_pkt.date()

    for item in forecast_raw:
        dt_utc = datetime.fromtimestamp(item['dt'], tz=timezone.utc)
        dt_pkt = dt_utc.astimezone(PKT)

        # Include today + tomorrow to get close to 24 entries
        if dt_pkt.date() not in (today_date, today_date + timedelta(days=1)):
            continue

        desc = item['weather'][0]['description'].lower()
        if 'rain' in desc:      icon = "🌧️"
        elif 'drizzle' in desc: icon = "🌦️"
        elif 'thunder' in desc: icon = "⛈️"
        elif 'snow' in desc:    icon = "❄️"
        elif 'cloud' in desc:   icon = "☁️"
        elif 'clear' in desc:   icon = "☀️"
        elif 'haze' in desc or 'fog' in desc or 'mist' in desc: icon = "🌫️"
        else:                   icon = "🌤️"

        slots.append({
            "time": dt_pkt.strftime("%I:%M %p").lstrip("0"),
            "label": dt_pkt.strftime("%a"),          # Mon, Tue…
            "icon": icon,
            "temp": round(item['main']['temp']),
            "desc": item['weather'][0]['description'].title(),
            "rain": int(item['pop'] * 100),
            "humidity": item['main']['humidity'],
        })

        if len(slots) >= 24:
            break

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

def get_groq_advice(weather, forecast_slots, groq_key):
    client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")

    # Build a brief summary of how the day looks
    day_snapshot = ", ".join(
        f"{s['time']} {s['temp']}C {s['desc']}" for s in forecast_slots[:8]
    )

    prompt = f"""
You are a friendly morning weather assistant for {weather['city']}, Pakistan.
Write ONLY these 3 sections. Be concise (2-3 sentences each max).

1. Weather Summary — describe how the day evolves based on: {day_snapshot}
2. What to Wear — based on {weather['rain_probability']}% rain chance and {weather['temperature']}C.
3. Daily Motivation — one uplifting sentence.

CRITICAL: Separate each section with exactly ### on its own line. No titles, no headers.

Example:
Morning starts cool and cloudy...
###
Carry a light jacket...
###
Every sunrise is a fresh start!
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def build_forecast_rows_html(slots):
    """Build HTML rows for all forecast slots."""
    rows = ""
    for i, s in enumerate(slots):
        bg = "rgba(255,255,255,0.04)" if i % 2 == 0 else "rgba(255,255,255,0.02)"
        rain_color = "#7eadd4" if s['rain'] < 40 else ("#f0a500" if s['rain'] < 70 else "#e05a5a")
        rows += (
            '<div style="display:flex;align-items:center;padding:10px 14px;'
            f'background:{bg};border-radius:10px;margin-bottom:4px;">'

            # Time + day label
            f'<div style="width:90px;flex-shrink:0;">'
            f'<div style="font-size:13px;color:#ffffff;font-weight:500;">{s["time"]}</div>'
            f'<div style="font-size:11px;color:#5a7a9a;letter-spacing:1px;">{s["label"]}</div>'
            f'</div>'

            # Icon
            f'<div style="width:36px;font-size:22px;text-align:center;flex-shrink:0;">{s["icon"]}</div>'

            # Description
            f'<div style="flex:1;font-size:13px;color:#a8c4e8;padding:0 10px;">{s["desc"]}</div>'

            # Temp
            f'<div style="width:52px;text-align:right;font-size:15px;font-weight:600;color:#ffffff;flex-shrink:0;">'
            f'{s["temp"]}°C</div>'

            # Rain
            f'<div style="width:46px;text-align:right;font-size:12px;color:{rain_color};flex-shrink:0;padding-left:8px;">'
            f'&#x1F4A7;{s["rain"]}%</div>'

            '</div>'
        )
    return rows

def build_html_email(weather, namaz, advice, forecast_slots):
    today = datetime.now(PKT).strftime("%A, %B %d %Y")

    sections = [s.strip() for s in advice.split('###')]
    summary    = sections[0] if len(sections) > 0 else "Enjoy the weather today!"
    outfit     = sections[1] if len(sections) > 1 else "Dress comfortably."
    motivation = sections[2] if len(sections) > 2 else "Have a great day!"

    desc = weather['description'].lower()
    if 'rain' in desc:       weather_icon = "&#127783;&#65039;"   # 🌧️
    elif 'cloud' in desc:    weather_icon = "&#9925;&#65039;"      # ☁️
    elif 'clear' in desc:    weather_icon = "&#9728;&#65039;"      # ☀️
    elif 'snow' in desc:     weather_icon = "&#10052;&#65039;"     # ❄️
    elif 'storm' in desc:    weather_icon = "&#9928;&#65039;"      # ⛈️
    elif 'haze' in desc or 'fog' in desc: weather_icon = "&#127787;&#65039;"  # 🌫️
    else:                    weather_icon = "&#127780;&#65039;"    # 🌤️

    forecast_html = build_forecast_rows_html(forecast_slots)

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=DM+Sans:wght@300;400;500&display=swap');
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:#0f0f1a; font-family:'DM Sans',sans-serif; color:#e8e8f0; padding:20px; }
  .wrapper {
    max-width:600px; margin:0 auto;
    background:linear-gradient(145deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);
    border-radius:24px; overflow:hidden; border:1px solid rgba(255,255,255,0.08);
  }
  .header {
    background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
    padding:40px 36px 32px; text-align:center; position:relative;
  }
  .header::after {
    content:''; position:absolute; bottom:-1px; left:0; right:0; height:40px;
    background:#1a1a2e; clip-path:ellipse(55% 100% at 50% 100%);
  }
  .date-badge {
    display:inline-block; background:rgba(255,255,255,0.12);
    border:1px solid rgba(255,255,255,0.2); border-radius:20px;
    padding:6px 16px; font-size:12px; letter-spacing:1.5px;
    text-transform:uppercase; margin-bottom:20px; color:#a8c4e8;
  }
  .city-name { font-family:'Playfair Display',serif; font-size:36px; font-weight:700; color:#fff; margin-bottom:6px; letter-spacing:-0.5px; }
  .country { font-size:13px; color:#7eadd4; letter-spacing:2px; text-transform:uppercase; }
  .temp-hero { text-align:center; padding:40px 36px 20px; }
  .weather-icon { font-size:64px; line-height:1; margin-bottom:12px; display:block; }
  .temp-display { font-family:'Playfair Display',serif; font-size:80px; font-weight:700; color:#fff; line-height:1; letter-spacing:-3px; }
  .temp-unit { font-size:36px; color:#7eadd4; vertical-align:super; }
  .weather-desc { font-size:18px; color:#a8c4e8; margin-top:8px; font-weight:300; letter-spacing:0.5px; }
  .feels-like { font-size:13px; color:#6a8aaa; margin-top:6px; }
  .stats-row {
    display:flex; margin:24px 36px;
    background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08);
    border-radius:16px; overflow:hidden;
  }
  .stat { flex:1; text-align:center; padding:16px 8px; border-right:1px solid rgba(255,255,255,0.06); }
  .stat:last-child { border-right:none; }
  .stat-icon { font-size:20px; display:block; margin-bottom:6px; }
  .stat-value { font-size:18px; font-weight:500; color:#fff; }
  .stat-label { font-size:11px; color:#5a7a9a; text-transform:uppercase; letter-spacing:1px; margin-top:2px; }
  .section { margin:0 36px 24px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07); border-radius:16px; padding:24px; }
  .section-header { display:flex; align-items:center; gap:10px; margin-bottom:14px; }
  .section-icon { font-size:20px; }
  .section-title { font-size:11px; text-transform:uppercase; letter-spacing:2px; color:#5a7a9a; font-weight:500; }
  .section-body { font-size:15px; line-height:1.7; color:#c8d8e8; font-weight:300; }
  .namaz-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:4px; }
  .namaz-item { background:rgba(255,255,255,0.04); border-radius:10px; padding:12px 14px; display:flex; justify-content:space-between; align-items:center; }
  .namaz-name { font-size:13px; color:#7eadd4; font-weight:500; }
  .namaz-time { font-size:13px; color:#fff; font-weight:400; }
  .motivation { margin:0 36px 24px; background:linear-gradient(135deg,rgba(30,60,114,0.5),rgba(42,82,152,0.3)); border:1px solid rgba(126,173,212,0.2); border-radius:16px; padding:24px; text-align:center; }
  .motivation-text { font-family:'Playfair Display',serif; font-size:17px; color:#a8c4e8; line-height:1.6; font-style:italic; }
  .footer { text-align:center; padding:20px 36px 32px; border-top:1px solid rgba(255,255,255,0.05); }
  .footer-text { font-size:12px; color:#3a5a7a; letter-spacing:0.5px; }
  .footer-brand { font-size:13px; color:#5a7a9a; margin-top:6px; font-weight:500; }
</style>
</head>
<body>
<div class="wrapper">

  <div class="header">
    <div class="date-badge">""" + today + """</div>
    <div class="city-name">""" + weather['city'] + """</div>
    <div class="country">Pakistan &nbsp;|&nbsp; Daily Briefing</div>
  </div>

  <div class="temp-hero">
    <span class="weather-icon">""" + weather_icon + """</span>
    <div><span class="temp-display">""" + str(weather['temperature']) + """<span class="temp-unit">°C</span></span></div>
    <div class="weather-desc">""" + weather['description'] + """</div>
    <div class="feels-like">Feels like """ + str(weather['feels_like']) + """°C</div>
  </div>

  <div class="stats-row">
    <div class="stat">
      <span class="stat-icon">&#128167;</span>
      <div class="stat-value">""" + str(weather['humidity']) + """%</div>
      <div class="stat-label">Humidity</div>
    </div>
    <div class="stat">
      <span class="stat-icon">&#9748;</span>
      <div class="stat-value">""" + str(weather['rain_probability']) + """%</div>
      <div class="stat-label">Rain</div>
    </div>
    <div class="stat">
      <span class="stat-icon">&#128168;</span>
      <div class="stat-value">""" + str(weather['wind_speed']) + """ m/s</div>
      <div class="stat-label">Wind</div>
    </div>
  </div>

  <div class="section">
    <div class="section-header">
      <span class="section-icon">&#127780;&#65039;</span>
      <span class="section-title">Weather Summary</span>
    </div>
    <div class="section-body">""" + summary + """</div>
  </div>

  <div class="section">
    <div class="section-header">
      <span class="section-icon">&#128085;</span>
      <span class="section-title">What to Wear &amp; Prep</span>
    </div>
    <div class="section-body">""" + outfit + """</div>
  </div>

  <!-- 24-HOUR FORECAST -->
  <div class="section">
    <div class="section-header">
      <span class="section-icon">&#128336;</span>
      <span class="section-title">24-Hour Forecast</span>
    </div>
    <div style="margin-top:4px;">""" + forecast_html + """</div>
  </div>

  <div class="section">
    <div class="section-header">
      <span class="section-icon">&#128332;</span>
      <span class="section-title">Prayer &amp; Sun Schedule</span>
    </div>
    <div class="namaz-grid">
      <div class="namaz-item"><span class="namaz-name">&#127749; Fajr</span><span class="namaz-time">""" + namaz['Fajr'] + """</span></div>
      <div class="namaz-item"><span class="namaz-name">&#9728;&#65039; Sunrise</span><span class="namaz-time">""" + namaz['Sunrise'] + """</span></div>
      <div class="namaz-item"><span class="namaz-name">&#127774; Dhuhr</span><span class="namaz-time">""" + namaz['Dhuhr'] + """</span></div>
      <div class="namaz-item"><span class="namaz-name">&#127751; Asr</span><span class="namaz-time">""" + namaz['Asr'] + """</span></div>
      <div class="namaz-item"><span class="namaz-name">&#127750; Maghrib</span><span class="namaz-time">""" + namaz['Maghrib'] + """</span></div>
      <div class="namaz-item"><span class="namaz-name">&#127769; Isha</span><span class="namaz-time">""" + namaz['Isha'] + """</span></div>
    </div>
  </div>

  <div class="motivation">
    <div class="motivation-text">"" + motivation + ""</div>
  </div>

  <div class="footer">
    <div class="footer-text">Delivered fresh every morning &#9749;</div>
    <div class="footer-brand">&#10024; Made &amp; Designed by Abdullah</div>
  </div>

</div>
</body>
</html>"""

    return html

def send_email(sender_email, sender_password, recipient_email, weather, namaz, advice, forecast_slots):
    subject = "&#128241; Your Daily Weather & Schedule App"

    html_content = build_html_email(weather, namaz, advice, forecast_slots)

    msg = MIMEMultipart('alternative')
    msg["Subject"] = "📱 Your Daily Weather & Schedule App"
    msg["From"] = sender_email
    msg["To"] = recipient_email

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

    weather_data   = get_weather(city, weather_key)
    forecast_slots = get_forecast_slots(weather_data.pop("forecast_raw"))
    namaz_data     = get_namaz_times(city)
    daily_advice   = get_groq_advice(weather_data, forecast_slots, groq_key)

    send_email(email, password, recipient, weather_data, namaz_data, daily_advice, forecast_slots)

if __name__ == "__main__":
    main()
