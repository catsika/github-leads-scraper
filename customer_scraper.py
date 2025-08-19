import os
import csv
import time
import requests
import re
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Generator, Optional
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

GITHUB_API = "https://api.github.com"

@dataclass
class Lead:
    email: str
    github_username: str
    name: str = ''
    repository: str = ''
    repo_description: str = ''
    repo_stars: int = 0
    repo_language: str = ''
    company: str = ''
    bio: str = ''

    def to_row(self) -> Dict:
        return {
            'email': self.email,
            'github_username': self.github_username,
            'name': self.name,
            'repository': self.repository,
            'repo_description': self.repo_description,
            'repo_stars': self.repo_stars,
            'repo_language': self.repo_language,
            'company': self.company,
            'bio': self.bio
        }

class CustomerScraper:
    def __init__(self, token: Optional[str] = None, output_filename: str = 'leads.csv'):
        # Only use environment token if no token parameter is explicitly provided
        if token is None:
            self.token = os.getenv('GITHUB_TOKEN')
        else:
            self.token = token
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({'Authorization': f'Bearer {self.token}'})
        self.session.headers.update({'Accept': 'application/vnd.github+json'})
        self.leads: Dict[str, Lead] = {}
        self.last_error: Optional[str] = None
        self.output_filename = output_filename
        self.lock = threading.Lock()

    # --------------- GitHub API Helpers ----------------
    def search_repositories(self, query: str, per_page: int = 30) -> List[Dict]:
        url = f"{GITHUB_API}/search/repositories"
        params = {'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': per_page}
        try:
            r = self.session.get(url, params=params, timeout=30)
            if r.status_code == 401:
                self.last_error = 'Unauthorized (bad or missing token)'
                # If we have a token and it failed, try without authentication
                if self.token:
                    print("Warning: Token authentication failed, trying without token...")
                    session_no_auth = requests.Session()
                    session_no_auth.headers.update({'Accept': 'application/vnd.github+json'})
                    r = session_no_auth.get(url, params=params, timeout=30)
                    if r.status_code == 200:
                        self.last_error = None
                        return r.json().get('items', [])
                return []
            if r.status_code == 403:
                remaining = r.headers.get('X-RateLimit-Remaining')
                if remaining == '0':
                    self.last_error = 'Rate limited (403). Wait before retry.'
                else:
                    self.last_error = 'Forbidden (403). Possibly missing scopes or abuse detection).'
                return []
            if r.status_code >= 400:
                try:
                    msg = r.json().get('message')
                except Exception:
                    msg = r.text[:120]
                self.last_error = f"HTTP {r.status_code}: {msg}"
                return []
            self.last_error = None
            return r.json().get('items', [])
        except requests.RequestException as e:
            self.last_error = f"Request error: {e.__class__.__name__}"
            return []

    def get_user(self, username: str) -> Dict:
        try:
            r = self.session.get(f"{GITHUB_API}/users/{username}", timeout=20)
            if r.status_code == 401 and self.token:
                # Try without authentication if token fails
                session_no_auth = requests.Session()
                session_no_auth.headers.update({'Accept': 'application/vnd.github+json'})
                r = session_no_auth.get(f"{GITHUB_API}/users/{username}", timeout=20)
            if r.status_code == 404:
                return {}
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            return {}

    def get_commits_emails(self, full_name: str, max_pages: int = 1) -> List[Dict]:
        emails = {}
        for page in range(1, max_pages+1):
            try:
                r = self.session.get(f"{GITHUB_API}/repos/{full_name}/commits", params={'per_page': 100, 'page': page}, timeout=30)
                if r.status_code == 401 and self.token:
                    # Try without authentication if token fails
                    session_no_auth = requests.Session()
                    session_no_auth.headers.update({'Accept': 'application/vnd.github+json'})
                    r = session_no_auth.get(f"{GITHUB_API}/repos/{full_name}/commits", params={'per_page': 100, 'page': page}, timeout=30)
                if r.status_code >= 400:
                    break
                commits = r.json()
                if not commits:
                    break
                for c in commits:
                    commit = c.get('commit', {}).get('author', {})
                    email = commit.get('email')
                    name = commit.get('name', '')
                    if email and self._valid_email(email) and not self._generic_email(email):
                        emails[email.lower()] = name
                if 'next' not in r.links:
                    break
            except requests.RequestException:
                break
        return [{'email': e, 'name': n} for e, n in emails.items()]

    # --------------- Main Stream Scrape ---------------
    def _process_repo(self, repo) -> List[Dict]:
        events = []
        full_name = repo.get('full_name')
        owner_login = repo.get('owner', {}).get('login')
        user = self.get_user(owner_login) if owner_login else {}
        emails_found = self.get_commits_emails(full_name, max_pages=1)
        primary_email = None
        for em in emails_found:
            primary_email = em
            break
        if not primary_email and user.get('email') and self._valid_email(user['email']) and not self._generic_email(user['email']):
            primary_email = {'email': user['email'], 'name': user.get('name') or ''}
        if primary_email:
            email_lower = primary_email['email'].lower()
            with self.lock:
                if email_lower not in self.leads:
                    lead = Lead(
                        email=email_lower,
                        github_username=owner_login or '',
                        name=primary_email.get('name') or (user.get('name') or ''),
                        repository=full_name or '',
                        repo_description=repo.get('description') or '',
                        repo_stars=repo.get('stargazers_count', 0),
                        repo_language=repo.get('language') or '',
                        company=user.get('company') or '',
                        bio=user.get('bio') or ''
                    )
                    self.leads[email_lower] = lead
                    events.append({
                        'phase': 'lead_added',
                        'email': email_lower,
                        'repository': full_name,
                        'name': lead.name,
                        'repo_stars': lead.repo_stars,
                        'repo_language': lead.repo_language,
                        'company': lead.company,
                        'repo_description': lead.repo_description,
                        'github_username': lead.github_username,
                        'reasons': []
                    })
        else:
            events.append({
                'phase': 'no_email',
                'repository': full_name,
                'reason': 'No commit or public email found'
            })
        return events

    def stream_scrape(self, max_repos_per_query: int = 30, queries: Optional[List[str]] = None, concurrency: int = 5) -> Generator[Dict, None, None]:
        if not queries:
            yield {'phase': 'error', 'error': 'No queries supplied. Provide queries.'}
            return
        total_queries = len(queries)
        yield {'phase': 'queries_received', 'queries': queries, 'total_queries': total_queries}
        for idx, query in enumerate(queries, start=1):
            yield {'phase': 'query_start', 'current_query': query, 'query_index': idx, 'total_queries': total_queries}
            repos = self.search_repositories(query, per_page=max_repos_per_query)
            if not repos:
                yield {
                    'phase': 'query_empty',
                    'current_query': query,
                    'query_index': idx,
                    'reason': self.last_error or 'No repositories returned'
                }
                time.sleep(0.05)
                continue
            repos = repos[:max_repos_per_query]
            repos_in_query = len(repos)
            processed = 0
            with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
                future_map = {executor.submit(self._process_repo, repo): repo for repo in repos}
                for fut in as_completed(future_map):
                    try:
                        events = fut.result()
                        for ev in events:
                            yield ev
                    except Exception as e:
                        yield {'phase': 'error', 'error': f'Repo task failed: {e.__class__.__name__}'}
                    processed += 1
                    yield {
                        'phase': 'progress',
                        'current_query': query,
                        'query_index': idx,
                        'total_queries': total_queries,
                        'repos_processed_in_query': processed,
                        'repos_in_query': repos_in_query,
                        'leads_total': len(self.leads)
                    }
            time.sleep(0.05)
        self._persist_leads()
        yield {'phase': 'finished', 'leads_total': len(self.leads), 'file': self.output_filename}

    # --------------- Persistence ---------------
    def _persist_leads(self):
        if not self.leads:
            return
        root = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.join(root, self.output_filename)
        headers = ['email','github_username','name','repository','repo_description','repo_stars','repo_language','company','bio']
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for lead in self.leads.values():
                writer.writerow(lead.to_row())

    # --------------- Helpers ---------------
    def _valid_email(self, email: str) -> bool:
        if not email or 'noreply' in email or email.endswith('.local'):
            return False
        return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

    def _generic_email(self, email: str) -> bool:
        prefix = email.split('@')[0]
        return prefix in {'support','info','contact','sales'}

# Convenience function for route

def stream_customer_scrape(params: Dict) -> Generator[Dict, None, None]:
    output_filename = params.get('output_filename', 'leads.csv')
    scraper = CustomerScraper(token=params.get('token'), output_filename=output_filename)
    max_repos_per_query = int(params.get('max_repos_per_query', 30))
    concurrency = int(params.get('concurrency', 5))

    raw_queries: List[str] = []
    if 'queries' in params and isinstance(params['queries'], list):
        raw_queries.extend([q for q in params['queries'] if q])
    if 'queries_raw' in params and isinstance(params['queries_raw'], str):
        for piece in re.split(r'[\n;]+', params['queries_raw']):
            piece = piece.strip()
            if piece:
                raw_queries.append(piece)
    seen = set(); final_queries = []
    for q in raw_queries:
        if q not in seen:
            seen.add(q); final_queries.append(q)

    for update in scraper.stream_scrape(max_repos_per_query=max_repos_per_query, queries=final_queries, concurrency=concurrency):
        yield update
