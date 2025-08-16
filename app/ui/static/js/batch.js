/**
 * 배치 처리 모드 JavaScript
 */

// 전역 변수
let currentBatchJob = null;
let batchStatsInterval = null;

// DOM 로드 완료 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    initializeBatchPage();
});

// 페이지 초기화
function initializeBatchPage() {
    console.log('Batch page initialized');
    
    // 이벤트 리스너 설정
    setupEventListeners();
    
    // 초기 상태 로드
    loadBatchStats();
    loadBatchHistory();
    
    // 주기적 업데이트 시작
    startPeriodicUpdates();
}

// 이벤트 리스너 설정
function setupEventListeners() {
    // 배치 시작 버튼
    const startBatchBtn = document.getElementById('start-batch-btn');
    if (startBatchBtn) {
        startBatchBtn.addEventListener('click', startBatchProcessing);
    }
    
    // 배치 중지 버튼
    const stopBatchBtn = document.getElementById('stop-batch-btn');
    if (stopBatchBtn) {
        stopBatchBtn.addEventListener('click', stopBatchProcessing);
    }
    
    // 설정 저장 버튼
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', saveBatchSettings);
    }
}

// 배치 통계 로드
async function loadBatchStats() {
    try {
        const stats = await API.get('/batch/stats');
        updateBatchStatsUI(stats);
    } catch (error) {
        console.error('Failed to load batch stats:', error);
        // 기본값으로 UI 업데이트
        updateBatchStatsUI({
            status: 'idle',
            total_processed: 0,
            success_rate: 0,
            current_cycle: 0,
            estimated_completion: null
        });
    }
}

// 배치 히스토리 로드
async function loadBatchHistory() {
    try {
        const history = await API.get('/batch/history?limit=10');
        updateBatchHistoryUI(history);
    } catch (error) {
        console.error('Failed to load batch history:', error);
        updateBatchHistoryUI([]);
    }
}

// 배치 통계 UI 업데이트
function updateBatchStatsUI(stats) {
    // 상태 업데이트
    const statusElement = document.getElementById('batch-status');
    if (statusElement) {
        const statusClass = getStatusClass(stats.status);
        statusElement.innerHTML = `<span class="badge ${statusClass}">${getStatusText(stats.status)}</span>`;
    }
    
    // 진행률 업데이트
    const progressElement = document.getElementById('batch-progress');
    if (progressElement) {
        const progress = stats.progress || 0;
        progressElement.style.width = `${progress}%`;
        progressElement.textContent = `${progress.toFixed(1)}%`;
    }
    
    // 통계 업데이트
    updateStatElement('total-processed', stats.total_processed || 0);
    updateStatElement('success-rate', Utils.formatPercent(stats.success_rate || 0));
    updateStatElement('current-cycle', stats.current_cycle || 0);
    updateStatElement('estimated-completion', stats.estimated_completion ? 
        Utils.formatDateTime(stats.estimated_completion) : '-');
}

// 배치 히스토리 UI 업데이트
function updateBatchHistoryUI(history) {
    const historyBody = document.getElementById('batch-history-body');
    if (!historyBody) return;
    
    if (!history || history.length === 0) {
        historyBody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-muted">
                    <i class="fas fa-info-circle me-2"></i>
                    배치 처리 기록이 없습니다.
                </td>
            </tr>
        `;
        return;
    }
    
    historyBody.innerHTML = history.map(job => `
        <tr>
            <td><code>${job.job_id}</code></td>
            <td><span class="badge ${getStatusClass(job.status)}">${getStatusText(job.status)}</span></td>
            <td>${job.total_cases || 0}</td>
            <td>${job.processed_cases || 0}</td>
            <td>${Utils.formatPercent(job.success_rate || 0)}</td>
            <td>${Utils.formatDateTime(job.created_at)}</td>
        </tr>
    `).join('');
}

// 배치 처리 시작
async function startBatchProcessing() {
    try {
        const settings = getBatchSettings();
        
        Utils.showLoading('배치 처리를 시작하는 중...');
        
        const response = await API.post('/batch/start', settings);
        currentBatchJob = response.job_id;
        
        Utils.hideLoading();
        Utils.showSuccess('배치 처리가 시작되었습니다.');
        
        // UI 상태 업데이트
        updateBatchControlsUI(true);
        
    } catch (error) {
        Utils.hideLoading();
        Utils.showError('배치 처리 시작 실패: ' + error.message);
        console.error('Failed to start batch processing:', error);
    }
}

// 배치 처리 중지
async function stopBatchProcessing() {
    if (!currentBatchJob) {
        Utils.showWarning('실행 중인 배치 작업이 없습니다.');
        return;
    }
    
    try {
        Utils.showLoading('배치 처리를 중지하는 중...');
        
        await API.post(`/batch/stop/${currentBatchJob}`);
        
        Utils.hideLoading();
        Utils.showSuccess('배치 처리가 중지되었습니다.');
        
        // UI 상태 업데이트
        updateBatchControlsUI(false);
        currentBatchJob = null;
        
    } catch (error) {
        Utils.hideLoading();
        Utils.showError('배치 처리 중지 실패: ' + error.message);
        console.error('Failed to stop batch processing:', error);
    }
}

// 배치 설정 저장
async function saveBatchSettings() {
    try {
        const settings = getBatchSettings();
        
        await API.post('/batch/settings', settings);
        Utils.showSuccess('설정이 저장되었습니다.');
        
    } catch (error) {
        Utils.showError('설정 저장 실패: ' + error.message);
        console.error('Failed to save batch settings:', error);
    }
}

// 배치 설정 가져오기
function getBatchSettings() {
    return {
        batch_size: parseInt(document.getElementById('batch-size')?.value || 10),
        max_parallel: parseInt(document.getElementById('max-parallel')?.value || 3),
        retry_limit: parseInt(document.getElementById('retry-limit')?.value || 2),
        quality_threshold: parseFloat(document.getElementById('quality-threshold')?.value || 0.8),
        auto_patch_enabled: document.getElementById('auto-patch-enabled')?.checked || false,
        notification_enabled: document.getElementById('notification-enabled')?.checked || true
    };
}

// 배치 컨트롤 UI 업데이트
function updateBatchControlsUI(isRunning) {
    const startBtn = document.getElementById('start-batch-btn');
    const stopBtn = document.getElementById('stop-batch-btn');
    
    if (startBtn) {
        startBtn.disabled = isRunning;
        startBtn.innerHTML = isRunning ? 
            '<i class="fas fa-spinner fa-spin me-2"></i>실행 중' :
            '<i class="fas fa-play me-2"></i>배치 시작';
    }
    
    if (stopBtn) {
        stopBtn.disabled = !isRunning;
    }
}

// 주기적 업데이트 시작
function startPeriodicUpdates() {
    // 10초마다 통계 업데이트
    batchStatsInterval = setInterval(() => {
        loadBatchStats();
    }, 10000);
}

// 주기적 업데이트 중지
function stopPeriodicUpdates() {
    if (batchStatsInterval) {
        clearInterval(batchStatsInterval);
        batchStatsInterval = null;
    }
}

// 상태 클래스 가져오기
function getStatusClass(status) {
    const statusMap = {
        'idle': 'bg-secondary',
        'running': 'bg-primary',
        'paused': 'bg-warning',
        'completed': 'bg-success',
        'failed': 'bg-danger',
        'cancelled': 'bg-secondary'
    };
    return statusMap[status] || 'bg-secondary';
}

// 상태 텍스트 가져오기
function getStatusText(status) {
    const statusMap = {
        'idle': '대기',
        'running': '실행 중',
        'paused': '일시 정지',
        'completed': '완료',
        'failed': '실패',
        'cancelled': '취소됨'
    };
    return statusMap[status] || '알 수 없음';
}

// 통계 요소 업데이트 헬퍼
function updateStatElement(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value;
    }
}

// 페이지 언로드 시 정리
window.addEventListener('beforeunload', function() {
    stopPeriodicUpdates();
});

// 전역 함수로 내보내기 (필요한 경우)
window.BatchJS = {
    startBatchProcessing,
    stopBatchProcessing,
    saveBatchSettings,
    loadBatchStats,
    loadBatchHistory
};
