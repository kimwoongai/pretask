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
        
        // Batch stats (mock data for now)
        document.getElementById('batch-cycles').textContent = '3';
        document.getElementById('batch-stable').innerHTML = '<span class="badge bg-warning">개선중</span>';
        
        // Full processing stats (mock data for now)
        document.getElementById('full-ready').innerHTML = '<span class="badge bg-secondary">대기중</span>';
        document.getElementById('full-progress').textContent = '0%';
        
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
        // Mock data for recent results
        const recentResults = [
            {
                case_id: 'case_001',
                status: 'completed',
                timestamp: new Date(Date.now() - 300000).toISOString(), // 5 minutes ago
                metrics: { nrr: 0.94, fpr: 0.988, ss: 0.92, token_reduction: 23.5 }
            },
            {
                case_id: 'case_002', 
                status: 'completed',
                timestamp: new Date(Date.now() - 600000).toISOString(), // 10 minutes ago
                metrics: { nrr: 0.91, fpr: 0.983, ss: 0.89, token_reduction: 18.2 }
            },
            {
                case_id: 'case_003',
                status: 'failed',
                timestamp: new Date(Date.now() - 900000).toISOString(), // 15 minutes ago
                error: 'Quality gate failed: NRR below threshold'
            }
        ];
        
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
        // Mock data for quality trends
        const trendData = {
            labels: ['1시간 전', '50분 전', '40분 전', '30분 전', '20분 전', '10분 전', '현재'],
            datasets: [
                {
                    label: 'NRR',
                    data: [0.91, 0.92, 0.93, 0.94, 0.93, 0.94, 0.95],
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    tension: 0.1
                },
                {
                    label: 'FPR',
                    data: [0.983, 0.985, 0.987, 0.988, 0.987, 0.989, 0.990],
                    borderColor: 'rgb(54, 162, 235)',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    tension: 0.1
                },
                {
                    label: 'SS',
                    data: [0.88, 0.89, 0.90, 0.91, 0.90, 0.92, 0.93],
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    tension: 0.1
                }
            ]
        };
        
        updateQualityChart(trendData);
        
    } catch (error) {
        console.error('Failed to load quality trends:', error);
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
