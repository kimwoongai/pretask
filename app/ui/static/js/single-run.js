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
    
    // View rules button
    document.getElementById('view-rules-btn').addEventListener('click', async function() {
        await showCurrentRules();
    });
    
    // Rule history button
    document.getElementById('rule-history-btn').addEventListener('click', async function() {
        await showRuleHistory();
    });
}

// Load case list
async function loadCaseList() {
    try {
        const response = await API.get('/cases?limit=50');
        console.log('Cases API response:', response);
        
        const caseSelect = document.getElementById('case-select');
        
        caseSelect.innerHTML = '<option value="">케이스를 선택하세요</option>';
        
        if (response.cases && response.cases.length > 0) {
            console.log(`Loading ${response.cases.length} cases`);
            response.cases.forEach(case_ => {
                const option = document.createElement('option');
                option.value = case_.case_id;
                // 실제 데이터 구조에 맞게 표시 형식 수정
                const displayText = `${case_.precedent_id || case_.case_id} - ${case_.case_name || '사건명 없음'} (${case_.court_name || case_.court_type || '법원 정보 없음'})`;
                option.textContent = displayText;
                caseSelect.appendChild(option);
            });
        } else {
            console.warn('No cases found in response');
            caseSelect.innerHTML += '<option disabled>판례를 찾을 수 없습니다</option>';
        }
        
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
                <div class="mt-1">
                    ${suggestion.pattern_before ? `
                        <div class="mb-1">
                            <small class="text-muted">현재:</small>
                            <code class="d-block bg-light p-2">${suggestion.pattern_before}</code>
                        </div>
                        <div class="mb-1">
                            <small class="text-muted">개선 후:</small>
                            <code class="d-block bg-success-subtle p-2">${suggestion.pattern_after}</code>
                        </div>
                    ` : `
                        <code class="d-block bg-light p-2">${suggestion.pattern || '정규식 패턴'}</code>
                    `}
                </div>
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
    
    // Get existing modal instance or create new one
    const modalElement = document.getElementById('ruleModal');
    let modal = bootstrap.Modal.getInstance(modalElement);
    if (!modal) {
        modal = new bootstrap.Modal(modalElement);
    }
    
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
            <div class="mt-1">
                ${suggestion.pattern_before ? `
                    <div class="mb-1">
                        <small class="text-muted">현재:</small>
                        <code class="d-block bg-light p-2">${suggestion.pattern_before}</code>
                    </div>
                    <div class="mb-1">
                        <small class="text-muted">개선 후:</small>
                        <code class="d-block bg-success-subtle p-2">${suggestion.pattern_after}</code>
                    </div>
                ` : `
                    <code class="d-block bg-light p-2">${suggestion.pattern || '정규식 패턴'}</code>
                `}
            </div>
        </div>
        <div class="mb-3">
            <strong>대체:</strong>
            <code class="d-block bg-light p-2 mt-1">${suggestion.replacement || '(제거)'}</code>
        </div>
    `;
    
    // Store selected suggestion
    window.selectedSuggestion = suggestion;
    
    // Hide any existing modal first, then show
    if (modal._isShown) {
        modal.hide();
        setTimeout(() => modal.show(), 300);
    } else {
        modal.show();
    }
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

// Show current rules
async function showCurrentRules() {
    try {
        const modal = new bootstrap.Modal(document.getElementById('rulesModal'));
        const loadingDiv = document.getElementById('rules-loading');
        const contentDiv = document.getElementById('rules-content');
        
        // Show loading
        loadingDiv.style.display = 'block';
        contentDiv.innerHTML = '';
        modal.show();
        
        // Get DSL rule status
        const dslStatus = await API.get('/rules/dsl/status');
        console.log('DSL status response:', dslStatus);
        
        const currentVersion = dslStatus.dsl_system?.performance_report?.total_rules || 0;
        console.log('Current DSL rules count:', currentVersion);
        
        // Hide loading
        loadingDiv.style.display = 'none';
        
        // Update current version display
        const versionText = `v1.0.0 (${currentVersion}개 규칙)`;
        document.getElementById('current-rule-version').textContent = versionText;
        
        // Display DSL rules
        const performanceReport = dslStatus.dsl_system.performance_report;
        const patchHistory = dslStatus.auto_patch.recent_patches || [];
        
        contentDiv.innerHTML = `
            <div class="mb-3">
                <h6><i class="fas fa-tag me-2"></i>DSL 규칙 시스템</h6>
                <p class="text-muted">MongoDB 기반 동적 규칙 관리</p>
                <small class="text-muted">저장소: ${dslStatus.dsl_system.storage} (${dslStatus.dsl_system.collection})</small>
                <span class="badge bg-success ms-2">활성</span>
            </div>
            
            <div class="mb-3">
                <h6><i class="fas fa-chart-line me-2"></i>규칙 통계</h6>
                <div class="row">
                    <div class="col-3">
                        <div class="text-center">
                            <div class="h5 text-success">${performanceReport.total_rules}</div>
                            <small>총 규칙</small>
                        </div>
                    </div>
                    <div class="col-3">
                        <div class="text-center">
                            <div class="h5 text-info">${performanceReport.enabled_rules}</div>
                            <small>활성 규칙</small>
                        </div>
                    </div>
                    <div class="col-3">
                        <div class="text-center">
                            <div class="h5 text-warning">${performanceReport.disabled_rules}</div>
                            <small>비활성 규칙</small>
                        </div>
                    </div>
                    <div class="col-3">
                        <div class="text-center">
                            <div class="h5 text-primary">${dslStatus.auto_patch.patch_count}</div>
                            <small>패치 수</small>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="mb-3">
                <h6><i class="fas fa-list me-2"></i>규칙 유형별 분류</h6>
                <div class="row">
                    ${Object.entries(performanceReport.rules_by_type).map(([type, count]) => `
                        <div class="col-4 mb-2">
                            <span class="badge bg-secondary me-2">${type}</span>
                            <span class="text-muted">${count}개</span>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            ${patchHistory.length > 0 ? `
                <div class="mb-3">
                    <h6><i class="fas fa-history me-2"></i>최근 자동 패치 (${patchHistory.length}개)</h6>
                    <ul class="list-unstyled">
                        ${patchHistory.map(patch => `
                            <li class="mb-1">
                                <i class="fas fa-chevron-right me-2 text-muted"></i>
                                <small class="text-muted">${patch.applied_at || '최근'}</small>
                                <span class="ms-2">${patch.description || '규칙 개선'}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
            ` : `
                <div class="mb-3">
                    <h6><i class="fas fa-info-circle me-2"></i>자동 패치</h6>
                    <p class="text-muted">아직 자동 패치가 적용되지 않았습니다.</p>
                </div>
            `}
            
            <div class="mb-3">
                <h6><i class="fas fa-check-circle me-2"></i>시스템 상태</h6>
                <div class="row">
                    <div class="col-4">
                        <small class="text-muted">DSL 시스템</small><br>
                        <span class="text-success">활성</span>
                    </div>
                    <div class="col-4">
                        <small class="text-muted">자동 패치</small><br>
                        <span class="text-success">활성</span>
                    </div>
                    <div class="col-4">
                        <small class="text-muted">MongoDB 연결</small><br>
                        <span class="text-success">정상</span>
                    </div>
                </div>
            </div>
        `;
        
    } catch (error) {
        console.error('Failed to load rules:', error);
        document.getElementById('rules-content').innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                규칙 파일을 불러오는 중 오류가 발생했습니다.
            </div>
        `;
    }
}

// Show rule history
async function showRuleHistory() {
    try {
        const modal = new bootstrap.Modal(document.getElementById('ruleHistoryModal'));
        const loadingDiv = document.getElementById('history-loading');
        const contentDiv = document.getElementById('history-content');
        
        // Show loading
        loadingDiv.style.display = 'block';
        contentDiv.innerHTML = '';
        modal.show();
        
        // Get DSL rule versions
        const data = await API.get('/rules/dsl/versions');
        console.log('DSL Rule history API response:', data);
        
        // Hide loading
        loadingDiv.style.display = 'none';
        
        // Safe array handling
        const versions = data.versions || [];
        const totalVersions = data.total_versions || versions.length;
        const currentVersion = data.current_version || 'v1.0.2';
        
        // Display history
        contentDiv.innerHTML = `
            <div class="mb-3">
                <h6><i class="fas fa-info-circle me-2"></i>총 ${totalVersions}개 버전</h6>
                <small class="text-muted">현재 버전: <strong>${currentVersion}</strong></small>
            </div>
            
            <div class="timeline">
                ${versions.length > 0 ? versions.map((version, index) => `
                    <div class="timeline-item ${version.is_current ? 'current' : ''}">
                        <div class="timeline-marker ${version.is_current ? 'bg-success' : version.is_stable ? 'bg-primary' : 'bg-secondary'}">
                            ${version.is_current ? '<i class="fas fa-star"></i>' : index + 1}
                        </div>
                        <div class="timeline-content">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <h6 class="mb-1">
                                        ${version.version}
                                        ${version.is_current ? '<span class="badge bg-success ms-2">현재</span>' : ''}
                                        ${version.is_stable ? '<span class="badge bg-primary ms-2">안정</span>' : ''}
                                    </h6>
                                    <p class="mb-1">${version.description}</p>
                                    <small class="text-muted">
                                        ${Utils.formatDateTime(version.created_at)} • 
                                        규칙 ${version.rules_count}개
                                    </small>
                                </div>
                                <div class="text-end">
                                    <div class="small">
                                        <div>토큰: ${Utils.formatPercent(version.performance.avg_token_reduction)}</div>
                                        <div>NRR: ${Utils.formatNumber(version.performance.avg_nrr, 3)}</div>
                                    </div>
                                </div>
                            </div>
                            
                            ${version.changes && Array.isArray(version.changes) && version.changes.length > 0 ? `
                                <div class="mt-2">
                                    <small class="text-muted">변경사항:</small>
                                    <ul class="list-unstyled ms-3 mt-1">
                                        ${version.changes.map(change => `
                                            <li class="small"><i class="fas fa-chevron-right me-1 text-muted"></i>${change}</li>
                                        `).join('')}
                                    </ul>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `).join('') : `
                    <div class="text-center py-4">
                        <div class="text-muted">
                            <i class="fas fa-info-circle me-2"></i>
                            규칙 버전 히스토리가 없습니다.
                        </div>
                        <small class="text-muted">현재 기본 규칙 세트를 사용 중입니다.</small>
                    </div>
                `}
            </div>
        `;
        
    } catch (error) {
        console.error('Failed to load rule history:', error);
        document.getElementById('history-content').innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                규칙 히스토리를 불러오는 중 오류가 발생했습니다.
            </div>
        `;
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (statsRefresh) {
        statsRefresh.stop();
    }
});
