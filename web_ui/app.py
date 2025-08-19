from flask import Flask, render_template, request, Response, jsonify, send_from_directory
import sys
import os
import requests
from dotenv import load_dotenv
import json
import time
import csv
import re

# Add project root to path for imports when running inside web_ui
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from customer_scraper import stream_customer_scrape

load_dotenv()

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape/customers', methods=['POST'])
def scrape_customers():
    data = request.get_json(force=True)
    params = {
        'token': data.get('token'),
        'max_repos_per_query': data.get('max_repos_per_query', 30),
        'queries_raw': data.get('queries_raw', '').strip(),
        'output_filename': data.get('output_filename', 'leads.csv')
    }

    # Validate presence of queries
    if not params['queries_raw']:
        return jsonify({'phase': 'error', 'error': 'No queries supplied.'}), 400

    def generate():
        empty = True
        for update in stream_customer_scrape(params):
            empty = False
            yield json.dumps(update) + "\n"
            time.sleep(0.05)
        if empty:
            yield json.dumps({'phase': 'error', 'error': 'No output generated.'})+"\n"
    return Response(generate(), mimetype='application/json')

@app.route('/<filename>')
def download_csv(filename):
    # Security: only allow CSV files and prevent path traversal
    if not filename.endswith('.csv') or '/' in filename or '\\' in filename:
        return jsonify({'error': 'Invalid filename'}), 400
    
    root = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(root)
    path = os.path.join(parent, filename)
    
    if os.path.exists(path):
        return send_from_directory(parent, filename, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
