import { state } from '../state.js';
import * as api from '../api.js';
import { showToast } from '../toast.js';
import { refreshGallery } from './gallery.js';

let batchPollingInterval = null;

export function initBatch() {
  const btnStartBatch = document.getElementById('btn-start-batch-jobs');
  if (btnStartBatch) {
    btnStartBatch.addEventListener('click', async () => {
      const numShorts = parseInt(document.getElementById('batch-num-input').value) || 5;
      try {
        const res = await api.startBatch(numShorts);
        showToast(res.message, 'success');
        document.getElementById('batch-progress-section')?.classList.remove('hidden');
        startBatchPolling();
      } catch (err) {
        showToast(`Failed to start batch: ${err.message}`, 'error');
      }
    });
  }

  const btnCancelRunningBatch = document.getElementById('btn-cancel-running-batch');
  if (btnCancelRunningBatch) {
    btnCancelRunningBatch.addEventListener('click', async () => {
      try {
        const res = await api.cancelBatch();
        showToast(res.message, 'info');
        document.getElementById('batch-status-indicator').innerText = 'Cancelling...';
      } catch (err) {
        showToast(`Cancel failed: ${err.message}`, 'error');
      }
    });
  }
}

export async function checkActiveBatch() {
  try {
    const data = await api.getBatchStatus();
    if (data.in_progress) {
      document.getElementById('batch-progress-section')?.classList.remove('hidden');
      updateBatchUI(data);
      startBatchPolling();
    }
  } catch (err) {
    // Ignore error on startup check
  }
}

function startBatchPolling() {
  if (batchPollingInterval) clearInterval(batchPollingInterval);
  pollBatchStatus();
  batchPollingInterval = setInterval(pollBatchStatus, 1000);
}

async function pollBatchStatus() {
  try {
    const data = await api.getBatchStatus();
    updateBatchUI(data);

    if (!data.in_progress) {
      clearInterval(batchPollingInterval);
      batchPollingInterval = null;
      document.getElementById('batch-status-indicator').innerText = 'Batch generation complete.';
      document.getElementById('btn-cancel-running-batch').style.display = 'none';
      refreshGallery(); // Refresh gallery with new videos
    } else {
      document.getElementById('batch-status-indicator').innerText = 'Running...';
      document.getElementById('btn-cancel-running-batch').style.display = 'block';
    }
  } catch (err) {
    console.error('Batch polling error:', err);
  }
}

function updateBatchUI(data) {
  let doneCount = 0;
  let runningCount = 0;
  let failedCount = 0;
  let queuedCount = 0;

  const grid = document.getElementById('batch-jobs-grid');
  if (!grid) return;

  grid.innerHTML = '';

  data.jobs.forEach(job => {
    if (job.status === 'Done') doneCount++;
    else if (job.failed || job.status.startsWith('Failed')) failedCount++;
    else if (job.status === 'Queued') queuedCount++;
    else runningCount++;

    const card = document.createElement('div');
    card.className = 'batch-job-card';
    
    let statusHTML = '';
    if (job.status === 'Done') {
      statusHTML = `<span style="color: #10B981; font-weight: 500;">✓ Done</span>`;
    } else if (job.failed || job.status.startsWith('Failed')) {
      statusHTML = `<span style="color: #EF4444; font-weight: 500;">✗ ${job.status}</span>`;
    } else if (job.status === 'Queued') {
      statusHTML = `<span style="color: var(--text-muted);">Queued...</span>`;
    } else {
      const p = job.progress || 0;
      statusHTML = `
        <div class="batch-progress-wrapper">
          <div class="batch-progress-bar-bg">
            <div class="batch-progress-bar-fill pulsing" style="width: ${p}%;"></div>
          </div>
          <span class="batch-progress-percent">${p}%</span>
        </div>
        <div class="batch-job-status-text">${job.status}</div>
      `;
    }

    card.innerHTML = `
      <div class="batch-job-header">
        <span class="batch-job-id">Job #${job.id}</span>
        <span class="batch-job-elapsed">${job.elapsed}</span>
      </div>
      <div class="batch-job-topic" title="${job.topic}">${job.topic}</div>
      <div class="batch-job-details">${job.voice} &bull; ${job.layout}</div>
      <div class="batch-job-status-container">
        ${statusHTML}
      </div>
    `;
    grid.appendChild(card);
  });

  const summary = document.getElementById('batch-summary');
  if (summary) {
    summary.innerHTML = `Progress: <span style="color: #10B981;">${doneCount} Done</span> | <span style="color: var(--accent);">${runningCount} Running</span> | <span style="color: #EF4444;">${failedCount} Failed</span> | <span style="color: var(--text-muted);">${queuedCount} Queued</span> (Total: ${data.num_shorts})`;
  }
}
