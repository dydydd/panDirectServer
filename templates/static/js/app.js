// ==================== 全局变量 ====================
let currentSection = 'dashboard';

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', function() {
    loadStatus();
    loadConfig();
    
    // 每30秒刷新一次状态
    setInterval(loadStatus, 30000);
    
    // 添加用户历史搜索和排序事件监听器
    const userSearchInput = document.getElementById('user-search-input');
    const userSortSelect = document.getElementById('user-sort-select');
    
    if (userSearchInput) {
        userSearchInput.addEventListener('input', function() {
            applyUserFilters();
            displayUserHistoryPage();
        });
    }
    
    if (userSortSelect) {
        userSortSelect.addEventListener('change', function() {
            applyUserFilters();
            displayUserHistoryPage();
        });
    }
});

// ==================== 导航切换 ====================
function showSection(section) {
    // 隐藏所有section
    document.querySelectorAll('.section').forEach(s => {
        s.classList.add('section-hidden');
    });
    
    // 显示选中的section
    document.getElementById(section + '-section').classList.remove('section-hidden');
    
    // 更新导航active状态
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    event.target.closest('.nav-item').classList.add('active');
    
    currentSection = section;
}

// ==================== 状态管理 ====================
async function loadStatus() {
    try {
        const response = await fetch('/api/status');
        const result = await response.json();
        
        if (result.code === 200) {
            const data = result.data;
            updateStatusBadges(data);
            updateDashboard(data);
        }
    } catch (error) {
        console.error('加载状态失败:', error);
    }
}

function updateStatusBadges(data) {
    const serviceStatus = document.getElementById('service-status');
    const embyStatus = document.getElementById('emby-status');
    const panStatus = document.getElementById('pan-status');
    
    // 服务状态
    if (data.service && data.service.status === 'running') {
        serviceStatus.className = 'badge badge-success';
        serviceStatus.innerHTML = '<span>●</span> 服务运行中';
    } else {
        serviceStatus.className = 'badge badge-danger';
        serviceStatus.innerHTML = '<span>●</span> 服务已停止';
    }
    
    // Emby状态
    if (data.emby && data.emby.status === 'running') {
        embyStatus.className = 'badge badge-success';
        embyStatus.innerHTML = '<span>●</span> Emby已连接';
    } else {
        embyStatus.className = 'badge badge-warning';
        embyStatus.innerHTML = '<span>●</span> Emby未配置';
    }
    
    // 网盘状态
    if (data['123'] && data['123'].status === 'connected') {
        panStatus.className = 'badge badge-success';
        panStatus.innerHTML = '<span>●</span> 123盘已连接';
    } else {
        panStatus.className = 'badge badge-warning';
        panStatus.innerHTML = '<span>●</span> 未连接';
    }
}

function updateDashboard(data) {
    // 更新仪表盘统计数据
    if (data.service) {
        document.getElementById('service-port').textContent = data.service.port || '5245';
    }
    
    if (data.emby) {
        document.getElementById('emby-server').textContent = data.emby.server || '未配置';
        document.getElementById('emby-port').textContent = data.emby.port || '8096';
    }
}

// ==================== 配置管理 ====================
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const result = await response.json();
        
        if (result.code === 200) {
            const config = result.data;
            populateConfigForm(config);
        }
    } catch (error) {
        console.error('加载配置失败:', error);
        showAlert('加载配置失败', 'error');
    }
}

function populateConfigForm(config) {
    // Emby配置
    document.getElementById('emby-enable').checked = config.emby?.enable || false;
    document.getElementById('emby-server').value = config.emby?.server || '';
    document.getElementById('emby-api-key').value = config.emby?.api_key === '******' ? '******' : (config.emby?.api_key || '');
    document.getElementById('emby-port').value = config.emby?.port || 8096;
    
    // 路径映射
    document.getElementById('path-mapping-enable').checked = config.emby?.path_mapping?.enable || false;
    document.getElementById('path-from').value = config.emby?.path_mapping?.from || '';
    document.getElementById('path-to').value = config.emby?.path_mapping?.to || '';
    
    // 123网盘配置
    document.getElementById('pan-enable').checked = config['123']?.enable || false;
    document.getElementById('client-id').value = config['123']?.client_id || '';
    document.getElementById('client-secret').value = config['123']?.client_secret || '';
    document.getElementById('mount-path').value = config['123']?.mount_path || '/123';
    document.getElementById('download-mode').value = config['123']?.download_mode || 'direct';
    
    // URL鉴权
    document.getElementById('url-auth-enable').checked = config['123']?.url_auth?.enable || false;
    document.getElementById('secret-key').value = config['123']?.url_auth?.secret_key === '******' ? '******' : (config['123']?.url_auth?.secret_key || '');
    document.getElementById('uid').value = config['123']?.url_auth?.uid || '';
    document.getElementById('expire-time').value = config['123']?.url_auth?.expire_time || 3600;
    document.getElementById('custom-domains').value = config['123']?.url_auth?.custom_domains?.join(',') || '';
    
    // 服务配置
    document.getElementById('service-port').value = config.service?.port || 5245;
    document.getElementById('external-url').value = config.service?.external_url || '';
    document.getElementById('log-level').value = config.service?.log_level || 'INFO';
}

async function saveConfig() {
    const config = {
        emby: {
            enable: document.getElementById('emby-enable').checked,
            server: document.getElementById('emby-server').value.trim(),
            api_key: document.getElementById('emby-api-key').value.trim(),
            port: parseInt(document.getElementById('emby-port').value),
            host: '0.0.0.0',
            proxy_enable: true,
            redirect_enable: true,
            ssl_verify: false,
            cache_enable: true,
            cache_expire_time: 3600,
            modify_playback_info: false,
            modify_items_info: true,
            path_mapping: {
                enable: document.getElementById('path-mapping-enable').checked,
                from: document.getElementById('path-from').value.trim(),
                to: document.getElementById('path-to').value.trim()
            }
        },
        '123': {
            enable: document.getElementById('pan-enable').checked,
            client_id: document.getElementById('client-id').value.trim(),
            client_secret: document.getElementById('client-secret').value.trim(),
            mount_path: document.getElementById('mount-path').value.trim(),
            download_mode: document.getElementById('download-mode').value,
            use_open_api: true,
            open_api_token: '',
            fallback_to_search: true,
            url_auth: {
                enable: document.getElementById('url-auth-enable').checked,
                secret_key: document.getElementById('secret-key').value.trim(),
                uid: document.getElementById('uid').value.trim(),
                expire_time: parseInt(document.getElementById('expire-time').value),
                custom_domains: document.getElementById('custom-domains').value.split(',').map(d => d.trim()).filter(d => d)
            }
        },
        service: {
            port: parseInt(document.getElementById('service-port').value),
            host: '0.0.0.0',
            external_url: document.getElementById('external-url').value.trim(),
            token: 'emby-proxy-token',
            username: 'admin',
            password: 'admin123',
            log_level: document.getElementById('log-level').value
        }
    };
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (result.code === 200) {
            showAlert('配置保存成功！请重启服务使配置生效。', 'success');
        } else {
            showAlert('保存失败: ' + (result.message || '未知错误'), 'error');
        }
    } catch (error) {
        console.error('保存配置失败:', error);
        showAlert('保存配置失败: ' + error.message, 'error');
    }
}

async function testPan123() {
    try {
        showAlert('正在测试连接...', 'warning');
        
        const response = await fetch('/api/test/123');
        const result = await response.json();
        
        if (result.code === 200) {
            showAlert('123网盘连接测试成功！', 'success');
        } else {
            showAlert('连接测试失败: ' + (result.message || '未知错误'), 'error');
        }
    } catch (error) {
        console.error('测试连接失败:', error);
        showAlert('测试连接失败: ' + error.message, 'error');
    }
}

async function restartService() {
    if (!confirm('确定要重启服务吗？这将中断当前所有连接。')) {
        return;
    }
    
    try {
        const response = await fetch('/api/restart', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.code === 200) {
            showAlert('服务正在重启...', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 3000);
        } else {
            showAlert('重启失败: ' + (result.message || '未知错误'), 'error');
        }
    } catch (error) {
        console.error('重启失败:', error);
        showAlert('重启失败: ' + error.message, 'error');
    }
}

// ==================== 提示框 ====================
function showAlert(message, type = 'success') {
    const alert = document.getElementById('alert');
    const alertText = document.getElementById('alert-text');
    
    // 移除所有类型类
    alert.className = 'alert show';
    
    // 添加对应类型类
    if (type === 'success') {
        alert.classList.add('alert-success');
    } else if (type === 'error') {
        alert.classList.add('alert-error');
    } else if (type === 'warning') {
        alert.classList.add('alert-warning');
    }
    
    alertText.textContent = message;
    
    // 3秒后自动隐藏
    setTimeout(() => {
        alert.classList.remove('show');
    }, 3000);
}

// ==================== 设备管理 ====================
let allUserHistory = {};
let filteredUserHistory = {};
let currentPage = 1;
const usersPerPage = 6;

async function loadDevices() {
    try {
        // 同时加载当前客户端和用户历史
        await Promise.all([
            loadCurrentClients(),
            loadUserHistory(),
            updateDeviceStats()
        ]);
    } catch (error) {
        console.error('加载设备失败:', error);
        showAlert('加载设备失败: ' + error.message, 'error');
    }
}

// 加载当前连接的客户端
async function loadCurrentClients() {
    try {
        const response = await fetch('/api/clients');
        if (!response.ok) throw new Error('获取客户端列表失败');
        
        const data = await response.json();
        const clients = data.data.clients;
        const clientsList = document.getElementById('current-clients-list');
        
        if (Object.keys(clients).length === 0) {
            clientsList.innerHTML = '<div class="empty-state"><p style="color: var(--gray-600);">暂无活跃客户端</p></div>';
            return;
        }
        
        let html = '';
        for (const [key, client] of Object.entries(clients)) {
            if (!client.client || client.client === 'Unknown') continue;
            
            const lastSeen = formatDateTime(client.last_seen);
            html += `
                <div style="background: var(--gray-50); border: 1px solid var(--gray-200); border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-weight: 600; color: var(--dark); margin-bottom: 0.25rem;">
                                📱 ${escapeHtml(client.client)} - ${escapeHtml(client.device)}
                            </div>
                            <div style="font-size: 0.875rem; color: var(--gray-600);">
                                👤 ${escapeHtml(client.username || 'Unknown')} | 🌐 ${escapeHtml(client.ip)} | ⏰ ${lastSeen}
                            </div>
                        </div>
                        <div style="display: flex; gap: 0.5rem;">
                            <button class="btn btn-danger-small btn-small" onclick="blockClientByName('${escapeHtml(client.client)}')">
                                拉黑客户端
                            </button>
                            <button class="btn btn-danger-small btn-small" onclick="blockClientByIP('${escapeHtml(client.ip)}')">
                                拉黑IP
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }
        
        clientsList.innerHTML = html;
        
    } catch (error) {
        console.error('加载当前客户端失败:', error);
        document.getElementById('current-clients-list').innerHTML = 
            '<div class="alert alert-error">❌ 加载客户端列表失败</div>';
    }
}

// 更新统计信息
async function updateDeviceStats() {
    try {
        const [clientsResponse, historyResponse] = await Promise.all([
            fetch('/api/clients'),
            fetch('/api/users/history')
        ]);
        
        if (clientsResponse.ok) {
            const clientsData = await clientsResponse.json();
            const activeClients = Object.keys(clientsData.data.clients).length;
            document.getElementById('active-clients-stat').textContent = activeClients;
        }
        
        if (historyResponse.ok) {
            const historyData = await historyResponse.json();
            const users = historyData.data.users;
            const totalUsers = Object.keys(users).length;
            const totalDevices = Object.values(users).reduce((sum, user) => sum + user.devices.length, 0);
            const totalIPs = Object.values(users).reduce((sum, user) => sum + user.ips.length, 0);
            
            document.getElementById('total-users-stat').textContent = totalUsers;
            document.getElementById('total-devices-stat').textContent = totalDevices;
            document.getElementById('total-ips-stat').textContent = totalIPs;
        }
    } catch (error) {
        console.error('更新统计信息失败:', error);
    }
}

// 加载用户历史记录
async function loadUserHistory() {
    try {
        const response = await fetch('/api/users/history');
        if (!response.ok) throw new Error('获取用户历史失败');
        
        const data = await response.json();
        allUserHistory = data.data.users;
        
        // 应用搜索和排序
        applyUserFilters();
        
        // 显示当前页
        displayUserHistoryPage();
        
    } catch (error) {
        console.error('加载用户历史失败:', error);
        document.getElementById('user-history-list').innerHTML = 
            '<div class="alert alert-error">❌ 加载用户历史失败</div>';
    }
}

// 应用搜索和排序过滤
function applyUserFilters() {
    const searchTerm = document.getElementById('user-search-input').value.toLowerCase();
    const sortBy = document.getElementById('user-sort-select').value;
    
    // 搜索过滤
    filteredUserHistory = {};
    for (const [userId, userInfo] of Object.entries(allUserHistory)) {
        if (userId.toLowerCase().includes(searchTerm)) {
            filteredUserHistory[userId] = userInfo;
        }
    }
    
    // 排序
    const sortedEntries = Object.entries(filteredUserHistory).sort((a, b) => {
        const [, userInfoA] = a;
        const [, userInfoB] = b;
        
        switch (sortBy) {
            case 'last_seen':
                return userInfoB.last_seen - userInfoA.last_seen;
            case 'device_count':
                return userInfoB.devices.length - userInfoA.devices.length;
            case 'ip_count':
                return userInfoB.ips.length - userInfoA.ips.length;
            default:
                return 0;
        }
    });
    
    // 重新构建过滤后的对象
    filteredUserHistory = {};
    sortedEntries.forEach(([userId, userInfo]) => {
        filteredUserHistory[userId] = userInfo;
    });
    
    // 重置到第一页
    currentPage = 1;
}

// 显示用户历史记录页面
function displayUserHistoryPage() {
    const userHistoryList = document.getElementById('user-history-list');
    const paginationDiv = document.getElementById('user-history-pagination');
    
    const filteredUsers = Object.keys(filteredUserHistory);
    const totalPages = Math.ceil(filteredUsers.length / usersPerPage);
    
    if (filteredUsers.length === 0) {
        userHistoryList.innerHTML = '<div class="empty-state"><p style="color: var(--gray-600);">暂无用户历史记录</p></div>';
        paginationDiv.innerHTML = '';
        return;
    }
    
    // 计算当前页的用户
    const startIndex = (currentPage - 1) * usersPerPage;
    const endIndex = Math.min(startIndex + usersPerPage, filteredUsers.length);
    const currentPageUsers = filteredUsers.slice(startIndex, endIndex);
    
    let html = '';
    currentPageUsers.forEach(userId => {
        const userInfo = filteredUserHistory[userId];
        const lastSeen = formatDateTime(userInfo.last_seen);
        
        html += `
            <div class="card" style="margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <div>
                        <div style="font-size: 1.125rem; font-weight: 600; color: var(--dark);">👤 ${escapeHtml(userId)}</div>
                        <div style="font-size: 0.875rem; color: var(--gray-600);">最后活动: ${lastSeen}</div>
                    </div>
                    <button class="btn btn-secondary btn-small" onclick="toggleUserDetails('${userId}')">
                        <span id="toggle-${userId}">📖 展开</span>
                    </button>
                </div>
                
                <div id="details-${userId}" style="display: none;">
                    <div style="margin-bottom: 1rem;">
                        <h5 style="margin: 0 0 0.5rem 0; color: var(--gray-700); font-size: 0.875rem;">📱 使用过的设备 (${userInfo.devices.length})</h5>
                        <div>
        `;
        
        userInfo.devices.forEach(device => {
            const deviceLastSeen = formatDateTime(device.last_seen);
            html += `
                <div style="display: inline-block; padding: 0.5rem 0.75rem; margin: 0.25rem; background: var(--gray-100); border-radius: 6px; font-size: 0.75rem;">
                    <div style="font-weight: 500;">${escapeHtml(device.client)} - ${escapeHtml(device.device)}</div>
                    <div style="color: var(--gray-600);">版本: ${escapeHtml(device.version)} | ${deviceLastSeen}</div>
                </div>
            `;
        });
        
        html += `
                        </div>
                    </div>
                    
                    <div>
                        <h5 style="margin: 0 0 0.5rem 0; color: var(--gray-700); font-size: 0.875rem;">🌐 使用过的IP (${userInfo.ips.length})</h5>
                        <div>
        `;
        
        userInfo.ips.forEach(ip => {
            const ipLastSeen = formatDateTime(ip.last_seen);
            html += `
                <div style="display: inline-block; padding: 0.5rem 0.75rem; margin: 0.25rem; background: #dbeafe; border-radius: 6px; font-size: 0.75rem;">
                    <div style="font-weight: 500;">${escapeHtml(ip.ip)}</div>
                    <div style="color: var(--gray-600);">${ipLastSeen}</div>
                </div>
            `;
        });
        
        html += `
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    userHistoryList.innerHTML = html;
    
    // 生成分页按钮
    generatePagination(totalPages, paginationDiv);
}

// 切换用户详情显示/隐藏
function toggleUserDetails(userId) {
    const detailsDiv = document.getElementById(`details-${userId}`);
    const toggleSpan = document.getElementById(`toggle-${userId}`);
    
    if (detailsDiv.style.display === 'none') {
        detailsDiv.style.display = 'block';
        toggleSpan.textContent = '📖 收起';
    } else {
        detailsDiv.style.display = 'none';
        toggleSpan.textContent = '📖 展开';
    }
}

// 生成分页按钮
function generatePagination(totalPages, paginationDiv) {
    if (totalPages <= 1) {
        paginationDiv.innerHTML = '';
        return;
    }
    
    let html = '';
    
    // 上一页按钮
    if (currentPage > 1) {
        html += `<button class="btn btn-secondary btn-small" onclick="goToUserPage(${currentPage - 1})">← 上一页</button>`;
    }
    
    // 页码按钮
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        const btnClass = i === currentPage ? 'btn-primary' : 'btn-secondary';
        html += `<button class="btn ${btnClass} btn-small" onclick="goToUserPage(${i})">${i}</button>`;
    }
    
    // 下一页按钮
    if (currentPage < totalPages) {
        html += `<button class="btn btn-secondary btn-small" onclick="goToUserPage(${currentPage + 1})">下一页 →</button>`;
    }
    
    paginationDiv.innerHTML = html;
}

// 跳转到指定页面
function goToUserPage(page) {
    currentPage = page;
    displayUserHistoryPage();
}

// 导出用户历史记录
function exportUserHistory() {
    try {
        const dataStr = JSON.stringify(allUserHistory, null, 2);
        const dataBlob = new Blob([dataStr], {type: 'application/json'});
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `user_history_${new Date().toISOString().split('T')[0]}.json`;
        link.click();
        URL.revokeObjectURL(url);
        showAlert('✅ 用户历史记录已导出', 'success');
    } catch (error) {
        showAlert('导出失败: ' + error.message, 'error');
    }
}

// 拉黑客户端（按名称）
async function blockClientByName(clientName) {
    if (!confirm(`确定要拦截客户端 "${clientName}" 吗？\n拦截后该类型的客户端将无法访问服务`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/clients/block', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                type: 'client',
                value: clientName
            })
        });
        
        if (!response.ok) throw new Error('拦截客户端失败');
        
        const data = await response.json();
        showAlert(`✅ ${data.message}`, 'success');
        
        setTimeout(() => loadDevices(), 1000);
        
    } catch (error) {
        showAlert('拦截客户端失败: ' + error.message, 'error');
    }
}

// 拉黑客户端（按IP）
async function blockClientByIP(ipAddress) {
    if (!confirm(`确定要拦截IP地址 "${ipAddress}" 吗？\n拦截后该IP地址将无法访问服务`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/clients/block', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                type: 'ip',
                value: ipAddress
            })
        });
        
        if (!response.ok) throw new Error('拦截IP失败');
        
        const data = await response.json();
        showAlert(`✅ ${data.message}`, 'success');
        
        setTimeout(() => loadDevices(), 1000);
        
    } catch (error) {
        showAlert('拦截IP失败: ' + error.message, 'error');
    }
}

// ==================== 客户端拦截 ====================
async function loadInterceptConfig() {
    try {
        const response = await fetch('/api/intercept/config');
        const result = await response.json();
        
        if (result.code === 200) {
            const config = result.data;
            document.getElementById('intercept-enable').checked = config.enable || false;
            document.getElementById('intercept-mode').value = config.mode || 'whitelist';
            document.getElementById('whitelist-devices').value = (config.whitelist_devices || []).join('\n');
            document.getElementById('blacklist-devices').value = (config.blacklist_devices || []).join('\n');
            document.getElementById('whitelist-ips').value = (config.whitelist_ips || []).join('\n');
        }
    } catch (error) {
        console.error('加载拦截配置失败:', error);
    }
}

async function saveInterceptConfig() {
    const config = {
        enable: document.getElementById('intercept-enable').checked,
        mode: document.getElementById('intercept-mode').value,
        whitelist_devices: document.getElementById('whitelist-devices').value
            .split('\n')
            .map(line => line.trim())
            .filter(line => line),
        blacklist_devices: document.getElementById('blacklist-devices').value
            .split('\n')
            .map(line => line.trim())
            .filter(line => line),
        whitelist_ips: document.getElementById('whitelist-ips').value
            .split('\n')
            .map(line => line.trim())
            .filter(line => line)
    };
    
    try {
        const response = await fetch('/api/intercept/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (result.code === 200) {
            showAlert('拦截配置保存成功！', 'success');
        } else {
            showAlert('保存失败: ' + (result.message || '未知错误'), 'error');
        }
    } catch (error) {
        console.error('保存拦截配置失败:', error);
        showAlert('保存拦截配置失败: ' + error.message, 'error');
    }
}

async function testInterceptRule() {
    const testDeviceId = prompt('请输入要测试的设备ID:');
    if (!testDeviceId) return;
    
    try {
        const response = await fetch('/api/intercept/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ device_id: testDeviceId })
        });
        
        const result = await response.json();
        
        if (result.code === 200) {
            const allowed = result.data.allowed;
            const reason = result.data.reason;
            if (allowed) {
                showAlert(`✅ 允许访问 - ${reason}`, 'success');
            } else {
                showAlert(`❌ 拒绝访问 - ${reason}`, 'warning');
            }
        } else {
            showAlert('测试失败: ' + (result.message || '未知错误'), 'error');
        }
    } catch (error) {
        console.error('测试失败:', error);
        showAlert('测试失败: ' + error.message, 'error');
    }
}

// ==================== 工具函数 ====================
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h}小时${m}分${s}秒`;
}

function formatDateTime(timestamp) {
    if (!timestamp) return '--';
    const date = new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}天前`;
    
    return date.toLocaleDateString('zh-CN');
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

