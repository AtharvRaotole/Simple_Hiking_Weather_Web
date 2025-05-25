import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app) # Allows requests from your frontend development server

# IMPORTANT: Replace with your actual OpenWeatherMap API key
# Consider using environment variables for real applications
API_KEY = "bcc690e1b6c3f757ce9d4f22745bb2f8"
WEATHER_API_URL = "http://api.openweathermap.org/data/2.5/forecast" # 5 day / 3 hour forecast

# --- Helper Function: Check if weather conditions meet preferences ---
def check_preferences(forecast_hour, prefs):
    """Checks if a single 3-hour forecast chunk meets user preferences."""
    # Directly use the temperature value as Celsius since we requested metric units
    temp_celsius = forecast_hour['main']['temp'] # Corrected line
    wind_speed_mps = forecast_hour['wind']['speed']
    precip_prob = forecast_hour.get('pop', 0) # Probability of precipitation (0 to 1)

    # Get preferences safely, providing defaults if missing
    pref_max_temp = float(prefs.get('maxTemp', 100))
    pref_min_temp = float(prefs.get('minTemp', -100))
    pref_max_wind = float(prefs.get('maxWind', 100))
    pref_max_precip = float(prefs.get('maxPrecip', 1.0)) # Pref is 0-1 here

    # --- The actual checks ---
    if not (pref_min_temp <= temp_celsius <= pref_max_temp):
        # Use the correct temp_celsius variable in the reason string
        return False, f"Temp {temp_celsius:.1f}°C outside range ({pref_min_temp}-{pref_max_temp}°C)"
    if wind_speed_mps > pref_max_wind:
        return False, f"Wind {wind_speed_mps:.1f} m/s too high (max {pref_max_wind} m/s)"
    if precip_prob > pref_max_precip:
        return False, f"Precipitation chance {precip_prob*100:.0f}% too high (max {pref_max_precip*100:.0f}%)"

    # If all checks pass:
    return True, "Conditions Met"

# --- API Endpoint ---
@app.route('/get_hike_forecast', methods=['POST'])
def get_hike_forecast():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    location = data.get('location')
    preferences = data.get('preferences', {}) # Get preferences dict

    if not location:
        return jsonify({"error": "Location is required"}), 400
    if not API_KEY or API_KEY == "YOUR_OPENWEATHERMAP_API_KEY":
         return jsonify({"error": "Server configuration error: Missing API Key"}), 500

    # --- Call OpenWeatherMap API ---
    params = {
        'q': location,
        'appid': API_KEY,
        'units': 'metric' # Use metric for easier preference comparison if needed, but API gives Kelvin by default
    }
    try:
        response = requests.get(WEATHER_API_URL, params=params)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        weather_data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling weather API: {e}")
        # Try to parse error message from OpenWeatherMap if possible
        try:
            error_details = response.json()
            return jsonify({"error": f"Could not fetch weather data: {error_details.get('message', str(e))}"}), 500
        except: # Handle cases where response is not JSON
             return jsonify({"error": f"Could not fetch weather data: {str(e)}"}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


    # --- Process Forecast Data ---
    processed_forecast = []
    daily_summary = {} # To aggregate results by day

    if 'list' not in weather_data:
         return jsonify({"error": "Unexpected API response format from OpenWeatherMap"}), 500

    for forecast_item in weather_data['list']:
        dt_object = datetime.fromtimestamp(forecast_item['dt'])
        date_str = dt_object.strftime('%Y-%m-%d')
        time_str = dt_object.strftime('%H:%M')

        # Initialize day if not seen before
        if date_str not in daily_summary:
            daily_summary[date_str] = {'good_periods': 0, 'total_periods': 0, 'details': [], 'overall_good': True, 'reasons_bad': set()}

        # Check preferences for this 3-hour slot
        is_good, reason = check_preferences(forecast_item, preferences)

        daily_summary[date_str]['total_periods'] += 1
        if is_good:
            daily_summary[date_str]['good_periods'] += 1
        else:
            daily_summary[date_str]['overall_good'] = False # If any period is bad, mark the day potentially bad
            daily_summary[date_str]['reasons_bad'].add(reason.split(" (")[0]) # Add the general reason

        # Store detailed info (optional, could simplify)
        daily_summary[date_str]['details'].append({
            "time": time_str,
            # Use the Celsius value directly, just like in check_preferences
            "temp_c": forecast_item['main']['temp'], # <--- CORRECTED LINE
            "description": forecast_item['weather'][0]['description'],
            "wind_mps": forecast_item['wind']['speed'],
            "precip_prob": forecast_item.get('pop', 0) * 100, # Percentage
            "is_good_period": is_good,
            "reason": reason if not is_good else ""
        })

    # --- Prepare Final Response ---
    # Convert daily summary sets to lists for JSON serialization
    for date_str, summary in daily_summary.items():
         summary['reasons_bad'] = list(summary['reasons_bad'])
         # Decide if the day is *overall* good. Let's say >50% of daylight periods are good?
         # This logic can be refined. For simplicity now, we'll just use the 'overall_good' flag (any bad period makes it bad)
         # A more nuanced approach might check only typical hiking hours (e.g., 9 AM - 5 PM)
         summary['recommendation'] = "Good" if summary['overall_good'] else "Potentially Bad"


    return jsonify({
        "location_name": weather_data.get('city', {}).get('name', location),
        "daily_summary": daily_summary,
        "preferences_used": preferences # Echo back preferences for clarity
        })

if __name__ == '__main__':
    # Use 0.0.0.0 to be accessible on your network if needed, otherwise 127.0.0.1
    app.run(debug=True, host='127.0.0.1', port=5000) # Run on port 5000