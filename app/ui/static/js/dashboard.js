// Dashboard JavaScript

let qualityChart = null;
let systemMetricsRefresh = null;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Dashboard DOM 로드 완료');
    console.log('✅ 현재 페이지 URL:', window.location.pathname);
    console.log('✅ DOM 요소 수:', document.querySelectorAll('*').length);
    
    loadDashboardData();
    initializeCharts();
    
    // 규칙 전용 처리 초기화를 약간 지연
    setTimeout(() => {
        console.log('🔧 규칙 처리 초기화 시작...');
        initializeRuleProcessing();
    }, 100);
    
    // Auto-refresh every 30 seconds
    systemMetricsRefresh = new AutoRefresh(loadSystemMetrics, 30000);
    systemMetricsRefresh.start();
    
    console.log('✅ Dashboard 초기화 완료');
});

// 페이지 로드 완료 후에도 한 번 더 시도
window.addEventListener('load', function() {
    console.log('✅ 페이지 완전 로드 완료');
    
    // DOM이 아직 준비되지 않았다면 다시 시도
    setTimeout(() => {
        const testButton = document.getElementById('test-rule-processing');
        if (testButton && !testButton.onclick) {
            console.log('🔄 테스트 버튼 재초기화 시도...');
            initializeRuleProcessing();
        }
    }, 500);
});

// Load all dashboard data
async function loadDashboardData() {
    await Promise.all([
        loadModeStatus(),
        loadProcessingStats(),
        loadSystemMetrics(),
        loadRecentResults(),
        loadQualityTrends()
    ]);
}

// Load mode status and configuration
async function loadModeStatus() {
    try {
        const config = await API.get('/config');
        
        // Update mode status
        const modeStatus = document.getElementById('mode-status');
        modeStatus.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-cog me-2 text-primary"></i>
                <strong>${config.mode}</strong>
            </div>
        `;
        
        // Update mode details
        const modeDetails = document.getElementById('mode-details');
        const autoPatch = document.getElementById('auto-patch-status');
        const autoAdvance = document.getElementById('auto-advance-status');
        const batchApi = document.getElementById('batch-api-status');
        const qualityGates = document.getElementById('quality-gates');
        
        autoPatch.textContent = config.auto_patch ? '활성' : '비활성';
        autoPatch.className = `badge ${config.auto_patch ? 'bg-success' : 'bg-secondary'}`;
        
        autoAdvance.textContent = config.auto_advance ? '활성' : '비활성';
        autoAdvance.className = `badge ${config.auto_advance ? 'bg-success' : 'bg-secondary'}`;
        
        batchApi.textContent = config.use_batch_api ? '사용' : '미사용';
        batchApi.className = `badge ${config.use_batch_api ? 'bg-info' : 'bg-secondary'}`;
        
        const gates = config.quality_gates;
        qualityGates.textContent = `NRR≥${gates.min_nrr}, FPR≥${gates.min_fpr}, SS≥${gates.min_ss}, 토큰절감≥${gates.min_token_reduction}%`;
        
        modeDetails.style.display = 'block';
        
    } catch (error) {
        console.error('Failed to load mode status:', error);
        const modeStatus = document.getElementById('mode-status');
        modeStatus.innerHTML = `
            <div class="text-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                모드 정보 로딩 실패
            </div>
        `;
    }
}

// Load processing statistics
async function loadProcessingStats() {
    try {
        // Single run stats
        const singleStats = await API.get('/single-run/stats').catch(() => ({ consecutive_passes: 0, ready_for_batch_mode: false }));
        
        document.getElementById('single-consecutive').textContent = singleStats.consecutive_passes || 0;
        document.getElementById('single-ready').innerHTML = singleStats.ready_for_batch_mode ? 
            '<span class="badge bg-success">준비완료</span>' : 
            '<span class="badge bg-secondary">준비중</span>';
        
        // Batch stats - 실제 데이터 또는 기본값
        try {
            const batchStats = await API.get('/batch/stats').catch(() => null);
            if (batchStats) {
                document.getElementById('batch-cycles').textContent = batchStats.cycles || '0';
                document.getElementById('batch-stable').innerHTML = batchStats.is_stable ? 
                    '<span class="badge bg-success">안정</span>' : 
                    '<span class="badge bg-warning">개선중</span>';
            } else {
                document.getElementById('batch-cycles').textContent = '0';
                document.getElementById('batch-stable').innerHTML = '<span class="badge bg-secondary">대기중</span>';
            }
        } catch (error) {
            document.getElementById('batch-cycles').textContent = '0';
            document.getElementById('batch-stable').innerHTML = '<span class="badge bg-secondary">대기중</span>';
        }
        
        // Full processing stats - 실제 데이터 또는 기본값
        try {
            const fullStats = await API.get('/full/stats').catch(() => null);
            if (fullStats) {
                document.getElementById('full-ready').innerHTML = fullStats.ready ? 
                    '<span class="badge bg-success">준비완료</span>' : 
                    '<span class="badge bg-secondary">대기중</span>';
                document.getElementById('full-progress').textContent = `${fullStats.progress || 0}%`;
            } else {
                document.getElementById('full-ready').innerHTML = '<span class="badge bg-secondary">대기중</span>';
                document.getElementById('full-progress').textContent = '0%';
            }
        } catch (error) {
            document.getElementById('full-ready').innerHTML = '<span class="badge bg-secondary">대기중</span>';
            document.getElementById('full-progress').textContent = '0%';
        }
        
    } catch (error) {
        console.error('Failed to load processing stats:', error);
    }
}

// Load system metrics
async function loadSystemMetrics() {
    try {
        const metrics = await API.get('/monitoring/metrics');
        
        if (metrics.system_metrics) {
            const system = metrics.system_metrics;
            
            document.getElementById('cpu-usage').textContent = Utils.formatPercent(system.cpu_percent);
            document.getElementById('memory-usage').textContent = Utils.formatPercent(system.memory_percent);
            document.getElementById('db-status').innerHTML = '<span class="badge bg-success">정상</span>';
        }
        
        // Load recent alerts
        const alerts = await API.get('/monitoring/alerts?hours=1').catch(() => []);
        document.getElementById('alert-count').textContent = alerts.length || 0;
        
    } catch (error) {
        console.error('Failed to load system metrics:', error);
        document.getElementById('cpu-usage').textContent = '-';
        document.getElementById('memory-usage').textContent = '-';
        document.getElementById('db-status').innerHTML = '<span class="badge bg-danger">오류</span>';
        document.getElementById('alert-count').textContent = '-';
    }
}

// Load recent processing results
async function loadRecentResults() {
    const container = document.getElementById('recent-results');
    
    try {
        // 실제 최근 처리 결과 조회
        const recentResults = await API.get('/processed-cases?limit=10&sort=created_at&order=desc').catch(() => []);
        
        console.log('🔍 Recent results 데이터 타입:', typeof recentResults);
        console.log('🔍 Recent results 내용:', recentResults);
        console.log('🔍 Recent results Array 여부:', Array.isArray(recentResults));
        
        container.innerHTML = '';
        
        // 배열인지 확인 후 처리
        if (Array.isArray(recentResults)) {
            recentResults.forEach(result => {
                const resultElement = document.createElement('div');
                resultElement.className = 'list-group-item d-flex justify-content-between align-items-start';
                
                const statusBadge = getStatusBadge(result.status, 
                    result.status === 'completed' ? '완료' : 
                    result.status === 'failed' ? '실패' : '진행중');
                
                let metricsHtml = '';
                if (result.metrics) {
                    // Utils가 없는 경우를 대비한 안전한 포맷팅
                    const nrrValue = typeof result.metrics.nrr === 'number' ? (result.metrics.nrr * 100).toFixed(1) + '%' : 'N/A';
                    const fprValue = typeof result.metrics.fpr === 'number' ? (result.metrics.fpr * 100).toFixed(1) + '%' : 'N/A';
                    const tokenValue = typeof result.metrics.token_reduction === 'number' ? result.metrics.token_reduction.toFixed(1) + '%' : 'N/A';
                    
                    metricsHtml = `
                        <div class="mt-1">
                            <small class="text-muted">
                                NRR: ${nrrValue} | 
                                FPR: ${fprValue} | 
                                토큰절감: ${tokenValue}
                            </small>
                        </div>
                    `;
                } else if (result.error) {
                    metricsHtml = `<div class="mt-1"><small class="text-danger">${result.error}</small></div>`;
                }
                
                // 시간 포맷팅 안전 처리
                let timeDisplay = 'N/A';
                if (result.timestamp) {
                    try {
                        timeDisplay = new Date(result.timestamp).toLocaleString();
                    } catch (e) {
                        timeDisplay = result.timestamp;
                    }
                } else if (result.created_at) {
                    try {
                        timeDisplay = new Date(result.created_at).toLocaleString();
                    } catch (e) {
                        timeDisplay = result.created_at;
                    }
                }
                
                resultElement.innerHTML = `
                    <div class="ms-2 me-auto">
                        <div class="fw-bold">${result.case_name || result.case_id || 'Unknown'}</div>
                        <small class="text-muted">${timeDisplay}</small>
                        ${metricsHtml}
                    </div>
                    <div>${statusBadge}</div>
                `;
                
                container.appendChild(resultElement);
            });
            
            if (recentResults.length === 0) {
                container.innerHTML = '<div class="text-center py-3 text-muted">최근 처리 결과가 없습니다.</div>';
            }
        } else {
            console.warn('🔍 Recent results가 배열이 아닙니다:', typeof recentResults, recentResults);
            container.innerHTML = '<div class="text-center py-3 text-muted">데이터 형식 오류 - 배열이 아닌 데이터를 받았습니다.</div>';
        }
        
    } catch (error) {
        console.error('Failed to load recent results:', error);
        container.innerHTML = `<div class="alert alert-danger">최근 결과 로딩 실패: ${error.message}</div>`;
    }
}

// Load quality trends
async function loadQualityTrends() {
    try {
        // 실제 품질 트렌드 데이터 조회
        const trendsData = await API.get('/analytics/quality-trends?hours=24').catch(() => null);
        
        let trendData;
        if (trendsData && trendsData.data && trendsData.data.length > 0) {
            // 실제 데이터가 있는 경우
            trendData = {
                labels: trendsData.labels || [],
                datasets: [
                    {
                        label: 'NRR',
                        data: trendsData.data.map(d => d.nrr || 0),
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.1)',
                        tension: 0.1
                    },
                    {
                        label: 'FPR',
                        data: trendsData.data.map(d => d.fpr || 0),
                        borderColor: 'rgb(54, 162, 235)',
                        backgroundColor: 'rgba(54, 162, 235, 0.1)',
                        tension: 0.1
                    },
                    {
                        label: 'SS',
                        data: trendsData.data.map(d => d.ss || 0),
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        tension: 0.1
                    }
                ]
            };
        } else {
            // 데이터가 없는 경우 빈 차트
            trendData = {
                labels: ['데이터 없음'],
                datasets: [
                    {
                        label: 'NRR',
                        data: [0],
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.1)',
                        tension: 0.1
                    },
                    {
                        label: 'FPR',
                        data: [0],
                        borderColor: 'rgb(54, 162, 235)',
                        backgroundColor: 'rgba(54, 162, 235, 0.1)',
                        tension: 0.1
                    },
                    {
                        label: 'SS',
                        data: [0],
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        tension: 0.1
                    }
                ]
            };
        }
        
        updateQualityChart(trendData);
        
    } catch (error) {
        console.error('Failed to load quality trends:', error);
        // 오류 시 빈 차트 표시
        const emptyData = {
            labels: ['오류'],
            datasets: [
                {
                    label: 'NRR',
                    data: [0],
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    tension: 0.1
                },
                {
                    label: 'FPR', 
                    data: [0],
                    borderColor: 'rgb(54, 162, 235)',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    tension: 0.1
                },
                {
                    label: 'SS',
                    data: [0],
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    tension: 0.1
                }
            ]
        };
        updateQualityChart(emptyData);
    }
}

// Initialize charts
function initializeCharts() {
    const ctx = document.getElementById('quality-trend-chart');
    if (ctx) {
        qualityChart = ChartHelpers.createLineChart(ctx, {
            labels: [],
            datasets: []
        }, {
            scales: {
                y: {
                    beginAtZero: false,
                    min: 0.8,
                    max: 1.0
                }
            },
            plugins: {
                legend: {
                    position: 'top'
                }
            }
        });
    }
}

// Update quality chart
function updateQualityChart(data) {
    if (qualityChart) {
        qualityChart.data = data;
        qualityChart.update();
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (systemMetricsRefresh) {
        systemMetricsRefresh.stop();
    }
});

// ==================== 간단한 테스트 함수 ====================
function simpleTest() {
    console.log('🎯 simpleTest 함수 호출됨!');
    alert('simpleTest 함수가 정상 작동합니다!');
}

// 전역에서 접근 가능하도록 설정
window.simpleTest = simpleTest;

// ==================== 규칙 전용 처리 기능 ====================

let ruleProcessingStatus = null;
let ruleProcessingInterval = null;

// 규칙 전용 처리 초기화
function initializeRuleProcessing() {
    console.log('🔧 initializeRuleProcessing 함수 호출됨');
    
    // DOM이 완전히 로드되었는지 확인
    console.log('🔧 DOM 상태:', document.readyState);
    console.log('🔧 전체 DOM 요소 수:', document.querySelectorAll('*').length);
    
    // 테스트 버튼 이벤트
    const testButton = document.getElementById('test-rule-processing');
    console.log('🔧 테스트 버튼 찾기 결과:', testButton);
    console.log('🔧 테스트 버튼 HTML:', testButton ? testButton.outerHTML : 'null');
    
    if (testButton) {
        console.log('✅ 테스트 버튼 발견! 이벤트 리스너 추가 중...');
        
        // 기존 이벤트 리스너 제거 (중복 방지)
        testButton.replaceWith(testButton.cloneNode(true));
        const newTestButton = document.getElementById('test-rule-processing');
        console.log('🔧 새 테스트 버튼:', newTestButton);
        
        newTestButton.addEventListener('click', function(e) {
            console.log('🎯 테스트 버튼 클릭 이벤트 발생!');
            console.log('🎯 이벤트 객체:', e);
            e.preventDefault();
            e.stopPropagation();
            
            // 간단한 테스트부터
            alert('🎉 버튼 클릭이 감지되었습니다!');
            console.log('🎯 alert 표시 완료, testRuleProcessing 함수 호출 시작');
            
            // 실제 함수 호출
            testRuleProcessing();
        });
        
        console.log('✅ 테스트 버튼 이벤트 리스너 추가 완료');
    } else {
        console.error('❌ 테스트 버튼을 찾을 수 없습니다');
        console.log('🔧 사용 가능한 버튼들:', document.querySelectorAll('button'));
        console.log('🔧 test-rule-processing ID를 가진 요소들:', document.querySelectorAll('[id*="test-rule"]'));
    }
    
    // 전체 처리 시작 버튼 이벤트
    const startButton = document.getElementById('start-rule-processing');
    console.log('시작 버튼 찾기:', startButton);
    
    if (startButton) {
        console.log('시작 버튼 이벤트 리스너 추가');
        startButton.addEventListener('click', function(e) {
            console.log('시작 버튼 클릭됨');
            e.preventDefault();
            startRuleProcessing();
        });
    } else {
        console.error('시작 버튼을 찾을 수 없습니다');
    }
    
    // 초기 상태 확인
    checkRuleProcessingStatus();
}

// 규칙 전용 처리 테스트
async function testRuleProcessing() {
    console.log('testRuleProcessing 함수 호출됨');
    
    const testButton = document.getElementById('test-rule-processing');
    const testLimit = document.getElementById('test-limit').value;
    const testResults = document.getElementById('test-results');
    
    console.log('테스트 버튼:', testButton);
    console.log('테스트 개수:', testLimit);
    console.log('결과 영역:', testResults);
    
    try {
        // 버튼 비활성화
        testButton.disabled = true;
        testButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>테스트 중...';
        
        console.log('API 호출 시작:', `/process/rule-only/test?limit=${testLimit}`);
        
        // 테스트 실행 - API 경로 수정 (API_BASE에 이미 /api가 포함되어 있음)
        const response = await API.post(`/process/rule-only/test?limit=${testLimit}`);
        
        console.log('API 응답:', response);
        
        if (response.status === 'success') {
            const results = response.test_results;
            
            // 결과 표시
            testResults.innerHTML = `
                <div class="alert alert-success alert-sm">
                    <strong>✅ 테스트 완료</strong><br>
                    • 처리된 문서: ${results.processed_documents}개<br>
                    • 평균 압축률: ${results.average_reduction_rate}%<br>
                    • 적용된 규칙: ${results.total_rules_applied}개<br>
                    • 규칙 버전: ${results.current_rules_version}
                </div>
            `;
            testResults.style.display = 'block';
            
            // 성공 알림
            showNotification('테스트 완료', `${results.processed_documents}개 문서 처리 완료 (평균 ${results.average_reduction_rate}% 압축)`, 'success');
            
        } else {
            throw new Error(response.message || '테스트 실패');
        }
        
    } catch (error) {
        console.error('테스트 실패:', error);
        console.error('에러 스택:', error.stack);
        
        let errorMessage = error.message;
        if (error.message.includes('Failed to fetch')) {
            errorMessage = '서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.';
        } else if (error.message.includes('404')) {
            errorMessage = 'API 엔드포인트를 찾을 수 없습니다. 서버 설정을 확인해주세요.';
        }
        
        testResults.innerHTML = `
            <div class="alert alert-danger alert-sm">
                <strong>❌ 테스트 실패</strong><br>
                ${errorMessage}<br>
                <small class="text-muted">자세한 내용은 브라우저 콘솔을 확인하세요.</small>
            </div>
        `;
        testResults.style.display = 'block';
        
        showNotification('테스트 실패', errorMessage, 'error');
        
    } finally {
        // 버튼 복구
        testButton.disabled = false;
        testButton.innerHTML = '<i class="fas fa-flask me-1"></i>테스트';
    }
}

// 규칙 전용 전체 처리 시작
async function startRuleProcessing() {
    const startButton = document.getElementById('start-rule-processing');
    const batchSize = document.getElementById('batch-size').value;
    
    try {
        // 확인 대화상자
        if (!confirm(`모든 판례를 기본 규칙만으로 전처리하시겠습니까?\n배치 크기: ${batchSize}개`)) {
            return;
        }
        
        // 버튼 비활성화
        startButton.disabled = true;
        startButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>시작 중...';
        
        // 처리 시작 (API_BASE에 이미 /api가 포함되어 있음)
        const response = await API.post(`/process/rule-only?batch_size=${batchSize}`);
        
        if (response.status === 'started') {
            // 성공 알림
            showNotification('처리 시작', '규칙 전용 전처리가 백그라운드에서 시작되었습니다', 'success');
            
            // 진행 상황 표시 시작
            startRuleProcessingMonitoring();
            
        } else {
            throw new Error(response.message || '처리 시작 실패');
        }
        
    } catch (error) {
        console.error('처리 시작 실패:', error);
        showNotification('처리 시작 실패', error.message, 'error');
        
        // 버튼 복구
        startButton.disabled = false;
        startButton.innerHTML = '<i class="fas fa-play me-1"></i>시작';
    }
}

// 규칙 처리 상태 모니터링 시작
function startRuleProcessingMonitoring() {
    const statusDiv = document.getElementById('rule-processing-status');
    statusDiv.style.display = 'block';
    
    // 주기적으로 상태 확인 (5초마다)
    ruleProcessingInterval = setInterval(checkRuleProcessingStatus, 5000);
    
    // 즉시 한 번 실행
    checkRuleProcessingStatus();
}

// 규칙 처리 상태 확인
async function checkRuleProcessingStatus() {
    try {
        const response = await API.get('/process/rule-only/status');
        
        if (response.status === 'success') {
            updateRuleProcessingUI(response.data);
        }
        
    } catch (error) {
        console.error('상태 확인 실패:', error);
    }
}

// 규칙 처리 UI 업데이트
function updateRuleProcessingUI(data) {
    const statusDiv = document.getElementById('rule-processing-status');
    const progressBar = document.getElementById('rule-progress-bar');
    const processedCount = document.getElementById('processed-count');
    const processingRate = document.getElementById('processing-rate');
    const startButton = document.getElementById('start-rule-processing');
    
    if (data.status === 'running') {
        // 진행 중
        statusDiv.style.display = 'block';
        processedCount.textContent = data.processed_count.toLocaleString();
        processingRate.textContent = `${data.processing_rate}/초`;
        
        // 진행률 계산 (임시로 처리된 수 기반)
        const progress = Math.min(data.processed_count / 1000 * 100, 100);
        progressBar.style.width = `${progress}%`;
        progressBar.textContent = `${Math.round(progress)}%`;
        
        // 버튼 상태
        startButton.disabled = true;
        startButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>처리 중...';
        
    } else if (data.status === 'completed') {
        // 완료
        processedCount.textContent = data.processed_count.toLocaleString();
        processingRate.textContent = `${data.processing_rate}/초`;
        
        progressBar.style.width = '100%';
        progressBar.textContent = '완료';
        progressBar.className = 'progress-bar bg-success';
        
        // 버튼 복구
        startButton.disabled = false;
        startButton.innerHTML = '<i class="fas fa-play me-1"></i>시작';
        
        // 모니터링 중지
        if (ruleProcessingInterval) {
            clearInterval(ruleProcessingInterval);
            ruleProcessingInterval = null;
        }
        
        // 완료 알림
        showNotification('처리 완료', `총 ${data.processed_count.toLocaleString()}개 문서 처리 완료`, 'success');
        
    } else {
        // 대기 상태
        statusDiv.style.display = 'none';
        startButton.disabled = false;
        startButton.innerHTML = '<i class="fas fa-play me-1"></i>시작';
    }
}

// 알림 표시 함수
function showNotification(title, message, type = 'info') {
    // 간단한 알림 구현 (Toast 또는 Alert 사용)
    const alertClass = {
        'success': 'alert-success',
        'error': 'alert-danger',
        'warning': 'alert-warning',
        'info': 'alert-info'
    }[type] || 'alert-info';
    
    const notification = document.createElement('div');
    notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
    notification.innerHTML = `
        <strong>${title}</strong><br>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // 5초 후 자동 제거
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}
