const form = document.getElementById('prefs-form');
const resultsDiv = document.getElementById('forecast-results');
const locationSpan = document.getElementById('result-location');
const loadingDiv = document.getElementById('loading');
const errorMessageDiv = document.getElementById('error-message');

// Backend API URL (make sure the port matches your Flask app)
const API_URL = 'http://127.0.0.1:5000/get_hike_forecast';

form.addEventListener('submit', async (event) => {
    event.preventDefault(); // Prevent default form submission

    // Clear previous results and errors
    resultsDiv.innerHTML = '';
    locationSpan.textContent = '...';
    errorMessageDiv.style.display = 'none';
    errorMessageDiv.textContent = '';
    loadingDiv.style.display = 'block'; // Show loading indicator

    // Get form data
    const formData = new FormData(form);
    const location = formData.get('location');
    const preferences = {
        minTemp: formData.get('minTemp'),
        maxTemp: formData.get('maxTemp'),
        maxWind: formData.get('maxWind'),
        // Convert percentage to decimal for API (0-1 range)
        maxPrecip: parseFloat(formData.get('maxPrecip')) / 100.0
    };

    try {
        // Send data to backend API
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ location, preferences }),
        });

        loadingDiv.style.display = 'none'; // Hide loading indicator

        if (!response.ok) {
             // Try to parse error message from backend JSON response
             let errorMsg = `HTTP error! Status: ${response.status}`;
             try {
                 const errorData = await response.json();
                 errorMsg = errorData.error || errorMsg; // Use backend error message if available
             } catch (e) {
                 // Ignore if response is not JSON
             }
            throw new Error(errorMsg);
        }

        const data = await response.json();

        // Display results
        locationSpan.textContent = data.location_name || location;
        displayForecast(data.daily_summary);

    } catch (error) {
        loadingDiv.style.display = 'none'; // Hide loading indicator
        console.error('Error fetching forecast:', error);
        errorMessageDiv.textContent = `Error: ${error.message}. Please check the location or backend console.`;
        errorMessageDiv.style.display = 'block'; // Show error message
    }
});

function displayForecast(dailySummary) {
    resultsDiv.innerHTML = ''; // Clear previous results

    // Sort dates (optional, but nice)
    const sortedDates = Object.keys(dailySummary).sort();

    if (sortedDates.length === 0) {
        resultsDiv.innerHTML = '<p>No forecast data available for the upcoming days.</p>';
        return;
    }


    sortedDates.forEach(date => {
        const dayData = dailySummary[date];
        const card = document.createElement('div');
        card.classList.add('forecast-card');

        // Determine recommendation class
        const recommendationClass = dayData.recommendation === 'Good' ? 'good' : 'bad';

        // Format date for display
        const displayDate = new Date(date + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' });

        let reasonsHTML = '';
        if (recommendationClass === 'bad' && dayData.reasons_bad.length > 0) {
             reasonsHTML = '<ul class="reasons">';
             dayData.reasons_bad.forEach(reason => {
                 reasonsHTML += `<li>${reason}</li>`;
             });
             reasonsHTML += '</ul>';
        }

        // Basic details (optional) - shows breakdown per 3hr block
        let detailsHTML = '<ul class="details-list">';
        dayData.details.forEach(detail => {
            const periodClass = detail.is_good_period ? '' : 'bad-period';
            detailsHTML += `<li class="${periodClass}">
                ${detail.time}: ${detail.temp_c.toFixed(1)}°C, ${detail.description}, Wind ${detail.wind_mps.toFixed(1)}m/s, Precip ${detail.precip_prob.toFixed(0)}% ${!detail.is_good_period ? `<small>(${detail.reason})</small>` : ''}
            </li>`;
        });
        detailsHTML += '</ul>';


        card.innerHTML = `
            <h3>
                ${displayDate}
                <span class="recommendation ${recommendationClass}">${dayData.recommendation}</span>
            </h3>
            ${reasonsHTML}
            ${detailsHTML}
            `;

        resultsDiv.appendChild(card);
    });
}