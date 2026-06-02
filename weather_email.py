import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from openai import OpenAI
from datetime import datetime


def get_weather_current(city, api_key):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}
    data = requests.get(url, params=params).json()
    return {
        "city": data["name"],
        "temperature": round(data["main"]["temp"]),
        "feels_like": round(data["main"]["feels_like"]),
        "description": data["weather"][0]["description"].title(),
        "humidity": data["main"]["humidity"],
        "wind_speed": round(data["wind"]["speed"]),
    }


def get_forecast_slots(city, api_key):
    """
    Pull 5-day/3-hour forecast and extract 8 representative slots for TODAY
    covering the full day: early morning, morning, late morning, noon,
    afternoon, late afternoon, evening, night.
    """
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city, "appid": api_key, "units": "metric", "cnt": 16}
    data = requests.get(url, params=params).json()

    slots = []
    for item in data["list"]:
        dt = datetime.utcfromtimestamp(item["dt"])
        # Convert UTC to PKT (UTC+5)
        pkt_hour = (dt.hour + 5) % 24
        pkt_label = datetime(dt.year, dt.month, dt.day, pkt_hour).strftime("%I:%M %p").lstrip("0")

        desc = item["weather"][0]["description"].title()
        temp = round(item["main"]["temp"])
        feels = round(item["main"]["feels_like"])
        rain_prob = round(item["pop"] * 100)
        humidity = item["main"]["humidity"]
        wind = round(item["wind"]["speed"])

        # Pick weather emoji
        d = desc.lower()
        if "thunder"    in d: icon = "⛈️"
        elif "rain"     in d: icon = "🌧️"
        elif "drizzle"  in d: icon = "🌦️"
        elif "snow"     in d: icon = "❄️"
        elif "fog"      in d or "haze" in d or "mist" in d: icon = "🌫️"
        elif "cloud"    in d: icon = "☁️"
        elif "clear"    in d: icon = "☀️"
        else:                 icon = "🌤️"

        slots.append({
            "hour": pkt_hour,
            "label": pkt_label,
            "desc": desc,
            "temp": temp,
            "feels": feels,
            "rain": rain_prob,
            "humidity": humidity,
            "wind": wind,
            "icon": icon,
        })

    # Pick up to 8 evenly spread slots
    if len(slots) > 8:
        step = len(slots) / 8
        slots = [slots[round(i * step)] for i in range(8)]

    return slots


def get_namaz_times(city):
    url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Pakistan&method=1"
    response = requests.get(url).json()
    timings = response["data"]["timings"]
    for key, value in timings.items():
        clean = value.split(" ")[0]
        try:
            t = datetime.strptime(clean, "%H:%M")
            timings[key] = t.strftime("%I:%M %p").lstrip("0")
        except Exception:
            pass
    return timings


def get_groq_summary(weather, slots, groq_key):
    client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")

    slot_text = "\n".join(
        f"  {s['label']}: {s['temp']}°C, {s['desc']}, rain {s['rain']}%"
        for s in slots
    )

    prompt = f"""
You are a concise morning weather assistant for {weather['city']}, Pakistan.
Based on the hourly forecast below, write EXACTLY 3 sections separated by ###.
No section titles. No markdown. 2-3 sentences each max.

HOURLY FORECAST:
{slot_text}

Section 1 — Overall day summary: how will the day evolve from morning to night?
Section 2 — What to wear and prepare for: umbrella? light jacket? sunscreen?
Section 3 — One powerful motivational sentence to start the day.
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def build_html_email(weather, slots, namaz, advice, sender_email):
    today_full  = datetime.now().strftime("%A, %B %d · %Y")
    today_short = datetime.now().strftime("%d %b %Y")

    parts = [s.strip() for s in advice.split("###")]
    summary    = parts[0] if len(parts) > 0 else "A great day ahead!"
    outfit     = parts[1] if len(parts) > 1 else "Dress comfortably."
    motivation = parts[2] if len(parts) > 2 else "Make today count."

    # Hero icon from first slot
    hero_icon  = slots[0]["icon"] if slots else "🌤️"
    mailto_link = (
        "mailto:" + sender_email
        + "?subject=Re%3A%20Your%20Daily%20Weather%20%26%20Schedule%20App"
    )

    # Build hourly forecast rows
    forecast_rows = ""
    for s in slots:
        forecast_rows += """
        <div class="fc-row">
          <span class="fc-time">FC_TIME</span>
          <span class="fc-icon">FC_ICON</span>
          <span class="fc-desc">FC_DESC</span>
          <span class="fc-temp">FC_TEMP&deg;C</span>
          <span class="fc-rain">FC_RAIN% rain</span>
        </div>""".replace("FC_TIME", s["label"]) \
                  .replace("FC_ICON", s["icon"]) \
                  .replace("FC_DESC", s["desc"]) \
                  .replace("FC_TEMP", str(s["temp"])) \
                  .replace("FC_RAIN", str(s["rain"]))

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400;1,600&family=Outfit:wght@300;400;500;600&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{background:#06060a;font-family:'Outfit',-apple-system,sans-serif;-webkit-font-smoothing:antialiased;padding:32px 12px 64px;}
.wrap{max-width:600px;margin:0 auto;}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;padding:0 4px;}
.topbar-brand{font-family:'Cormorant Garamond',serif;font-size:13px;font-weight:600;color:#c8963c;letter-spacing:0.12em;text-transform:uppercase;}
.topbar-date{font-size:11px;color:#2a2a3a;letter-spacing:0.08em;}
.card{background:#0c0c12;border-radius:24px;border:1px solid rgba(200,150,60,0.12);overflow:hidden;box-shadow:0 32px 64px rgba(0,0,0,0.7);}
/* HERO */
.hero{position:relative;overflow:hidden;min-height:260px;background:linear-gradient(160deg,#0e0e1a 0%,#12100a 50%,#0a0a0e 100%);}
.hero-glow-top{position:absolute;top:-80px;left:50%;transform:translateX(-50%);width:400px;height:300px;background:radial-gradient(ellipse,rgba(200,150,60,0.12) 0%,transparent 70%);pointer-events:none;}
.hero-glow-side{position:absolute;bottom:-40px;right:-60px;width:200px;height:200px;background:radial-gradient(circle,rgba(200,150,60,0.06) 0%,transparent 70%);pointer-events:none;}
.hero-content{position:relative;z-index:2;padding:36px 36px 32px;display:flex;align-items:flex-start;justify-content:space-between;gap:20px;}
.hero-left{flex:1;}
.hero-eyebrow{display:inline-flex;align-items:center;gap:7px;background:rgba(200,150,60,0.08);border:1px solid rgba(200,150,60,0.18);border-radius:99px;padding:5px 13px;margin-bottom:16px;}
.eyebrow-dot{width:5px;height:5px;border-radius:50%;background:#c8963c;}
.eyebrow-text{font-size:10px;font-weight:500;letter-spacing:0.16em;text-transform:uppercase;color:#c8963c;}
.hero-city{font-family:'Cormorant Garamond',serif;font-size:50px;font-weight:700;color:#f5f0e8;line-height:0.95;letter-spacing:-1px;}
.hero-country{font-size:12px;color:#3a3020;letter-spacing:0.2em;text-transform:uppercase;margin-top:10px;}
.hero-right{text-align:right;padding-top:8px;}
.temp-big{font-family:'Cormorant Garamond',serif;font-size:84px;font-weight:600;color:#ffffff;line-height:1;letter-spacing:-4px;}
.temp-deg{font-size:38px;color:#c8963c;vertical-align:super;}
.weather-icon-hero{font-size:26px;display:block;margin-bottom:4px;text-align:right;}
.temp-desc{font-size:14px;color:#6a5a3a;margin-top:4px;font-weight:300;}
.temp-feels{font-size:12px;color:#3a3020;margin-top:3px;}
/* GOLD RULE */
.gold-rule{height:1px;background:linear-gradient(90deg,transparent,rgba(200,150,60,0.4) 30%,rgba(200,150,60,0.4) 70%,transparent);margin:0 36px;}
/* STATS */
.stats-bar{display:flex;border-bottom:1px solid rgba(255,255,255,0.04);}
.stat{flex:1;text-align:center;padding:16px 8px;border-right:1px solid rgba(255,255,255,0.04);}
.stat:last-child{border-right:none;}
.stat-icon{font-size:18px;display:block;margin-bottom:6px;}
.stat-val{font-family:'Cormorant Garamond',serif;font-size:22px;font-weight:600;color:#e8dcc8;}
.stat-lbl{font-size:9.5px;text-transform:uppercase;letter-spacing:0.14em;color:#2a2518;margin-top:3px;}
/* HOURLY FORECAST */
.fc-wrap{padding:24px 36px 8px;}
.fc-title{font-size:9.5px;text-transform:uppercase;letter-spacing:0.18em;color:#3a3020;font-weight:600;margin-bottom:14px;display:flex;align-items:center;gap:8px;}
.fc-title::before{content:'';flex:0 0 16px;height:1px;background:rgba(200,150,60,0.3);}
.fc-title::after{content:'';flex:1;height:1px;background:rgba(200,150,60,0.3);}
.fc-row{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.03);}
.fc-row:last-child{border-bottom:none;}
.fc-time{font-size:12px;color:#6a5a3a;font-weight:500;min-width:68px;font-family:'Cormorant Garamond',serif;}
.fc-icon{font-size:18px;min-width:28px;text-align:center;}
.fc-desc{font-size:12px;color:#7a6a50;flex:1;font-weight:300;}
.fc-temp{font-family:'Cormorant Garamond',serif;font-size:17px;font-weight:600;color:#e8dcc8;min-width:52px;text-align:right;}
.fc-rain{font-size:11px;color:#3a3020;min-width:58px;text-align:right;}
/* CONTENT SECTIONS */
.sections{padding:8px 0;}
.sec{padding:22px 36px;border-bottom:1px solid rgba(255,255,255,0.03);display:flex;gap:20px;align-items:flex-start;}
.sec:last-child{border-bottom:none;}
.sec-left{flex-shrink:0;width:36px;text-align:center;padding-top:2px;}
.sec-num{font-family:'Cormorant Garamond',serif;font-size:11px;font-weight:600;color:#c8963c;display:block;margin-top:6px;}
.sec-icon{font-size:22px;display:block;}
.sec-right{flex:1;}
.sec-label{font-size:9.5px;text-transform:uppercase;letter-spacing:0.18em;color:#3a3020;font-weight:600;margin-bottom:8px;display:block;}
.sec-body{font-size:15px;line-height:1.75;color:#b8a888;font-weight:300;}
/* NAMAZ GRID */
.namaz-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:2px;}
.namaz-cell{background:rgba(200,150,60,0.04);border:1px solid rgba(200,150,60,0.1);border-radius:12px;padding:12px 10px;text-align:center;}
.namaz-emoji{font-size:16px;display:block;margin-bottom:5px;}
.namaz-name{font-size:10px;text-transform:uppercase;letter-spacing:0.12em;color:#4a3a20;font-weight:600;display:block;margin-bottom:4px;}
.namaz-time{font-family:'Cormorant Garamond',serif;font-size:15px;font-weight:600;color:#c8963c;}
/* MOTIVATION */
.motivation-wrap{margin:4px 36px 24px;background:linear-gradient(135deg,rgba(200,150,60,0.06),rgba(200,150,60,0.02));border:1px solid rgba(200,150,60,0.15);border-radius:18px;padding:26px 28px;text-align:center;}
.motivation-text{font-family:'Cormorant Garamond',serif;font-size:19px;font-weight:400;font-style:italic;color:#c8963c;line-height:1.55;}
/* REPLY BUTTON */
.reply-wrap{padding:4px 36px 28px;text-align:center;}
.reply-btn{display:inline-block;background:linear-gradient(135deg,#c8963c,#e8b84a);color:#0a0806 !important;text-decoration:none !important;font-size:13px;font-weight:600;padding:14px 36px;border-radius:99px;box-shadow:0 8px 24px rgba(200,150,60,0.25);}
.reply-hint{font-size:11px;color:#2a2518;margin-top:10px;}
/* FOOTER */
.footer{padding:16px 36px 20px;border-top:1px solid rgba(255,255,255,0.04);display:flex;align-items:center;justify-content:space-between;}
.footer-left{font-size:10.5px;color:#1e1810;font-family:'Courier New',monospace;}
.footer-right{font-family:'Cormorant Garamond',serif;font-size:13px;font-weight:600;color:#3a3020;}
.footer-right span{color:#c8963c;}
.bottom{text-align:center;margin-top:20px;font-size:10px;color:#18140c;letter-spacing:0.16em;text-transform:uppercase;}
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <span class="topbar-brand">Daily Briefing</span>
    <span class="topbar-date">TOPBAR_DATE</span>
  </div>
  <div class="card">
    <!-- HERO -->
    <div class="hero">
      <div class="hero-glow-top"></div>
      <div class="hero-glow-side"></div>
      <div class="hero-content">
        <div class="hero-left">
          <div class="hero-eyebrow">
            <div class="eyebrow-dot"></div>
            <span class="eyebrow-text">TODAY_FULL</span>
          </div>
          <div class="hero-city">CITY_NAME</div>
          <div class="hero-country">Islamic Republic of Pakistan</div>
        </div>
        <div class="hero-right">
          <span class="weather-icon-hero">HERO_ICON</span>
          <div class="temp-big">TEMPERATURE<span class="temp-deg">&#176;</span></div>
          <div class="temp-desc">DESCRIPTION</div>
          <div class="temp-feels">Feels like FEELS_LIKE&#176;C</div>
        </div>
      </div>
    </div>
    <!-- GOLD RULE -->
    <div class="gold-rule"></div>
    <!-- STATS -->
    <div class="stats-bar">
      <div class="stat"><span class="stat-icon">&#128167;</span><div class="stat-val">HUMIDITY%</div><div class="stat-lbl">Humidity</div></div>
      <div class="stat"><span class="stat-icon">&#127746;</span><div class="stat-val">RAIN_PROB%</div><div class="stat-lbl">Rain</div></div>
      <div class="stat"><span class="stat-icon">&#128168;</span><div class="stat-val">WIND m/s</div><div class="stat-lbl">Wind</div></div>
    </div>
    <!-- HOURLY FORECAST -->
    <div class="fc-wrap">
      <div class="fc-title">Hourly Forecast · Today</div>
      FORECAST_ROWS
    </div>
    <!-- SECTIONS -->
    <div class="sections">
      <div class="sec">
        <div class="sec-left"><span class="sec-icon">&#127780;</span><span class="sec-num">01</span></div>
        <div class="sec-right"><span class="sec-label">Day Summary</span><div class="sec-body">SUMMARY</div></div>
      </div>
      <div class="sec">
        <div class="sec-left"><span class="sec-icon">&#128085;</span><span class="sec-num">02</span></div>
        <div class="sec-right"><span class="sec-label">What to Wear &amp; Prep</span><div class="sec-body">OUTFIT</div></div>
      </div>
      <div class="sec">
        <div class="sec-left"><span class="sec-icon">&#128332;</span><span class="sec-num">03</span></div>
        <div class="sec-right">
          <span class="sec-label">Prayer &amp; Sun Schedule</span>
          <div class="namaz-grid">
            <div class="namaz-cell"><span class="namaz-emoji">&#127749;</span><span class="namaz-name">Fajr</span><span class="namaz-time">FAJR</span></div>
            <div class="namaz-cell"><span class="namaz-emoji">&#9728;</span><span class="namaz-name">Sunrise</span><span class="namaz-time">SUNRISE</span></div>
            <div class="namaz-cell"><span class="namaz-emoji">&#127774;</span><span class="namaz-name">Dhuhr</span><span class="namaz-time">DHUHR</span></div>
            <div class="namaz-cell"><span class="namaz-emoji">&#127751;</span><span class="namaz-name">Asr</span><span class="namaz-time">ASR</span></div>
            <div class="namaz-cell"><span class="namaz-emoji">&#127750;</span><span class="namaz-name">Maghrib</span><span class="namaz-time">MAGHRIB</span></div>
            <div class="namaz-cell"><span class="namaz-emoji">&#127769;</span><span class="namaz-name">Isha</span><span class="namaz-time">ISHA</span></div>
          </div>
        </div>
      </div>
    </div>
    <!-- MOTIVATION -->
    <div class="motivation-wrap">
      <div class="motivation-text">MOTIVATION</div>
    </div>
    <!-- REPLY BUTTON -->
    <div class="reply-wrap">
      <a href="MAILTO_LINK" class="reply-btn">&#128172; &nbsp; Ask a Question</a>
      <div class="reply-hint">Have a question about today's weather? Just hit reply — AI answers instantly.</div>
    </div>
    <!-- FOOTER -->
    <div class="footer">
      <div class="footer-left">auto-delivered · islamabad · pkt</div>
      <div class="footer-right">by <span>Abdullah Adnan</span></div>
    </div>
  </div>
  <div class="bottom">Powered by Groq &amp; OpenWeather · Built by Abdullah</div>
</div>
</body>
</html>"""

    html = html.replace("TOPBAR_DATE",   today_short)
    html = html.replace("TODAY_FULL",    today_full)
    html = html.replace("CITY_NAME",     weather["city"])
    html = html.replace("HERO_ICON",     hero_icon)
    html = html.replace("TEMPERATURE",   str(weather["temperature"]))
    html = html.replace("DESCRIPTION",   weather["description"])
    html = html.replace("FEELS_LIKE",    str(weather["feels_like"]))
    html = html.replace("HUMIDITY",      str(weather["humidity"]))
    html = html.replace("RAIN_PROB",     str(slots[0]["rain"] if slots else 0))
    html = html.replace("WIND",          str(weather["wind_speed"]))
    html = html.replace("FORECAST_ROWS", forecast_rows)
    html = html.replace("SUMMARY",       summary)
    html = html.replace("OUTFIT",        outfit)
    html = html.replace("MOTIVATION",    motivation)
    html = html.replace("FAJR",          namaz["Fajr"])
    html = html.replace("SUNRISE",       namaz["Sunrise"])
    html = html.replace("DHUHR",         namaz["Dhuhr"])
    html = html.replace("ASR",           namaz["Asr"])
    html = html.replace("MAGHRIB",       namaz["Maghrib"])
    html = html.replace("ISHA",          namaz["Isha"])
    html = html.replace("MAILTO_LINK",   mailto_link)

    return html


def send_email(sender_email, sender_password, recipient_email, weather, slots, namaz, advice):
    subject = "🌤️ Your Daily Weather & Schedule — Islamabad"

    html_content = build_html_email(weather, slots, namaz, advice, sender_email)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender_email
    msg["To"]      = recipient_email

    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)


def main():
    email       = os.environ["EMAIL_ADDRESS"]
    password    = os.environ["EMAIL_PASSWORD"]
    weather_key = os.environ["WEATHER_API_KEY"]
    groq_key    = os.environ["GROQ_API_KEY"]
    recipient   = os.environ.get("EMAIL_RECIPIENT", "abdullahpk998989898@gmail.com")

    city = "Islamabad"

    weather_data = get_weather_current(city, weather_key)
    forecast_slots = get_forecast_slots(city, weather_key)
    namaz_data   = get_namaz_times(city)
    daily_advice = get_groq_summary(weather_data, forecast_slots, groq_key)

    send_email(email, password, recipient, weather_data, forecast_slots, namaz_data, daily_advice)


if __name__ == "__main__":
    main()
