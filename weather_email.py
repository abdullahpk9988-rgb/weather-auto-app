import os
import smtplib
from email.message import EmailMessage
import requests
from openai import OpenAI
from datetime import datetime

def get_weather(city, api_key):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}
    current = requests.get(url, params=params).json()
    
    # Get forecast for rain probability
    forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
    forecast = requests.get(forecast_url, params=params).json()
    
    rain_prob = int(forecast['list'][0]['pop'] * 100) # Convert to percentage
    
    return {
        "city": current["name"],
        "temperature": current["main"]["temp"],
        "description": current["weather"][0]["description"],
        "rain_probability": rain_prob
    }

def get_namaz_times(city):
    # Free API for Namaz times
    url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Pakistan&method=1"
    response = requests.get(url).json()
    timings = response['data']['timings']
    
    # FORCING 12-HOUR FORMAT: Convert the API's 24-hour time to perfect 12-hour AM/PM
    for key, value in timings.items():
        # The API sometimes adds "(PKT)", so we split and grab just the time
        clean_time = value.split(" ")[0] 
        try:
            time_obj = datetime.strptime(clean_time, "%H:%M")
            # This converts it to "3:45 PM" and removes any weird leading zeros
            timings[key] = time_obj.strftime("%I:%M %p").lstrip("0")
        except Exception:
            pass # If it fails, just keep the original text
            
    return timings

def get_groq_advice(weather, namaz, groq_key):
    client = OpenAI(
        api_key=groq_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    # The Mega-Prompt
    prompt = f"""
    You are a highly intelligent and helpful morning assistant. Write a daily briefing for the user based on this data for {weather['city']}.
    
    Current Temp: {weather['temperature']}°C
    Condition: {weather['description']}
    Rain Probability: {weather['rain_probability']}%
    
    Namaz Times & Sun Schedule Today:
    Sunrise: {namaz['Sunrise']}
    Fajr: {namaz['Fajr']}
    Dhuhr: {namaz['Dhuhr']}
    Asr: {namaz['Asr']}
    Sunset: {namaz['Sunset']}
    Maghrib: {namaz['Maghrib']}
    Isha: {namaz['Isha']}
    
    Please format the email clearly with these sections:
    1. A quick summary of the day's weather (predict how the morning, afternoon, and night will feel).
    2. Specific clothing and preparation advice for the day (e.g., if rain probability is high, mention an umbrella).
    3. A clean, easy-to-read schedule of the Namaz times alongside the Sunrise/Sunset times. The times provided above are already in perfect 12-hour AM/PM format—do not change them, just print them exactly as they are.
    4. A short, motivating closing thought.
    """
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def send_email(sender_email, sender_password, recipient_email, advice):
    subject = "🌅 Your Ultimate Daily Briefing & Schedule"
    
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email 
    msg.set_content(advice)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)

def main():
    email = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    weather_key = os.environ["WEATHER_API_KEY"]
    groq_key = os.environ["GROQ_API_KEY"]
    recipient = os.environ.get("EMAIL_RECIPIENT", "adspk243@gmail.com")
    
    city = "Islamabad"
    
    weather_data = get_weather(city, weather_key)
    namaz_data = get_namaz_times(city)
    
    daily_advice = get_groq_advice(weather_data, namaz_data, groq_key)
    
    send_email(email, password, recipient, daily_advice)

if __name__ == "__main__":
    main()
