# earth-observation-api

## To run this,can be made in two steps.

### With local host, you can run this command: 'python flaskApp.py'
then access this on "http://127.0.0.1:5000/".

### To test the API, access it on "http://127.0.0.1:5000/generate_map" as **POST**

The format of the jsaon to be sent is:

{
  "roi": [[[30.0348, -1.9441], [30.1048, -1.9441], [30.1048, -1.9291], [30.0348, -1.9291], [30.0348, -1.9441]]],
  "feature": "LST"
}

current suppoting features are:
- SM: Soil moisture
- NDVI: vegetation index
- LST: Land surface temperature

roi: Is region of interest, as coordinate.

The response also will be JSON format
