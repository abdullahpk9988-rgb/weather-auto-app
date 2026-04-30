# Weather Email Project

This project sends a daily weather report email using OpenWeatherMap and Gmail SMTP.

## Files
- `weather_email.py`: Main script
- `requirements.txt`: Python dependency
- `.env.example`: Example environment variables

## Setup
1. Install dependency:
   `pip install -r requirements.txt`
2. Set environment variables:
   - `EMAIL_ADDRESS`
   - `EMAIL_PASSWORD` (Gmail App Password)
   - `WEATHER_API_KEY`
   - Optional: `WEATHER_CITY` (default is `Islamabad`)
   - Optional: `EMAIL_RECIPIENT` (default is `EMAIL_ADDRESS`)
3. Run:
   `python weather_email.py`

## Daily Automation
Instructions are included in comments at the top of `weather_email.py` for:
- Windows Task Scheduler
- Linux/Mac cron
