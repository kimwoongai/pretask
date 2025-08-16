// Dashboard JavaScript

let qualityChart = null;
let systemMetricsRefresh = null;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    loadDashboardData();
    initializeCharts();
    
    // Auto-refresh every 30 seconds
    systemMetricsRefresh = new AutoRefresh(loadSystemMetrics, 30000);
    systemMetricsRefresh.start();
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
        
        container.innerHTML = '';
        
        recentResults.forEach(result => {
            const resultElement = document.createElement('div');
            resultElement.className = 'list-group-item d-flex justify-content-between align-items-start';
            
            const statusBadge = getStatusBadge(result.status, 
                result.status === 'completed' ? '완료' : 
                result.status === 'failed' ? '실패' : '진행중');
            
            let metricsHtml = '';
            if (result.metrics) {
                metricsHtml = `
                    <div class="mt-1">
                        <small class="text-muted">
                            NRR: ${Utils.formatNumber(result.metrics.nrr, 3)} | 
                            FPR: ${Utils.formatNumber(result.metrics.fpr, 3)} | 
                            토큰절감: ${Utils.formatPercent(result.metrics.token_reduction)}
                        </small>
                    </div>
                `;
            } else if (result.error) {
                metricsHtml = `<div class="mt-1"><small class="text-danger">${result.error}</small></div>`;
            }
            
            resultElement.innerHTML = `
                <div class="ms-2 me-auto">
                    <div class="fw-bold">${result.case_id}</div>
                    <small class="text-muted">${Utils.formatRelativeTime(result.timestamp)}</small>
                    ${metricsHtml}
                </div>
                <div>${statusBadge}</div>
            `;
            
            container.appendChild(resultElement);
        });
        
    } catch (error) {
        console.error('Failed to load recent results:', error);
        Utils.showError(container, '최근 결과를 로딩할 수 없습니다.');
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
