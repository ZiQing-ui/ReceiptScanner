// Fuel Receipt OCR Scanner - Batch Processing & Grand Total
document.addEventListener('DOMContentLoaded', () => {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const browseBtn = document.getElementById('browseBtn');
  const scanAllSamplesBtn = document.getElementById('scanAllSamplesBtn');

  const emptyState = document.getElementById('emptyState');
  const loaderCard = document.getElementById('loaderCard');
  const loaderText = document.getElementById('loaderText');
  const resultsSection = document.getElementById('resultsSection');

  const grandTotalValue = document.getElementById('grandTotalValue');
  const receiptsCount = document.getElementById('receiptsCount');
  const totalsFoundCount = document.getElementById('totalsFoundCount');
  const listCount = document.getElementById('listCount');
  const receiptsList = document.getElementById('receiptsList');
  const downloadAllJsonBtn = document.getElementById('downloadAllJsonBtn');
  const toast = document.getElementById('toast');

  let currentBatchData = null;

  browseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  dropzone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) uploadMultipleFiles(files);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) uploadMultipleFiles(fileInput.files);
  });

  if (scanAllSamplesBtn) {
    scanAllSamplesBtn.addEventListener('click', () => {
      setLoading(true, 'Scanning all sample receipts with OCR engine...');
      fetch('/api/scan-samples', { method: 'POST' })
        .then(res => {
          if (!res.ok) throw new Error('Failed to scan samples: ' + res.status);
          return res.json();
        })
        .then(data => renderBatchResults(data))
        .catch(err => {
          setLoading(false);
          alert('Error scanning samples: ' + err.message);
        });
    });
  }

  downloadAllJsonBtn.addEventListener('click', () => {
    if (!currentBatchData) return;
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(currentBatchData, null, 2));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', dataStr);
    dlAnchor.setAttribute('download', `fuel_receipts_batch_${Date.now()}.json`);
    document.body.appendChild(dlAnchor);
    dlAnchor.click();
    dlAnchor.remove();
  });

  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => { toast.classList.remove('show'); }, 2500);
  }

  function setLoading(isLoading, text) {
    if (isLoading) {
      emptyState.style.display = 'none';
      resultsSection.style.display = 'none';
      if (loaderText) loaderText.textContent = text || 'Processing receipts with OCR engine...';
      loaderCard.style.display = 'block';
    } else {
      loaderCard.style.display = 'none';
    }
  }

  function uploadMultipleFiles(fileList) {
    const formData = new FormData();
    const count = fileList.length;
    for (let i = 0; i < count; i++) {
      formData.append('files', fileList[i]);
    }

    setLoading(true, `Processing ${count} receipt image${count > 1 ? 's' : ''}...`);

    fetch('/api/scan', { method: 'POST', body: formData })
      .then(res => {
        if (!res.ok) throw new Error('Scan failed with status ' + res.status);
        return res.json();
      })
      .then(data => renderBatchResults(data))
      .catch(err => {
        setLoading(false);
        alert('Error scanning uploaded receipts: ' + err.message);
      });
  }

  function renderBatchResults(data) {
    currentBatchData = data;
    setLoading(false);

    // 1. Update Grand Total Banner
    const grand = data.grand_total || 0;
    grandTotalValue.textContent = Number(grand).toFixed(2);
    receiptsCount.textContent = data.receipt_count || 0;
    totalsFoundCount.textContent = `${data.totals_found_count || 0} / ${data.receipt_count || 0}`;
    listCount.textContent = data.receipt_count || 0;

    // 2. Render Individual Receipt Cards
    receiptsList.innerHTML = '';
    const receipts = data.receipts || [];

    receipts.forEach((r, idx) => {
      const card = document.createElement('div');
      card.className = 'receipt-card';

      let pillClass = 'pill-none';
      let confText = r.total_confidence || 'NOT FOUND';
      if (r.total_confidence === 'HIGH') pillClass = 'pill-high';
      else if (r.total_confidence === 'MEDIUM') pillClass = 'pill-medium';
      else if (r.total_confidence === 'LOW') pillClass = 'pill-low';

      const totalDisplay = (r.total_amount !== null && r.total_amount !== undefined)
        ? `$${Number(r.total_amount).toFixed(2)}`
        : '<span style="color:#f85149">Not Found</span>';

      const rawText = r.raw_text || '';
      const lineCount = rawText ? rawText.split('\n').length : 0;

      const previewHtml = r.annotated_image 
        ? `<img src="${r.annotated_image}" alt="Receipt ${idx + 1}">` 
        : '<div style="color:#8b949e;padding:40px;">No preview available</div>';

      const stateHtml = r.state
        ? `<div class="receipt-location"><span class="loc-icon">📍</span> State: <strong>${escapeHtml(r.state)}</strong></div>`
        : `<div class="receipt-location no-loc"><span class="loc-icon">📍</span> State: Not detected</div>`;

      card.innerHTML = `
        <div class="receipt-card-header">
          <div class="receipt-file-info">
            <span class="receipt-index">${idx + 1}</span>
            <div>
              <span class="receipt-filename">${escapeHtml(r.filename || 'receipt.png')}</span>
              ${stateHtml}
            </div>
          </div>
          <div class="receipt-total-badge-group">
            <span class="receipt-total-amount">${totalDisplay}</span>
            <span class="receipt-confidence-pill ${pillClass}">${confText}</span>
          </div>
        </div>
        <div class="receipt-body">
          <div class="receipt-preview-col">
            ${previewHtml}
          </div>
          <div class="receipt-raw-col">
            <div class="raw-col-header">
              <span class="raw-col-title">Raw OCR Output Text (${lineCount} lines)</span>
              <button type="button" class="btn-action copy-single-btn" data-index="${idx}">
                Copy Raw Text
              </button>
            </div>
            <pre class="raw-box">${escapeHtml(rawText || '(No text recognized)')}</pre>
          </div>
        </div>
      `;

      receiptsList.appendChild(card);
    });

    // Attach copy handlers
    document.querySelectorAll('.copy-single-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const index = parseInt(e.currentTarget.getAttribute('data-index'), 10);
        const receipt = receipts[index];
        if (receipt && receipt.raw_text) {
          navigator.clipboard.writeText(receipt.raw_text).then(() => {
            showToast('Raw OCR text copied to clipboard!');
          });
        }
      });
    });

    resultsSection.style.display = 'block';
  }

  function escapeHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
});

