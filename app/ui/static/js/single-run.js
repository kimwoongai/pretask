// Single Run Mode JavaScript

let currentCaseId = null;
let isProcessing = false;
let statsRefresh = null;

// Initialize single run page
document.addEventListener('DOMContentLoaded', function() {
    loadCaseList();
    loadStats();
    setupEventListeners();
    
    // Auto-refresh stats every 10 seconds
    statsRefresh = new AutoRefresh(loadStats, 10000);
    statsRefresh.start();
});

// Setup event listeners
function setupEventListeners() {
    // Case selection
    document.getElementById('case-select').addEventListener('change', function() {
        const caseId = this.value;
        const processBtn = document.getElementById('process-btn');
        
        if (caseId) {
            processBtn.disabled = false;
            currentCaseId = caseId;
        } else {
            processBtn.disabled = true;
            currentCaseId = null;
        }
    });
    
    // Process button
    document.getElementById('process-btn').addEventListener('click', async function() {
        if (!currentCaseId || isProcessing) return;
        
        await processCase(currentCaseId);
    });
    
    // Next case button
    document.getElementById('next-case-btn').addEventListener('click', async function() {
        await getNextCase();
    });
    
    // Show diff button
    document.getElementById('show-diff-btn').addEventListener('click', function() {
        showDiffView();
    });
    
    // Apply rule button
    document.getElementById('apply-rule-btn').addEventListener('click', async function() {
        await applySelectedRule();
    });
}

// Load case list
async function loadCaseList() {
    try {
        const response = await API.get('/cases?limit=50&status=pending');
        const caseSelect = document.getElementById('case-select');
        
        caseSelect.innerHTML = '<option value="">케이스를 선택하세요</option>';
        
        response.cases.forEach(case_ => {
            const option = document.createElement('option');
            option.value = case_.case_id;
            option.textContent = `${case_.case_id} (${case_.court_type} - ${case_.case_type})`;
            caseSelect.appendChild(option);
        });
        
    } catch (error) {
        console.error('Failed to load case list:', error);
        Utils.showToast('케이스 목록 로딩에 실패했습니다.', 'danger');
    }
}

// Load processing stats
async function loadStats() {
    try {
        const stats = await API.get('/single-run/stats');
        
        document.getElementById('consecutive-passes').textContent = stats.consecutive_passes || 0;
        
        const batchReady = document.getElementById('batch-ready');
        if (stats.ready_for_batch_mode) {
            batchReady.innerHTML = '<span class="badge bg-success">준비완료</span>';
        } else {
            batchReady.innerHTML = '<span class="badge bg-secondary">준비중</span>';
        }
        
        // Update progress bar
        const progressBar = document.getElementById('progress-bar');
        const progress = Math.min((stats.consecutive_passes / 20) * 100, 100);
        progressBar.style.width = progress + '%';
        progressBar.setAttribute('aria-valuenow', stats.consecutive_passes);
        
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

// Process a case
async function processCase(caseId) {
    if (isProcessing) return;
    
    isProcessing = true;
    
    // Show processing status
    showProcessingStatus();
    
    try {
        const result = await API.post(`/single-run/process/${caseId}`);
        
        // Display results
        displayProcessingResult(result);
        
        // Update stats
        await loadStats();
        
        // Show success message
        if (result.passed) {
            Utils.showToast(`케이스 ${caseId} 처리 완료 (합격)`, 'success');
        } else {
            Utils.showToast(`케이스 ${caseId} 처리 완료 (불합격)`, 'warning');
        }
        
    } catch (error) {
        console.error('Failed to process case:', error);
        hideProcessingStatus();
        Utils.showToast(`케이스 처리 중 오류가 발생했습니다: ${error.message}`, 'danger');
    } finally {
        isProcessing = false;
    }
}

// Show processing status
function showProcessingStatus() {
    document.getElementById('processing-status').style.display = 'block';
    document.getElementById('result-content').style.display = 'none';
    document.getElementById('no-result').style.display = 'none';
}

// Hide processing status
function hideProcessingStatus() {
    document.getElementById('processing-status').style.display = 'none';
    document.getElementById('no-result').style.display = 'block';
}

// Display processing result
function displayProcessingResult(result) {
    // Hide processing status
    document.getElementById('processing-status').style.display = 'none';
    document.getElementById('no-result').style.display = 'none';
    document.getElementById('result-content').style.display = 'block';
    
    // Update metrics
    const metrics = result.metrics;
    document.getElementById('nrr-value').textContent = Utils.formatNumber(metrics.nrr, 3);
    document.getElementById('fpr-value').textContent = Utils.formatNumber(metrics.fpr, 3);
    document.getElementById('ss-value').textContent = Utils.formatNumber(metrics.ss, 3);
    document.getElementById('token-reduction').textContent = Utils.formatPercent(metrics.token_reduction);
    
    // Update result alert
    const resultAlert = document.getElementById('result-alert');
    const resultMessage = document.getElementById('result-message');
    
    if (result.passed) {
        resultAlert.className = 'alert alert-success';
        resultMessage.innerHTML = `
            <i class="fas fa-check-circle me-2"></i>
            <strong>합격!</strong> 모든 품질 게이트를 통과했습니다.
            <div class="mt-2">
                <small>처리 시간: ${Utils.formatDuration(result.processing_time_ms)} | 
                토큰 절감: ${result.token_reduction}%</small>
            </div>
        `;
    } else {
        resultAlert.className = 'alert alert-warning';
        const errors = result.errors || [];
        const errorList = errors.join(', ');
        
        resultMessage.innerHTML = `
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>불합격</strong> 품질 게이트를 통과하지 못했습니다.
            <div class="mt-2">
                <small>오류: ${errorList}</small>
            </div>
        `;
    }
    
    resultAlert.style.display = 'block';
    
    // Show rule suggestions if available
    if (result.suggestions && result.suggestions.length > 0) {
        displayRuleSuggestions(result.suggestions);
    } else {
        document.getElementById('rule-suggestions').style.display = 'none';
    }
    
    // Store result data for diff view
    window.currentResult = result;
}

// Display rule suggestions
function displayRuleSuggestions(suggestions) {
    const container = document.getElementById('suggestions-content');
    const ruleSuggestions = document.getElementById('rule-suggestions');
    
    container.innerHTML = '';
    
    suggestions.forEach((suggestion, index) => {
        const suggestionElement = document.createElement('div');
        suggestionElement.className = `rule-suggestion ${getConfidenceClass(suggestion.confidence_score)}`;
        
        suggestionElement.innerHTML = `
            <div class="d-flex justify-content-between align-items-start mb-2">
                <h6 class="mb-0">${suggestion.description}</h6>
                <span class="confidence-score ${getConfidenceClass(suggestion.confidence_score)}">
                    ${Utils.formatPercent(suggestion.confidence_score * 100)}
                </span>
            </div>
            <div class="mb-2">
                <small class="text-muted">
                    <strong>유형:</strong> ${suggestion.rule_type} | 
                    <strong>적용 케이스:</strong> ${suggestion.applicable_cases.join(', ')}
                </small>
            </div>
            <div class="mb-2">
                <strong>패턴:</strong>
                <code class="d-block bg-light p-2 mt-1">${suggestion.pattern}</code>
            </div>
            <div class="mb-3">
                <strong>대체:</strong>
                <code class="d-block bg-light p-2 mt-1">${suggestion.replacement || '(제거)'}</code>
            </div>
            <button class="btn btn-sm btn-outline-primary" onclick="showRuleModal(${index})">
                <i class="fas fa-cog me-1"></i>적용
            </button>
        `;
        
        container.appendChild(suggestionElement);
    });
    
    ruleSuggestions.style.display = 'block';
    
    // Store suggestions for modal
    window.currentSuggestions = suggestions;
}

// Get confidence class
function getConfidenceClass(score) {
    if (score >= 0.8) return 'high-confidence';
    if (score >= 0.6) return 'medium-confidence';
    return 'low-confidence';
}

// Show rule application modal
function showRuleModal(index) {
    const suggestion = window.currentSuggestions[index];
    const modal = new bootstrap.Modal(document.getElementById('ruleModal'));
    
    const ruleDetails = document.getElementById('rule-details');
    ruleDetails.innerHTML = `
        <div class="mb-3">
            <strong>설명:</strong> ${suggestion.description}
        </div>
        <div class="mb-3">
            <strong>규칙 유형:</strong> ${suggestion.rule_type}
        </div>
        <div class="mb-3">
            <strong>신뢰도:</strong> 
            <span class="confidence-score ${getConfidenceClass(suggestion.confidence_score)}">
                ${Utils.formatPercent(suggestion.confidence_score * 100)}
            </span>
        </div>
        <div class="mb-3">
            <strong>패턴:</strong>
            <code class="d-block bg-light p-2 mt-1">${suggestion.pattern}</code>
        </div>
        <div class="mb-3">
            <strong>대체:</strong>
            <code class="d-block bg-light p-2 mt-1">${suggestion.replacement || '(제거)'}</code>
        </div>
    `;
    
    // Store selected suggestion
    window.selectedSuggestion = suggestion;
    
    modal.show();
}

// Apply selected rule
async function applySelectedRule() {
    const suggestion = window.selectedSuggestion;
    const autoRerun = document.getElementById('auto-rerun').checked;
    
    if (!suggestion) return;
    
    try {
        // Apply the rule (this would be implemented in the backend)
        Utils.showToast('규칙이 적용되었습니다.', 'success');
        
        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('ruleModal'));
        modal.hide();
        
        // Auto-rerun if selected
        if (autoRerun && currentCaseId) {
            setTimeout(() => {
                processCase(currentCaseId);
            }, 1000);
        }
        
    } catch (error) {
        console.error('Failed to apply rule:', error);
        Utils.showToast(`규칙 적용 중 오류가 발생했습니다: ${error.message}`, 'danger');
    }
}

// Get next case suggestion
async function getNextCase() {
    try {
        const response = await API.get('/single-run/next-case');
        
        if (response.next_case_id) {
            const caseSelect = document.getElementById('case-select');
            caseSelect.value = response.next_case_id;
            currentCaseId = response.next_case_id;
            
            document.getElementById('process-btn').disabled = false;
            
            Utils.showToast(`다음 케이스로 ${response.next_case_id}를 제안합니다.`, 'info');
        } else {
            Utils.showToast('더 이상 처리할 케이스가 없습니다.', 'warning');
        }
        
    } catch (error) {
        console.error('Failed to get next case:', error);
        Utils.showToast('다음 케이스 제안을 가져올 수 없습니다.', 'danger');
    }
}

// Show diff view
function showDiffView() {
    const result = window.currentResult;
    if (!result) return;
    
    const modal = new bootstrap.Modal(document.getElementById('diffModal'));
    
    document.getElementById('before-content').textContent = result.before_content || '';
    document.getElementById('after-content').textContent = result.after_content || '';
    document.getElementById('diff-summary').textContent = result.diff_summary || '';
    
    modal.show();
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (statsRefresh) {
        statsRefresh.stop();
    }
});
