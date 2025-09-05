// Common JavaScript functions for Document Processing Pipeline

// API base URL - 배포된 서버 주소
const API_BASE = 'https://document-processing-pipeline.onrender.com/api';

// Utility functions
const Utils = {
    // Format numbers
    formatNumber(num, decimals = 2) {
        if (num === null || num === undefined || isNaN(num)) return '-';
        return Number(num).toFixed(decimals);
    },

    // Format percentage
    formatPercent(num, decimals = 1) {
        if (num === null || num === undefined || isNaN(num)) return '-';
        return Number(num).toFixed(decimals) + '%';
    },

    // Format time duration
    formatDuration(ms) {
        if (!ms) return '-';
        if (ms < 1000) return ms + 'ms';
        if (ms < 60000) return (ms / 1000).toFixed(1) + 's';
        if (ms < 3600000) return (ms / 60000).toFixed(1) + 'm';
        return (ms / 3600000).toFixed(1) + 'h';
    },

    // Format file size
    formatBytes(bytes) {
        if (!bytes) return '-';
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + sizes[i];
    },

    // Format date
    formatDateTime(dateStr) {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        return date.toLocaleString('ko-KR');
    },

    // Format relative time
    formatRelativeTime(dateStr) {
        if (!dateStr) return '-';
        const now = new Date();
        const date = new Date(dateStr);
        const diffMs = now - date;
        
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return '방금 전';
        if (diffMins < 60) return diffMins + '분 전';
        if (diffHours < 24) return diffHours + '시간 전';
        return diffDays + '일 전';
    },

    // Show toast notification
    showToast(message, type = 'info', duration = 5000) {
        const toastContainer = document.getElementById('toast-container') || this.createToastContainer();
        
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast, { delay: duration });
        bsToast.show();
        
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    },

    // Create toast container if it doesn't exist
    createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1055';
        document.body.appendChild(container);
        return container;
    },

    // Show loading spinner
    showLoading(element, message = '로딩 중...') {
        element.innerHTML = `
            <div class="text-center py-3">
                <div class="spinner-border spinner-border-sm" role="status"></div>
                <span class="ms-2">${message}</span>
            </div>
        `;
    },

    // Show error message
    showError(element, message = '오류가 발생했습니다.') {
        element.innerHTML = `
            <div class="text-center py-3 text-danger">
                <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                <div>${message}</div>
            </div>
        `;
    },

    // Debounce function
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Throttle function
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
};

// API service
const API = {
    // Generic API call
    async call(endpoint, options = {}) {
        const url = API_BASE + endpoint;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API call failed:', error);
            throw error;
        }
    },

    // GET request
    async get(endpoint) {
        return this.call(endpoint);
    },

    // POST request
    async post(endpoint, data) {
        return this.call(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    // PUT request
    async put(endpoint, data) {
        return this.call(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    // DELETE request
    async delete(endpoint) {
        return this.call(endpoint, {
            method: 'DELETE'
        });
    }
};

// Status badge helper
function getStatusBadge(status, text) {
    const badges = {
        'completed': 'success',
        'in_progress': 'primary',
        'pending': 'secondary',
        'failed': 'danger',
        'cancelled': 'warning'
    };
    
    const badgeClass = badges[status] || 'secondary';
    return `<span class="badge bg-${badgeClass}">${text || status}</span>`;
}

// Quality metrics helper
function getQualityBadge(value, threshold, isReverse = false) {
    const passed = isReverse ? value <= threshold : value >= threshold;
    const badgeClass = passed ? 'success' : 'danger';
    const icon = passed ? 'check' : 'times';
    
    return `<span class="badge bg-${badgeClass}">
        <i class="fas fa-${icon} me-1"></i>
        ${Utils.formatNumber(value, 3)}
    </span>`;
}

// Progress bar helper
function createProgressBar(value, max = 100, showText = true) {
    const percentage = Math.min((value / max) * 100, 100);
    const text = showText ? `${value}/${max} (${Utils.formatPercent(percentage)})` : '';
    
    return `
        <div class="progress mb-2">
            <div class="progress-bar" role="progressbar" style="width: ${percentage}%" 
                 aria-valuenow="${value}" aria-valuemin="0" aria-valuemax="${max}"></div>
        </div>
        ${text ? `<small class="text-muted">${text}</small>` : ''}
    `;
}

// Chart helpers
const ChartHelpers = {
    // Default chart options
    defaultOptions: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                beginAtZero: true
            }
        },
        plugins: {
            legend: {
                position: 'top'
            }
        }
    },

    // Create line chart
    createLineChart(ctx, data, options = {}) {
        return new Chart(ctx, {
            type: 'line',
            data: data,
            options: { ...this.defaultOptions, ...options }
        });
    },

    // Create bar chart
    createBarChart(ctx, data, options = {}) {
        return new Chart(ctx, {
            type: 'bar',
            data: data,
            options: { ...this.defaultOptions, ...options }
        });
    },

    // Create doughnut chart
    createDoughnutChart(ctx, data, options = {}) {
        return new Chart(ctx, {
            type: 'doughnut',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                },
                ...options
            }
        });
    }
};

// Initialize common functionality
document.addEventListener('DOMContentLoaded', function() {
    // Update current time
    function updateCurrentTime() {
        const timeElement = document.getElementById('current-time');
        if (timeElement) {
            timeElement.textContent = new Date().toLocaleString('ko-KR');
        }
    }
    
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);
    
    // Load current mode
    loadCurrentMode();
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Load current processing mode
async function loadCurrentMode() {
    try {
        const config = await API.get('/config');
        const modeElement = document.getElementById('current-mode');
        
        if (modeElement) {
            modeElement.textContent = config.mode;
            modeElement.className = 'badge bg-primary';
        }
    } catch (error) {
        console.error('Failed to load current mode:', error);
    }
}

// Auto-refresh functionality
class AutoRefresh {
    constructor(callback, interval = 30000) {
        this.callback = callback;
        this.interval = interval;
        this.intervalId = null;
        this.isActive = false;
    }
    
    start() {
        if (this.isActive) return;
        
        this.isActive = true;
        this.intervalId = setInterval(this.callback, this.interval);
    }
    
    stop() {
        if (!this.isActive) return;
        
        this.isActive = false;
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }
    
    setInterval(newInterval) {
        this.interval = newInterval;
        if (this.isActive) {
            this.stop();
            this.start();
        }
    }
}

// Export for use in other scripts
window.Utils = Utils;
window.API = API;
window.ChartHelpers = ChartHelpers;
window.AutoRefresh = AutoRefresh;
window.getStatusBadge = getStatusBadge;
window.getQualityBadge = getQualityBadge;
window.createProgressBar = createProgressBar;
