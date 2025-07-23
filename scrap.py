import requests
import csv
import os
from argparse import ArgumentParser
import logging
from time import sleep
import concurrent.futures
from dotenv import load_dotenv
import re

load_dotenv()

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- GitHub API Communication ---
def get_github_token(token_arg=None):
    """Retrieves the GitHub token from arguments, environment variables, or a hardcoded value."""
    if token_arg:
        return token_arg
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logging.error("GitHub token not found. Please provide it via the --token argument or set the GITHUB_TOKEN environment variable.")
    return token

def search_repositories(query, max_repos, headers):
    """Searches GitHub for repositories matching the query."""
    repos = []
    page = 1
    logging.info(f"Searching for up to {max_repos} repositories matching query: '{query}'")
    while len(repos) < max_repos:
        url = f"https://api.github.com/search/repositories?q={query}&per_page=100&page={page}"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"GitHub API error during search: {e}")
            break

        data = response.json()
        items = data.get("items", [])
        if not items:
            logging.info("No more repositories found.")
            break
        
        repos.extend(items)
        logging.info(f"Found {len(repos)} repositories so far...")
        
        if "next" not in response.links:
            break
        page += 1
        sleep(1)
        
    logging.info(f"Total repositories found: {len(repos)}")
    return repos[:max_repos]

def extract_emails_from_repo(repo, headers):
    """Extracts unique author emails from a repository's commits."""
    full_repo_name = repo["full_name"]
    emails = set()
    page = 1
    
    while True:
        url = f"https://api.github.com/repos/{full_repo_name}/commits?per_page=100&page={page}"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            break

        commits = response.json()
        if not commits:
            break

        for commit in commits:
            try:
                author = commit["commit"]["author"]
                email = author.get("email")
                name = author.get("name")
                if email and "noreply" not in email and not email.endswith(".users.noreply.github.com") and not email.endswith(".local") and re.match(r"[^@]+@[^@]+\.[^@]+", email):
                    emails.add((name, email))
            except (TypeError, KeyError):
                continue
        
        if "next" not in response.links:
            break
        page += 1
        sleep(0.5)

    return [{"name": name, "email": email, "repo": full_repo_name} for name, email in emails]

def run_scraper(args):
    """Main function to run the scraper."""
    token = get_github_token(args.token)
    if not token:
        yield {"error": "GitHub token is not provided."}
        return

    headers = {"Authorization": f"token {token}"}
    repos = search_repositories(args.query, args.max_repos, headers)
    all_emails = set()
    
    processed_repos = 0
    total_repos = len(repos)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_repo = {executor.submit(extract_emails_from_repo, repo, headers): repo for repo in repos}
        
        for future in concurrent.futures.as_completed(future_to_repo):
            repo_name = future_to_repo[future]['full_name']
            try:
                repo_emails = future.result()
                for email_info in repo_emails:
                    email_tuple = (email_info['name'], email_info['email'], email_info['repo'])
                    all_emails.add(email_tuple)
            except Exception as exc:
                logging.error(f'{repo_name} generated an exception: {exc}')
            finally:
                processed_repos += 1
                progress = (processed_repos / total_repos) * 100 if total_repos > 0 else 0
                yield {"progress": progress}

    results = []
    if all_emails:
        sorted_emails = sorted(list(all_emails), key=lambda x: x[2])
        
        with open(args.output, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["name", "email", "repo"])
            writer.writeheader()
            
            batch_size = 100
            for i in range(0, len(sorted_emails), batch_size):
                batch = sorted_emails[i:i+batch_size]
                for name, email, repo in batch:
                    results.append({"name": name, "email": email, "repo": repo})
                writer.writerows([{"name": name, "email": email, "repo": repo} for name, email, repo in batch])
        
        yield {"file_saved": f"Successfully wrote leads to {args.output}"}
    else:
        logging.info("No new leads found.")
        
    yield {"results": results}

if __name__ == "__main__":
    parser = ArgumentParser(description="Scrape GitHub for email addresses from repository commits.")
    parser.add_argument("-q", "--query", default="software license key OR license server",
                        help="The search query to find repositories.")
    parser.add_argument("-m", "--max-repos", type=int, default=100,
                        help="The maximum number of repositories to scrape.")
    parser.add_argument("-w", "--workers", type=int, default=10,
                        help="Number of concurrent threads to use.")
    parser.add_argument("-o", "--output", default="github_licensing_leads.csv",
                        help="The output CSV file name.")
    parser.add_argument("-t", "--token", help="GitHub API token. Overrides GITHUB_TOKEN environment variable.")
    
    args = parser.parse_args()
    for _ in run_scraper(args):
        pass
