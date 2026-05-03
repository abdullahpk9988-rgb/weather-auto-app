import os
import smtplib
from email.message import EmailMessage
import requests

def get_weather(city, api_key):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}
    response = requests.get(url, params=params).json()
    
    return {
        "city": response["name"],
        "temperature": response["main"]["temp"],
        "description": response["weather"][0]["description"],
        "humidity": response["main"]["humidity"],
        "wind_speed": response["wind"]["speed"],
    }

def smart_agent_advice(weather):
    """Local, foolproof logic to tell you what to wear without an API key."""
    temp = weather["temperature"]
    description = weather["description"].lower()

    advice = ""
    if temp >= 30:
        advice = "It's hot today. Wear light, breathable clothes and stay hydrated."
    elif temp >= 20:
        advice = "The weather is pleasant. Normal, comfortable clothing is perfect."
    elif temp >= 10:
        advice = "It's a bit cool. Grab a light jacket or hoodie before heading out."
    else:
        advice = "It's cold. Wear warm layers and a good jacket."

    if "rain" in description or "shower" in description:
        advice += " Also, take an umbrella—it looks like rain."
    
    return advice

def send_email(sender_email, sender_password, weather, advice):
    subject = "🌤️ Your Daily Weather & Style Guide"
    
    body = f"""Hello Abdullah,

Here is your daily update:
Temperature: {weather['temperature']}°C
Condition: {weather['description'].title()}

🧠 Smart Agent Advice:
{advice}
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = sender_email
    msg.set_content(body)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)

def main():
    email = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    weather_key = os.environ["WEATHER_API_KEY"]
    
    weather_data = get_weather("Islamabad", weather_key)
    daily_advice = smart_agent_advice(weather_data)
    send_email(email, password, weather_data, daily_advice)

if __name__ == "__main__":
    main()
