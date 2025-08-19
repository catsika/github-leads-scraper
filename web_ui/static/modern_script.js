// Modern GitHub Lead Scraper JavaScript

class LeadScraper {
    constructor() {
        this.isRunning = false;
        this.leads = [];
        this.startTime = null;
        this.currentFilename = 'leads.csv';
        
        this.initializeElements();
        this.bindEvents();
    }

    initializeElements() {
        this.form = document.getElementById('scrapeForm');
        this.queriesInput = document.getElementById('queries');
        this.tokenInput = document.getElementById('token');
        this.maxReposInput = document.getElementById('maxRepos');
        this.outputFilenameInput = document.getElementById('outputFilename');
        this.startBtn = document.getElementById('startBtn');
        this.clearBtn = document.getElementById('clearBtn');
        this.downloadBtn = document.getElementById('downloadBtn');
        this.startLabel = document.getElementById('startLabel');
        this.loadingSpinner = document.getElementById('loadingSpinner');
        this.errorBanner = document.getElementById('errorBanner');
        this.errorMessage = document.getElementById('errorMessage');
        this.totalLeads = document.getElementById('totalLeads');
        this.currentQuery = document.getElementById('currentQuery');
        this.progressPercent = document.getElementById('progressPercent');
        this.progressContainer = document.getElementById('progressContainer');
        this.progressFill = document.getElementById('progressFill');
        this.progressText = document.getElementById('progressText');
        this.resultsTable = document.getElementById('resultsTable');
        this.resultsBody = document.getElementById('resultsBody');
        this.sampleSelect = document.getElementById('sampleSelect');
        this.insertSamplesBtn = document.getElementById('insertSamples');
    }

    bindEvents() {
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        this.clearBtn.addEventListener('click', () => this.clearResults());
        this.downloadBtn.addEventListener('click', () => this.downloadCsv());
        ['queries','maxRepos','outputFilename'].forEach(id => {
            const el = document.getElementById(id === 'queries' ? 'queries' : id);
            el.addEventListener('input', () => this.persistState());
        });
        if (this.insertSamplesBtn) {
            this.insertSamplesBtn.addEventListener('click', () => this.insertSamples());
        }
        this.restoreState();
    }

    async handleSubmit(e) {
        e.preventDefault();
        
        if (this.isRunning) {
            this.stopScraping();
            return;
        }

        const queries = this.queriesInput.value.trim();
        if (!queries) {
            this.showError('Please enter at least one search query');
            return;
        }

        this.startScraping();
    }

    async startScraping() {
        this.isRunning = true;
        this.startTime = Date.now();
        this.leads = [];
        this.currentFilename = this.outputFilenameInput.value.trim() || 'leads.csv';
        
        // Update UI
        this.startBtn.classList.add('loading');
        this.startLabel.textContent = 'Stop Scraping';
        this.startBtn.classList.remove('btn-primary');
        this.startBtn.classList.add('btn-secondary');
        this.hideError();
        this.showProgress();
        this.clearTable();

        const params = {
            queries_raw: this.queriesInput.value.trim(),
            token: this.tokenInput.value.trim(),
            max_repos_per_query: parseInt(this.maxReposInput.value) || 30,
            output_filename: this.currentFilename
        };

        try {
            const response = await fetch('/scrape/customers', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(params)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (this.isRunning) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n').filter(line => line.trim());

                for (const line of lines) {
                    try {
                        const update = JSON.parse(line);
                        this.handleUpdate(update);
                    } catch (e) {
                        console.warn('Failed to parse update:', line);
                    }
                }
            }
        } catch (error) {
            this.showError(`Scraping failed: ${error.message}`);
        } finally {
            this.stopScraping();
        }
    }

    stopScraping() {
        this.isRunning = false;
        this.startBtn.classList.remove('loading');
        this.startLabel.textContent = 'Start';
        this.startBtn.classList.add('primary');
        this.hideProgress();
        if (this.leads.length > 0) {
            this.clearBtn.disabled = false;
            this.downloadBtn.disabled = false;
        }
    }

    persistState() {
        try {
            const state = {
                queries: this.queriesInput.value,
                maxRepos: this.maxReposInput.value,
                outputFilename: this.outputFilenameInput.value
            };
            localStorage.setItem('leadScraperState', JSON.stringify(state));
        } catch (_) {}
    }

    restoreState() {
        try {
            const raw = localStorage.getItem('leadScraperState');
            if (!raw) return;
            const state = JSON.parse(raw);
            if (state.queries) this.queriesInput.value = state.queries;
            if (state.maxRepos) this.maxReposInput.value = state.maxRepos;
            if (state.outputFilename) this.outputFilenameInput.value = state.outputFilename;
        } catch (_) {}
    }

    handleUpdate(update) {
        const { phase } = update;
        switch (phase) {
            case 'queries_received':
                this.updateStats(0, `0/${update.total_queries}`, '0%');
                this.updateProgress(0, `0/${update.total_queries} queries`);
                break;
            case 'query_start':
                this.updateStats(this.leads.length, `${update.query_index}/${update.total_queries}`, '0%');
                this.updateProgress(0, `Q${update.query_index}`);
                break;
            case 'lead_added':
                this.addLead(update);
                break;
            case 'progress':
                const percent = Math.round((update.repos_processed_in_query / update.repos_in_query) * 100);
                this.updateStats(update.leads_total, `${update.query_index}/${update.total_queries}`, `${percent}%`);
                this.updateProgress(percent, `${update.repos_processed_in_query}/${update.repos_in_query}`);
                break;
            case 'finished':
                this.updateProgress(100, `Done (${update.leads_total})`);
                this.currentFilename = update.file;
                break;
            case 'error':
                this.showError(update.error);
                break;
        }
    }

    addLead(leadData) {
        const lead = {
            email: leadData.email,
            name: leadData.name || leadData.github_username || '',
            repository: leadData.repository || ''
        };
        this.leads.push(lead);
        const empty = this.resultsBody.querySelector('.empty-state');
        if (empty) empty.remove();
        const row = document.createElement('tr');
        row.innerHTML = `<td>${this.escapeHtml(lead.email)}</td><td>${this.escapeHtml(lead.name)}</td><td>${this.escapeHtml(lead.repository)}</td>`;
        this.resultsBody.appendChild(row);
        this.updateStats(this.leads.length, null, null);
    }

    showProgress() {
        this.progressContainer.style.display = 'block';
    }

    hideProgress() {
        this.progressContainer.style.display = 'none';
    }

    updateProgress(percent, text) {
        this.progressFill.style.width = `${percent}%`;
        this.progressText.textContent = text;
    }

    showError(message) {
        this.errorMessage.textContent = message;
        this.errorBanner.style.display = 'flex';
    }

    hideError() {
        this.errorBanner.style.display = 'none';
    }

    clearResults() {
        this.leads = [];
        this.clearTable();
        this.updateStats(0, '0/0', '0%');
        this.hideProgress();
        
        // Disable action buttons
        this.clearBtn.disabled = true;
        this.downloadBtn.disabled = true;
    }

    downloadCsv() {
        window.location.href = `/${this.currentFilename}`;
    }

    clearTable() {
        this.resultsBody.innerHTML = `
            <tr class="empty-state">
                <td colspan="3">
                    <div class="empty-state-content">
                        <i class="fas fa-search"></i>
                        <p>No leads found yet</p>
                        <small>Start scraping to see results here</small>
                    </div>
                </td>
            </tr>
        `;
    }

    updateStats(leads, queries, progress) {
        if (leads !== null) this.totalLeads.textContent = leads;
        if (queries !== null) this.currentQuery.textContent = queries;
        if (progress !== null) this.progressPercent.textContent = progress;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    insertSamples() {
        if (!this.sampleSelect) return;
        const val = this.sampleSelect.value;
        if (!val) return;
        const existing = this.queriesInput.value.trim();
        this.queriesInput.value = existing ? (existing + '\n' + val) : val;
        this.persistState();
    }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    new LeadScraper();
});
