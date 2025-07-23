document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('scrape-form');
    const statusDiv = document.getElementById('status');
    const resultsContainer = document.getElementById('results-container');
    const resultsTableBody = document.querySelector('#results-table tbody');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = document.querySelector('.btn-text');
    const spinner = document.querySelector('.spinner');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const copyBtn = document.getElementById('copy-btn');
    const tokenInput = document.getElementById('token');
    
    let currentResults = [];

    // Load token from local storage
    const savedToken = localStorage.getItem('github_token');
    if (savedToken) {
        tokenInput.value = savedToken;
    }

    tokenInput.addEventListener('input', () => {
        localStorage.setItem('github_token', tokenInput.value);
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        // Reset UI
        currentResults = [];
        statusDiv.textContent = '';
        submitBtn.disabled = true;
        btnText.textContent = 'Scraping...';
        spinner.style.display = 'inline-block';
        resultsContainer.style.display = 'none';
        resultsTableBody.innerHTML = '';
        progressContainer.style.display = 'block';
        progressBar.style.width = '0%';
        progressBar.style.backgroundColor = '#000';

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch('/scrape', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n').filter(line => line.trim() !== '');

                for (const line of lines) {
                    try {
                        const json = JSON.parse(line);
                        if (json.progress) {
                            progressBar.style.width = `${json.progress}%`;
                            statusDiv.textContent = `Scraping... (${Math.round(json.progress)}%)`;
                        }
                        if (json.results) {
                            currentResults = json.results;
                            displayResults(currentResults);
                            if (currentResults.length > 0) {
                                statusDiv.textContent = `Scraping complete. Found ${currentResults.length} unique emails.`;
                            } else {
                                statusDiv.textContent = 'Scraping complete. No new leads found.';
                            }
                        }
                        if (json.file_saved) {
                            statusDiv.textContent = json.file_saved;
                        }
                        if (json.error) {
                            throw new Error(json.error);
                        }
                    } catch (e) {
                        console.error("Error parsing chunk: ", line, e);
                    }
                }
            }

        } catch (error) {
            statusDiv.textContent = `An error occurred: ${error.message}`;
            progressBar.style.backgroundColor = '#dc3545';
        } finally {
            submitBtn.disabled = false;
            btnText.textContent = 'Scrape';
            spinner.style.display = 'none';
        }
    });

    function displayResults(results, sortKey = 'repo', sortOrder = 'asc') {
        resultsContainer.style.display = 'block';
        resultsTableBody.innerHTML = '';

        const sortedResults = [...results].sort((a, b) => {
            if (a[sortKey] < b[sortKey]) return sortOrder === 'asc' ? -1 : 1;
            if (a[sortKey] > b[sortKey]) return sortOrder === 'asc' ? 1 : -1;
            return 0;
        });

        sortedResults.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.name}</td>
                <td>${item.email}</td>
                <td>${item.repo}</td>
            `;
            resultsTableBody.appendChild(row);
        });
    }

    document.querySelectorAll('#results-table th').forEach(header => {
        header.addEventListener('click', () => {
            const sortKey = header.dataset.sort;
            const currentOrder = header.dataset.order || 'desc';
            const newOrder = currentOrder === 'asc' ? 'desc' : 'asc';
            
            document.querySelectorAll('#results-table th').forEach(th => {
                th.classList.remove('sort-asc', 'sort-desc');
                delete th.dataset.order;
            });

            header.dataset.order = newOrder;
            header.classList.add(newOrder === 'asc' ? 'sort-asc' : 'sort-desc');

            displayResults(currentResults, sortKey, newOrder);
        });
    });

    copyBtn.addEventListener('click', () => {
        if (currentResults.length > 0) {
            const csv = convertToCSV(currentResults);
            navigator.clipboard.writeText(csv).then(() => {
                copyBtn.textContent = 'Copied!';
                setTimeout(() => {
                    copyBtn.textContent = 'Copy as CSV';
                }, 2000);
            }, (err) => {
                console.error('Could not copy text: ', err);
            });
        }
    });

    function convertToCSV(data) {
        const headers = 'name,email,repo';
        const rows = data.map(row => `"${row.name}","${row.email}","${row.repo}"`);
        return [headers, ...rows].join('\n');
    }

    const tabs = document.querySelectorAll('.tab-link');
    const tabContents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = document.getElementById(tab.dataset.tab);

            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            tabContents.forEach(c => c.classList.remove('active'));
            target.classList.add('active');
        });
    });

    const extractForm = document.getElementById('extract-form');
    const extractBtn = document.getElementById('extract-btn');
    const csvFileInput = document.getElementById('csv-file');
    const extractedEmailsContainer = document.getElementById('extracted-emails-container');
    const extractedEmailsTextarea = document.getElementById('extracted-emails');
    const copyEmailsBtn = document.getElementById('copy-emails-btn');

    extractForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData();
        formData.append('csv_file', csvFileInput.files[0]);

        try {
            const response = await fetch('/extract', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                extractedEmailsTextarea.value = result.emails.join('\n');
                extractedEmailsContainer.style.display = 'block';
            } else {
                alert(`Error: ${result.message}`);
            }
        } catch (error) {
            alert(`An unexpected error occurred: ${error.message}`);
        }
    });

    copyEmailsBtn.addEventListener('click', () => {
        extractedEmailsTextarea.select();
        document.execCommand('copy');
        copyEmailsBtn.textContent = 'Copied!';
        setTimeout(() => {
            copyEmailsBtn.textContent = 'Copy Emails';
        }, 2000);
    });
});
