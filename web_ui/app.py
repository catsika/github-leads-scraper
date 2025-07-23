from flask import Flask, render_template, request, Response, jsonify
import sys
import os
import requests
from dotenv import load_dotenv
from argparse import Namespace
import json
import time
import csv
import re

load_dotenv()

# Add the parent directory to the Python path to import the scraper
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrap import run_scraper

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.get_json()
    query = data.get('query')
    max_repos = int(data.get('max_repos', 100))
    workers = int(data.get('workers', 10))
    output_file = data.get('output', 'github_licensing_leads.csv')
    token = data.get('token')

    args = Namespace(
        query=query,
        max_repos=max_repos,
        workers=workers,
        output=output_file,
        token=token
    )

    def generate(args):
        try:
            for progress_update in run_scraper(args):
                yield f"{json.dumps(progress_update)}\n"
                time.sleep(0.1)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                yield f'{json.dumps({"error": "GitHub API rate limit exceeded or token is invalid."})}\n'
            else:
                yield f'{json.dumps({"error": f"An HTTP error occurred: {e}"})}\n'
        except Exception as e:
            yield f'{json.dumps({"error": f"An unexpected error occurred: {e}"})}\n'

    return Response(generate(args), mimetype='application/json')

@app.route('/extract', methods=['POST'])
def extract():
    try:
        if 'csv_file' not in request.files:
            return jsonify({"success": False, "message": "No file part"})
        
        file = request.files['csv_file']
        
        if file.filename == '':
            return jsonify({"success": False, "message": "No selected file"})

        if file and file.filename.endswith('.csv'):
            emails = set()
            stream = file.stream.read().decode("utf-8")
            reader = csv.reader(stream.splitlines())
            header = next(reader)
            email_idx = header.index('email')

            for row in reader:
                email = row[email_idx]
                if not email.endswith(".local") and re.match(r"[^@]+@[^@]+\.[^@]+", email):
                    cleaned_email = re.sub(r'[<>]', '', email)
                    emails.add(cleaned_email)
            
            return jsonify({"success": True, "emails": list(emails)})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
