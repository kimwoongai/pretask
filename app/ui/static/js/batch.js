/**
 * 배치 처리 모드 JavaScript
 */

// 전역 변수
let currentBatchJob = null;
let batchStatsInterval = null;

// Utils 폴백 함수들을 먼저 정의
const UtilsFallback = {
    showLoading: function(message) {
        console.log('Loading:', message);
        // 간단한 로딩 표시
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'batch-loading';
        loadingDiv.innerHTML = `
            <div class="position-fixed top-50 start-50 translate-middle bg-dark text-white p-3 rounded">
                <i class="fas fa-spinner fa-spin me-2"></i>${message}
            </div>
        `;
        loadingDiv.style.zIndex = '9999';
        document.body.appendChild(loadingDiv);
    },
    hideLoading: function() {
        console.log('Loading hidden');
        const loadingDiv = document.getElementById('batch-loading');
        if (loadingDiv) {
            loadingDiv.remove();
        }
    },
    showSuccess: function(message) {
        alert('✅ 성공: ' + message);
        console.log('Success:', message);
    },
    showError: function(message) {
        alert('❌ 오류: ' + message);
        console.error('Error:', message);
    },
    showWarning: function(message) {
        alert('⚠️ 경고: ' + message);
        console.warn('Warning:', message);
    },
    formatPercent: function(value) {
        return (value * 100).toFixed(1) + '%';
    },
    formatDateTime: function(dateString) {
        return new Date(dateString).toLocaleString('ko-KR');
    }
};

// Utils가 없는 경우 즉시 폴백으로 설정
if (typeof Utils === 'undefined') {
    console.warn('Utils not found, using fallback');
    window.Utils = UtilsFallback;
}

// 추가 안전장치: 1초 후에도 Utils 재확인
setTimeout(() => {
    if (typeof Utils === 'undefined' || !Utils.hideLoading) {
        console.warn('Utils still not available after 1 second, forcing fallback');
        window.Utils = UtilsFallback;
    }
}, 1000);

// DOM 로드 완료 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    // Utils 재확인 및 폴백 설정
    if (typeof Utils === 'undefined') {
        console.warn('Utils still not found after DOM load, setting fallback');
        window.Utils = UtilsFallback;
    }
    
    // 페이지 초기화
    initializeBatchPage();
});

// 페이지 초기화
function initializeBatchPage() {
    console.log('Batch page initialized with Utils');
    
    // 이벤트 리스너 설정
    setupEventListeners();
    
    // 초기 상태 로드
    loadBatchStats();
    loadBatchHistory();
    
    // 주기적 업데이트 시작
    startPeriodicUpdates();
}

// Utils 없이 페이지 초기화 (폴백)
function initializeBatchPageWithoutUtils() {
    console.log('Batch page initialized without Utils (fallback mode)');
    
    // 기본 이벤트 리스너만 설정
    setupEventListenersWithoutUtils();
    
    // 기본 상태 표시
    showFallbackMessage();
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
    
    // 통계 업데이트 - 직접 UtilsFallback 사용
    updateStatElement('total-processed', stats.total_processed || 0);
    updateStatElement('success-rate', UtilsFallback.formatPercent(stats.success_rate || 0));
    updateStatElement('current-cycle', stats.current_cycle || 0);
    updateStatElement('estimated-completion', stats.estimated_completion ? 
        UtilsFallback.formatDateTime(stats.estimated_completion) : '-');
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
            <td>${UtilsFallback.formatPercent(job.success_rate || 0)}</td>
            <td>${UtilsFallback.formatDateTime(job.created_at)}</td>
        </tr>
    `).join('');
}

// 배치 처리 시작
async function startBatchProcessing() {
    // 강제로 Utils를 폴백으로 완전 교체
    console.log('startBatchProcessing: Utils check:', typeof Utils);
    console.log('startBatchProcessing: Utils.hideLoading check:', typeof Utils?.hideLoading);
    
    // Utils가 없거나 필수 함수가 없으면 완전히 교체
    if (typeof Utils === 'undefined' || typeof Utils.hideLoading !== 'function') {
        console.warn('Utils incomplete in startBatchProcessing, completely replacing with fallback');
        window.Utils = { ...UtilsFallback }; // 완전한 복사본으로 교체
    }
    
    try {
        const settings = getBatchSettings();
        
        // 직접 UtilsFallback 사용
        UtilsFallback.showLoading('배치 처리를 시작하는 중...');
        
        const response = await API.post('/batch/start', settings);
        currentBatchJob = response.job_id;
        
        UtilsFallback.hideLoading();
        UtilsFallback.showSuccess('배치 처리가 시작되었습니다.');
        
        // UI 상태 업데이트
        updateBatchControlsUI(true);
        
    } catch (error) {
        // 에러 처리에서는 항상 UtilsFallback 직접 사용
        UtilsFallback.hideLoading();
        UtilsFallback.showError('배치 처리 시작 실패: ' + error.message);
        console.error('Failed to start batch processing:', error);
    }
}

// 배치 처리 중지
async function stopBatchProcessing() {
    if (!currentBatchJob) {
        UtilsFallback.showWarning('실행 중인 배치 작업이 없습니다.');
        return;
    }
    
    try {
        UtilsFallback.showLoading('배치 처리를 중지하는 중...');
        
        await API.post(`/batch/stop/${currentBatchJob}`);
        
        UtilsFallback.hideLoading();
        UtilsFallback.showSuccess('배치 처리가 중지되었습니다.');
        
        // UI 상태 업데이트
        updateBatchControlsUI(false);
        currentBatchJob = null;
        
    } catch (error) {
        UtilsFallback.hideLoading();
        UtilsFallback.showError('배치 처리 중지 실패: ' + error.message);
        console.error('Failed to stop batch processing:', error);
    }
}

// 배치 설정 저장
async function saveBatchSettings() {
    try {
        const settings = getBatchSettings();
        
        await API.post('/batch/settings', settings);
        UtilsFallback.showSuccess('설정이 저장되었습니다.');
        
    } catch (error) {
        UtilsFallback.showError('설정 저장 실패: ' + error.message);
        console.error('Failed to save batch settings:', error);
    }
}

// 배치 설정 가져오기
function getBatchSettings() {
    return {
        sample_size: parseInt(document.getElementById('sample-size')?.value || 10),
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

// Utils 없이 이벤트 리스너 설정 (폴백)
function setupEventListenersWithoutUtils() {
    // 배치 시작 버튼
    const startBatchBtn = document.getElementById('start-batch-btn');
    if (startBatchBtn) {
        startBatchBtn.addEventListener('click', function() {
            alert('Utils 객체를 로드할 수 없어 배치 처리를 시작할 수 없습니다. 페이지를 새로고침해 주세요.');
        });
    }
}

// 폴백 메시지 표시
function showFallbackMessage() {
    const statusElement = document.getElementById('batch-status');
    if (statusElement) {
        statusElement.innerHTML = '<span class="badge bg-warning">시스템 로딩 중...</span>';
    }
}

// 배치 처리 시작 (Utils 폴백 버전) - 제거됨, 메인 함수에서 폴백 처리

// 전역 함수로 내보내기 (필요한 경우)
window.BatchJS = {
    startBatchProcessing,
    stopBatchProcessing,
    saveBatchSettings,
    loadBatchStats,
    loadBatchHistory
};
