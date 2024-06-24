
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import ee
import geemap
from google.oauth2 import service_account
from datetime import datetime, timedelta
import json
import os

import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Path to your service account JSON key file
service_account_key = 'service_account_key.json'

# Define the required scope for Earth Engine
scopes = ['https://www.googleapis.com/auth/earthengine']

# Authenticate and initialize the Earth Engine library with the service account credentials
credentials = service_account.Credentials.from_service_account_file(service_account_key, scopes=scopes)
ee.Initialize(credentials)

def calculate_monthly_values(start_date, end_date, roi, feature):
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%Y-%m-%d')
    current_date = start_date
    monthly_values = []

    while current_date <= end_date:
        next_date = (current_date + timedelta(days=32)).replace(day=1)
        month_start = current_date.strftime('%Y-%m-%d')
        month_end = (next_date - timedelta(days=1)).strftime('%Y-%m-%d')

        if feature == 'NDVI':
            collection = ee.ImageCollection('COPERNICUS/S2_SR').filterBounds(roi).filterDate(month_start, month_end)
            image = collection.map(lambda img: img.normalizedDifference(['B8', 'B4'])).mean()

        elif feature == 'SM':
            collection = ee.ImageCollection('NASA/SMAP/SPL3SMP_E/006').filterBounds(roi).filterDate(month_start, month_end)
            if collection.size().getInfo() == 0:
                logger.error(f"No SM data available for the date range: {month_start} to {month_end}")
                monthly_values.append({'date': month_start, 'value': None})
                current_date = next_date
                continue
            image = collection.select('soil_moisture_am').mean()
            # collection = ee.ImageCollection('NASA_USDA/HSL/SMAP10KM_soil_moisture').filterBounds(roi).filterDate(month_start, month_end)
            # image = collection.select('ssm').mean()

        elif feature == 'LST':
            collection = ee.ImageCollection('MODIS/061/MOD21A1D').filterBounds(roi).filterDate(month_start, month_end)
            if collection.size().getInfo() == 0:
                logger.error(f"No LST data available for the date range: {month_start} to {month_end}")
                monthly_values.append({'date': month_start, 'value': None})
                current_date = next_date
                continue
            image = collection.select('LST_1KM').mean().subtract(273.15)  # Convert to Celsius

        value = image.reduceRegion(reducer=ee.Reducer.mean(), geometry=roi, scale=1000, maxPixels=1e9).getInfo()

        monthly_values.append({
            'date': month_start,
            'value': value.get('nd' if feature == 'NDVI' else 'sm' if feature == 'SM' else 'LST_1KM', None)
        })

        current_date = next_date

    return monthly_values

def generate_map_and_values(roi_coordinates, feature):
    roi = ee.Geometry.Polygon(roi_coordinates)
    start_date = '2023-01-01'
    end_date = datetime.utcnow().strftime('%Y-%m-%d')

    if feature == 'NDVI':
        sentinel2 = ee.ImageCollection('COPERNICUS/S2_SR').filterBounds(roi).filterDate(start_date, end_date).sort('system:time_start', False).first()
        image = sentinel2.normalizedDifference(['B8', 'B4'])
        visualization_params = {'min': -1, 'max': 1, 'palette': ['red', 'yellow', 'green']}
        
    elif feature == 'SM':
        collection = ee.ImageCollection('NASA/SMAP/SPL3SMP_E/006').filterBounds(roi).filterDate(start_date, end_date)
        if collection.size().getInfo() == 0:
            raise ValueError('No SM data available for the given ROI and date range.')
        image = collection.select('soil_moisture_am').mean()
        visualization_params = {'min': 0, 'max': 1, 'palette': ['0300ff', '418504', 'efff07', 'efff07', 'ff0303']}

        # collection = ee.ImageCollection('NASA_USDA/HSL/SMAP10KM_soil_moisture').filterBounds(roi).filterDate(start_date, end_date)
        # image = collection.sort('system:time_start', False).first()
        # if image:
        #     visualization_params = {'bands': ['ssm'], 'min': 0, 'max': 1, 'palette': ['blue', 'white', 'brown']}
        # else:
        #     raise ValueError('No images found for the given ROI and date range for Soil Moisture.')

    elif feature == 'LST':
        collection = ee.ImageCollection('MODIS/061/MOD21A1D').filterBounds(roi).filterDate(start_date, end_date)
        if collection.size().getInfo() == 0:
            raise ValueError('No LST data available for the given ROI and date range.')
        image = collection.select('LST_1KM').mean().multiply(0.02).subtract(273.15)  # Convert to Celsius
        visualization_params = {'min': -10, 'max': 40, 'palette': ['blue', 'white', 'red']}

    def get_map_id_params(image, vis_params):
        map_id = image.getMapId(vis_params)
        return {
            'mapid': map_id['mapid'],
            'token': map_id['token'],
            'url_format': map_id['tile_fetcher'].url_format
        }

    map_config = {
        'roi': roi_coordinates,
        'start_date': start_date,
        'end_date': end_date,
        'feature': feature,
        'visualization': get_map_id_params(image, visualization_params)
    }

    monthly_values = calculate_monthly_values(start_date, end_date, roi, feature)
    return map_config, monthly_values

@app.route('/generate_map', methods=['POST'])
def generate_map():
    data = request.json
    roi = data.get('roi')
    feature = data.get('feature')
    if not roi:
        return jsonify({'error': 'ROI is required'}), 400
    if not feature:
        return jsonify({'error': 'Feature is required'}), 400

    try:
        map_config, monthly_values = generate_map_and_values(roi, feature)
        return jsonify({
            'map_config': map_config,
            'monthly_values': monthly_values
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)

