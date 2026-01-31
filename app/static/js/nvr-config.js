/**
 * NVR配置模块
 * 包含NVR配置的CRUD操作和通道管理
 */

// 当前编辑的NVR配置ID
let currentEditingNvrConfigId = null;
// 当前编辑的通道配置列表
let channelConfigs = [];
// 标记数据库地址是否被用户手动修改过
let dbHostManuallyChanged = false;

/**
 * 加载所有NVR配置
 */
async function loadNvrConfigs() {
  try {
    const configs = await api("/api/nvr-configs");
    const listDiv = document.getElementById("nvr-config-list");
    if (!listDiv) return;

    if (!configs || configs.length === 0) {
      listDiv.innerHTML = `
        <div style="padding:40px; text-align:center; border:2px dashed var(--border); border-radius:12px; background:rgba(34,211,238,0.05);">
          <div style="font-size:48px; margin-bottom:16px;">📹</div>
          <div class="muted" style="font-size:16px; margin-bottom:8px;">暂无NVR配置</div>
          <div class="muted" style="font-size:13px; margin-bottom:20px;">点击右上角"新增NVR配置"按钮开始添加</div>
          <button class="secondary" onclick="showNvrConfigForm()" style="font-size:14px; padding:10px 20px;">
            <span style="font-size:16px; margin-right:6px;">+</span> 立即添加
          </button>
        </div>
      `;
      return;
    }

    // 使用表格形式展示配置列表
    let html = `
      <div style="overflow-x:auto;">
        <table style="width:100%; border-collapse:separate; border-spacing:0;">
          <thead>
            <tr style="background:rgba(34,211,238,0.1);">
              <th style="padding:12px; text-align:left; font-size:13px; font-weight:600; color:var(--text); border-bottom:2px solid var(--accent);">序号</th>
              <th style="padding:12px; text-align:left; font-size:13px; font-weight:600; color:var(--text); border-bottom:2px solid var(--accent);">车场名称</th>
              <th style="padding:12px; text-align:left; font-size:13px; font-weight:600; color:var(--text); border-bottom:2px solid var(--accent);">NVR信息</th>
              <th style="padding:12px; text-align:left; font-size:13px; font-weight:600; color:var(--text); border-bottom:2px solid var(--accent);">数据库信息</th>
              <th style="padding:12px; text-align:left; font-size:13px; font-weight:600; color:var(--text); border-bottom:2px solid var(--accent);">通道数量</th>
              <th style="padding:12px; text-align:left; font-size:13px; font-weight:600; color:var(--text); border-bottom:2px solid var(--accent);">操作</th>
            </tr>
          </thead>
          <tbody>
    `;
    
    configs.forEach((config, index) => {
      const channels = Array.isArray(config.channels) ? config.channels : [];
      const channelCount = channels.length;
      const channelsWithSpaces = channels.filter(ch => ch.parking_spaces && ch.parking_spaces.length > 0).length;
      const channelsWithTrack = channels.filter(ch => ch.track_space && String(ch.track_space).trim() !== "").length;
      const dbInfo = config.db_host && config.db_name 
        ? `${config.db_host}:${config.db_port || 3306}/${config.db_name}`
        : '<span class="muted">未配置</span>';

      const channelExtra = [];
      if (channelsWithSpaces > 0) channelExtra.push(`有车位：${channelsWithSpaces}`);
      if (channelsWithTrack > 0) channelExtra.push(`识别区域：${channelsWithTrack}`);
      const channelSummary = channelExtra.length > 0 ? `（${channelExtra.join('，')}）` : '';
      
      html += `
        <tr style="border-bottom:1px solid var(--border); transition:background 0.2s;" 
            onmouseover="this.style.background='rgba(255,255,255,0.03)'" 
            onmouseout="this.style.background='transparent'">
          <td style="padding:16px; font-size:13px; color:var(--muted);">${index + 1}</td>
          <td style="padding:16px;">
            <div style="font-weight:600; font-size:14px; color:var(--text); margin-bottom:4px;">${config.parking_name}</div>
          </td>
          <td style="padding:16px;">
            <div style="font-size:12px; margin-bottom:4px;">
              <span class="muted">IP:</span> <span style="color:var(--text);">${config.nvr_ip}:${config.nvr_port}</span>
            </div>
            <div style="font-size:12px;">
              <span class="muted">账号:</span> <span style="color:var(--text);">${config.nvr_username}</span>
            </div>
          </td>
          <td style="padding:16px;">
            <div style="font-size:12px; color:var(--text); word-break:break-all;">${dbInfo}</div>
          </td>
          <td style="padding:16px;">
            <div style="font-size:13px; font-weight:600;">
              <span class="link" style="font-weight:600;" onclick="viewNvrChannelSpaces(${config.id})">
                通道：${channelCount} 个
              </span>
            </div>
            ${channelSummary ? `<div class="muted" style="font-size:11px; margin-top:4px;">${channelSummary}</div>` : ""}
          </td>
          <td style="padding:16px;">
            <div style="display:flex; gap:8px;">
              <button class="ghost" style="font-size:12px; padding:6px 12px;" onclick="editNvrConfig(${config.id})" title="编辑配置">编辑</button>
              <button class="ghost" style="font-size:12px; padding:6px 12px; color:#ff6b6b;" onclick="deleteNvrConfig(${config.id})" title="删除配置">删除</button>
              <button class="ghost" style="font-size:12px; padding:6px 12px; color:var(--accent);" onclick="viewNvrConfigDetail(${config.id})" title="查看详情">详情</button>
            </div>
          </td>
        </tr>
      `;
    });
    
    html += `
          </tbody>
        </table>
      </div>
    `;
    
    listDiv.innerHTML = html;
  } catch (e) {
    console.error("加载NVR配置失败:", e);
    document.getElementById("nvr-config-list").innerHTML = '<div class="muted">加载失败</div>';
  }
}

/**
 * 同步NVR IP地址到数据库地址
 */
function syncNvrIpToDbHost() {
  const nvrIp = document.getElementById("nvr-ip").value.trim();
  const dbHostInput = document.getElementById("nvr-db-host");
  
  // 如果数据库地址为空，或者是之前同步的值，则自动同步
  // 如果用户已经手动修改过，则不自动覆盖
  if (!dbHostManuallyChanged || !dbHostInput.value.trim()) {
    dbHostInput.value = nvrIp;
  }
}

/**
 * 显示NVR配置表单（新增）
 */
function showNvrConfigForm() {
  currentEditingNvrConfigId = null;
  channelConfigs = [];
  dbHostManuallyChanged = false;
  document.getElementById("nvr-form-title").textContent = "新增NVR配置";
  const summaryBar = document.getElementById("nvr-summary-bar");
  if (summaryBar) {
    summaryBar.style.display = "none";
    summaryBar.textContent = "";
  }
  const form = document.getElementById("nvr-config-form");
  form.style.display = "block";
  
  // 隐藏列表，显示表单
  const listContainer = document.getElementById("nvr-config-list-container");
  if (listContainer) {
    listContainer.style.display = "none";
  }
  
  // 清空表单
  document.getElementById("nvr-ip").value = "";
  document.getElementById("nvr-parking-name").value = "";
  document.getElementById("nvr-username").value = "admin";
  document.getElementById("nvr-password").value = "admin123=";
  document.getElementById("nvr-port").value = "10081";
  document.getElementById("nvr-db-host").value = "";
  document.getElementById("nvr-db-user").value = "";
  document.getElementById("nvr-db-password").value = "";
  document.getElementById("nvr-db-port").value = "3306";
  document.getElementById("nvr-db-name").value = "";
  document.getElementById("channel-config-list").innerHTML = "";
  
  // 为数据库地址输入框添加手动修改标记
  const dbHostInput = document.getElementById("nvr-db-host");
  dbHostInput.addEventListener('input', function() {
    dbHostManuallyChanged = true;
  });
  
  // 初始化通道配置列表显示
  renderChannelConfigs();
  
  // 滚动到表单
  document.getElementById("nvr-config-form").scrollIntoView({ behavior: 'smooth' });
  
  // 延迟滚动到通道配置区域，确保用户能看到
  setTimeout(() => {
    const channelSection = document.querySelector('#channel-config-list')?.parentElement;
    if (channelSection) {
      channelSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, 300);
}

/**
 * 取消NVR配置表单
 */
function cancelNvrConfigForm() {
  document.getElementById("nvr-config-form").style.display = "none";
  const listContainer = document.getElementById("nvr-config-list-container");
  if (listContainer) {
    listContainer.style.display = "block";
  }
  currentEditingNvrConfigId = null;
  channelConfigs = [];
  dbHostManuallyChanged = false;
}

/**
 * 编辑NVR配置
 */
async function editNvrConfig(configId) {
  try {
    const config = await api(`/api/nvr-configs/${configId}`);
    currentEditingNvrConfigId = configId;
    channelConfigs = config.channels || [];
    dbHostManuallyChanged = false; // 编辑时重置标记
    document.getElementById("nvr-form-title").textContent = "编辑NVR配置";
    const summaryBar = document.getElementById("nvr-summary-bar");
    if (summaryBar) {
      const chs = Array.isArray(config.channels) ? config.channels : [];
      const totalChannels = chs.length;
      const totalSpaces = chs.reduce((sum, ch) => sum + ((ch.parking_spaces && ch.parking_spaces.length) || 0), 0);
      summaryBar.textContent = `${config.parking_name || ''}（${config.nvr_ip || ''}:${config.nvr_port || ''}）｜通道：${totalChannels} 个｜总车位：${totalSpaces} 个`;
      summaryBar.style.display = "block";
    }
    document.getElementById("nvr-ip").value = config.nvr_ip;
    document.getElementById("nvr-parking-name").value = config.parking_name;
    document.getElementById("nvr-username").value = config.nvr_username;
    document.getElementById("nvr-password").value = config.nvr_password;
    document.getElementById("nvr-port").value = config.nvr_port;
    
    // 如果数据库地址为空，自动使用NVR IP
    const dbHost = config.db_host || config.nvr_ip;
    document.getElementById("nvr-db-host").value = dbHost;
    document.getElementById("nvr-db-user").value = config.db_user || "";
    document.getElementById("nvr-db-password").value = config.db_password || "";
    document.getElementById("nvr-db-port").value = config.db_port || "3306";
    document.getElementById("nvr-db-name").value = config.db_name || "";
    
    // 为数据库地址输入框添加手动修改标记
    const dbHostInput = document.getElementById("nvr-db-host");
    dbHostInput.addEventListener('input', function() {
      dbHostManuallyChanged = true;
    });
    
    renderChannelConfigs();
    const form = document.getElementById("nvr-config-form");
    form.style.display = "block";
    
    // 隐藏列表，显示表单
    const listContainer = document.getElementById("nvr-config-list-container");
    if (listContainer) {
      listContainer.style.display = "none";
    }
    
    form.scrollIntoView({ behavior: 'smooth' });
  } catch (e) {
    console.error("加载NVR配置失败:", e);
    alert("加载配置失败: " + (e.message || e));
  }
}

/**
 * 删除NVR配置
 */
async function deleteNvrConfig(configId) {
  if (!confirm("确定要删除这个NVR配置吗？删除后无法恢复。")) {
    return;
  }
  
  try {
    await api(`/api/nvr-configs/${configId}`, { method: "DELETE" });
    alert("删除成功");
    loadNvrConfigs();
  } catch (e) {
    console.error("删除NVR配置失败:", e);
    alert("删除失败: " + (e.message || e));
  }
}

/**
 * 查看NVR配置详情（基础信息 + 通道列表简要）
 * 保留原有功能，供“详情”按钮使用
 */
async function viewNvrConfigDetail(configId) {
  try {
    const config = await api(`/api/nvr-configs/${configId}`);
    
    // 构建详情HTML
    let detailHtml = `
      <div style="max-width:800px; max-height:80vh; overflow-y:auto;">
        <h4 style="margin:0 0 20px 0; color:var(--accent);">${config.parking_name} - 配置详情</h4>
        
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:24px;">
          <div>
            <h5 style="margin:0 0 12px 0; font-size:14px; color:var(--text);">NVR基本信息</h5>
            <div style="background:rgba(0,0,0,0.2); border-radius:8px; padding:12px;">
              <div style="margin-bottom:8px;"><span class="muted">IP地址:</span> <span style="color:var(--text);">${config.nvr_ip}:${config.nvr_port}</span></div>
              <div style="margin-bottom:8px;"><span class="muted">账号:</span> <span style="color:var(--text);">${config.nvr_username}</span></div>
              <div><span class="muted">密码:</span> <span style="color:var(--text);">${'*'.repeat(config.nvr_password?.length || 0)}</span></div>
            </div>
          </div>
          
          <div>
            <h5 style="margin:0 0 12px 0; font-size:14px; color:var(--text);">数据库信息</h5>
            <div style="background:rgba(0,0,0,0.2); border-radius:8px; padding:12px;">
              <div style="margin-bottom:8px;"><span class="muted">地址:</span> <span style="color:var(--text);">${config.db_host || '未配置'}</span></div>
              <div style="margin-bottom:8px;"><span class="muted">账号:</span> <span style="color:var(--text);">${config.db_user || '未配置'}</span></div>
              <div style="margin-bottom:8px;"><span class="muted">端口:</span> <span style="color:var(--text);">${config.db_port || 3306}</span></div>
              <div><span class="muted">数据库:</span> <span style="color:var(--text);">${config.db_name || '未配置'}</span></div>
            </div>
          </div>
        </div>
        
        <div>
          <h5 style="margin:0 0 12px 0; font-size:14px; color:var(--text);">通道概览 (${config.channels?.length || 0}个)</h5>
          <div class="muted" style="font-size:12px;">
            详细的通道与车位信息请通过列表中的“通道数量”链接查看。
          </div>
        </div>
      </div>
    `;
    
    // 显示模态框
    showDetailModal(detailHtml);
  } catch (e) {
    console.error("加载NVR配置详情失败:", e);
    alert("加载详情失败: " + (e.message || e));
  }
}

/**
 * 查看某个NVR的“通道 + 车位详情”
 * 从列表中的“通道数量”点击进入
 */
async function viewNvrChannelSpaces(configId) {
  try {
    const config = await api(`/api/nvr-configs/${configId}`);
    const channelCount = config.channels ? config.channels.length : 0;

    let detailHtml = `
      <div style="max-width:1100px; max-height:80vh; overflow-y:auto;">
        <h4 style="margin:0 0 12px 0; color:var(--accent);">
          NVR: ${config.nvr_ip}:${config.nvr_port} - 通道与车位详情
        </h4>
        <div class="muted" style="font-size:12px; margin-bottom:16px;">
          车场名称：${config.parking_name || "-"} ｜ 通道数量：${channelCount} 个（以下为扁平列表：一行 = 一个通道上的一个车位）
        </div>
    `;

    if (!config.channels || config.channels.length === 0) {
      detailHtml += `
        <div style="padding:20px; text-align:center; border:1px dashed var(--border); border-radius:8px;">
          <div class="muted" style="font-size:13px;">暂无通道配置，请先在“编辑”中添加通道。</div>
        </div>
      </div>`;
      showDetailModal(detailHtml);
      return;
    }

    // 按通道分组的扁平列表：先输出通道组头，再输出该通道的车位行
    detailHtml += `
      <div style="overflow-x:auto;">
        <table style="width:100%; border-collapse:separate; border-spacing:0;">
          <thead>
            <tr style="background:rgba(30,64,175,0.6);">
              <th style="padding:8px 10px; font-size:12px;">序号</th>
              <th style="padding:8px 10px; font-size:12px;">车位号</th>
              <th style="padding:8px 10px; font-size:12px;">坐标 (x1, y1, x2, y2)</th>
            </tr>
          </thead>
          <tbody>
    `;

    let rowIndex = 1;
    let hasAnySpace = false;

    config.channels.forEach((ch) => {
      const spaces = Array.isArray(ch.parking_spaces) ? ch.parking_spaces : [];
      const spaceCount = spaces.length;
      const hasTrack = ch.track_space && String(ch.track_space).trim() !== "";

      // 通道组头行
      detailHtml += `
        <tr style="background:rgba(15,23,42,0.95);">
          <td colspan="3" style="padding:8px 10px; font-size:12px;">
            <span style="color:var(--accent); font-weight:600;">通道：${ch.channel_code || '-'}</span>
            <span style="margin-left:8px; color:var(--muted);">IP：${ch.camera_ip || '-'}</span>
            <span style="margin-left:8px; color:var(--muted);">名称：${ch.camera_name || '-'}</span>
            <span style="margin-left:8px; color:var(--muted);">SN：${ch.camera_sn || '-'}</span>
            <span style="margin-left:8px; color:var(--muted);">车位：${spaceCount} 个</span>
            <span style="margin-left:8px; color:${hasTrack ? '#4ade80' : '#9ca3af'};">
              识别区域：${hasTrack ? '已配置' : '未配置'}
            </span>
          </td>
        </tr>
      `;

      if (!spaces || spaces.length === 0) {
        detailHtml += `
          <tr>
            <td colspan="3" style="padding:10px 10px; font-size:12px; color:var(--muted);">
              暂无车位数据。可在“编辑”中为该通道配置SN并查询车位。
            </td>
          </tr>
        `;
        return;
      }

      hasAnySpace = true;

      spaces.forEach((ps) => {
        const bbox = Array.isArray(ps.bbox) ? ps.bbox : [];
        const coordText = bbox.length === 4 ? bbox.join(", ") : "-";
        detailHtml += `
          <tr>
            <td style="padding:8px 10px; font-size:12px; color:var(--muted);">${rowIndex++}</td>
            <td style="padding:8px 10px; font-size:12px; color:var(--text);">${ps.space_name || ps.space_id || "-"}</td>
            <td style="padding:8px 10px; font-size:12px; font-family:monospace; color:#e5e7eb;">${coordText}</td>
          </tr>
        `;
      });
    });

    if (!hasAnySpace) {
      detailHtml += `
        <tr>
          <td colspan="3" style="padding:16px; text-align:center; font-size:12px; color:var(--muted);">
            所有通道当前都没有车位数据。可在“编辑”中为通道配置SN并查询车位后再查看。
          </td>
        </tr>
      `;
    }

    detailHtml += `
          </tbody>
        </table>
      </div>
      </div>
    `;

    showDetailModal(detailHtml);
  } catch (e) {
    console.error("加载NVR通道+车位详情失败:", e);
    alert("加载通道与车位详情失败: " + (e.message || e));
  }
}

/**
 * 折叠/展开某个通道的车位表格
 */
function toggleNvrChannelSection(sectionId) {
  const el = document.getElementById(sectionId);
  if (!el) return;
  const collapsed = el.getAttribute("data-collapsed") === "true";
  if (collapsed) {
    el.style.display = "block";
    el.setAttribute("data-collapsed", "false");
  } else {
    el.style.display = "none";
    el.setAttribute("data-collapsed", "true");
  }
}

/**
 * 显示详情模态框
 */
function showDetailModal(content) {
  // 创建模态框
  let modal = document.getElementById('nvr-detail-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'nvr-detail-modal';
    modal.className = 'modal';
    modal.style.cssText = 'position:fixed; inset:0; background:rgba(0,0,0,0.72); display:none; justify-content:center; align-items:center; z-index:9999; padding:20px;';
    modal.onclick = function(e) {
      if (e.target === modal) {
        closeDetailModal();
      }
    };
    document.body.appendChild(modal);
  }
  
  modal.innerHTML = `
    <div class="modal-content" style="max-width:1200px; width:95vw; max-height:90vh; overflow-y:auto; background:#0b1220; border:1px solid var(--border); border-radius:12px; padding:24px;">
      ${content}
      <div style="margin-top:24px; padding-top:20px; border-top:1px solid var(--border); text-align:right;">
        <button class="ghost" onclick="closeDetailModal()" style="font-size:14px; padding:10px 24px;">关闭</button>
      </div>
    </div>
  `;
  
  modal.style.display = 'flex';
}

/**
 * 关闭详情模态框
 */
function closeDetailModal() {
  const modal = document.getElementById('nvr-detail-modal');
  if (modal) {
    modal.style.display = 'none';
  }
}

/**
 * 添加通道配置
 * 直接添加一个空的通道配置，用户可以在表单中填写所有信息
 */
function addChannelConfig() {
  // 生成默认通道编号（c1, c2, c3...）
  let channelCode = "c1";
  let counter = 1;
  while (channelConfigs.find(ch => ch.channel_code.toLowerCase() === channelCode.toLowerCase())) {
    counter++;
    channelCode = `c${counter}`;
  }
  
  // 添加新的通道配置
  channelConfigs.push({
    id: null,
    channel_code: channelCode,
    camera_ip: "",
    camera_name: "",
    camera_sn: "",
    track_space: "",
    parking_spaces: []
  });
  
  renderChannelConfigs();
  
  // 滚动到新添加的通道配置
  setTimeout(() => {
    const channelList = document.getElementById("channel-config-list");
    if (channelList) {
      const lastChannel = channelList.querySelector('div:last-child');
      if (lastChannel) {
        lastChannel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        // 自动聚焦到通道编号输入框
        const channelCodeInput = lastChannel.querySelector('input[placeholder*="c1"]');
        if (channelCodeInput) {
          setTimeout(() => channelCodeInput.focus(), 200);
        }
      }
    }
  }, 100);
}

/**
 * 检查通道编号是否重复
 */
function checkChannelCodeDuplicate(index) {
  const channel = channelConfigs[index];
  if (!channel || !channel.channel_code) return;
  
  const duplicate = channelConfigs.find((ch, idx) => 
    idx !== index && 
    ch.channel_code && 
    ch.channel_code.toLowerCase() === channel.channel_code.toLowerCase()
  );
  
  if (duplicate) {
    alert(`通道编号 "${channel.channel_code}" 已存在，请使用其他编号`);
    // 恢复为默认值或清空
    const defaultCode = `c${index + 1}`;
    channel.channel_code = defaultCode;
    renderChannelConfigs();
  }
}

/**
 * 删除通道配置
 */
function removeChannelConfig(index) {
  if (confirm("确定要删除这个通道配置吗？")) {
    channelConfigs.splice(index, 1);
    renderChannelConfigs();
  }
}

/**
 * 渲染通道配置列表
 */
function renderChannelConfigs() {
  const listDiv = document.getElementById("channel-config-list");
  if (!listDiv) return;

  if (channelConfigs.length === 0) {
    listDiv.innerHTML = `
      <div style="padding:20px; text-align:center; border:2px dashed var(--border); border-radius:8px; background:rgba(34,211,238,0.05);">
        <div class="muted" style="margin-bottom:12px; font-size:14px;">暂无通道配置</div>
        <button class="secondary" onclick="addChannelConfig()" style="font-size:13px; padding:8px 16px;">+ 点击添加第一个通道</button>
      </div>
    `;
    return;
  }

  let html = '<div style="display:flex; flex-direction:column; gap:12px;">';
  channelConfigs.forEach((ch, index) => {
    html += `
      <div style="border:1px solid var(--border); border-radius:8px; padding:16px; background:rgba(255,255,255,0.02);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid var(--border);">
          <div>
            <h5 style="margin:0 0 4px 0;">通道配置 ${index + 1}</h5>
            <div class="muted" style="font-size:12px;">填写下方信息完成通道配置</div>
          </div>
          <button class="ghost" style="font-size:12px; padding:4px 8px; color:#ff6b6b;" onclick="removeChannelConfig(${index})">删除通道</button>
        </div>
        <div class="row">
          <label>所属通道 *</label>
          <div style="display:flex; gap:8px; align-items:center;">
            <input type="text" value="${ch.channel_code || ''}" placeholder="例如: c1" 
                   onchange="channelConfigs[${index}].channel_code = this.value.trim(); checkChannelCodeDuplicate(${index});" 
                   oninput="channelConfigs[${index}].channel_code = this.value" 
                   style="max-width:120px;" />
            <div class="muted" style="font-size:11px;">通道编号（如: c1, c2, c3, c4）</div>
          </div>
        </div>
        <div class="row">
          <label>摄像头IP *</label>
          <input type="text" value="${ch.camera_ip || ''}" placeholder="例如: 192.168.1.121" 
                 onchange="channelConfigs[${index}].camera_ip = this.value" 
                 oninput="channelConfigs[${index}].camera_ip = this.value" />
        </div>
        <div class="row">
          <label>摄像头名称 *</label>
          <input type="text" value="${ch.camera_name || ''}" placeholder="例如: 高新四路26号枪机" 
                 onchange="channelConfigs[${index}].camera_name = this.value" 
                 oninput="channelConfigs[${index}].camera_name = this.value" />
        </div>
        <div class="row">
          <label>摄像头SN *</label>
          <div style="display:flex; flex-direction:column; gap:8px;">
            <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
              <input type="text" value="${ch.camera_sn || ''}" placeholder="例如: GXSLqj000026" 
                     onchange="channelConfigs[${index}].camera_sn = this.value; autoFetchParkingSpaces(${index}); autoFetchTrackSpace(${index});" 
                     oninput="channelConfigs[${index}].camera_sn = this.value" 
                     onblur="autoFetchParkingSpaces(${index}); autoFetchTrackSpace(${index});"
                     style="flex:1; min-width:220px;" />
              <button class="ghost" style="font-size:12px; padding:4px 8px;" 
                      onclick="manualFetchParkingSpaces(${index})"
                      title="手动查询车位坐标">
                查询车位
              </button>
              <button class="ghost" style="font-size:12px; padding:4px 8px;" 
                      onclick="manualFetchTrackSpace(${index})"
                      title="手动查询识别停车区域坐标">
                查询识别区域
              </button>
            </div>
            ${ch.parking_spaces && ch.parking_spaces.length > 0 ? `
              <div style="padding:8px; background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); border-radius:6px;">
                <div style="font-size:12px; color:#10b981; font-weight:600; margin-bottom:6px;">
                  ✓ 已查询到 ${ch.parking_spaces.length} 个车位
                </div>
                <div style="display:flex; flex-wrap:wrap; gap:6px;">
                  ${ch.parking_spaces.map(ps => `
                    <span style="font-size:11px; padding:4px 8px; background:rgba(16,185,129,0.15); border-radius:4px; color:#10b981;">
                      ${ps.space_name || ps.space_id} [${Array.isArray(ps.bbox) ? ps.bbox.join(',') : ps.bbox}]
                    </span>
                  `).join('')}
                </div>
              </div>
            ` : ch.camera_sn ? `
              <div style="font-size:11px; color:var(--muted); padding:4px 8px;">
                输入SN后将自动查询车位信息和识别停车区域坐标...
              </div>
            ` : ''}
          </div>
        </div>
        <div class="row">
          <label>识别停车区域坐标</label>
          <div style="display:flex; flex-direction:column; gap:4px;">
            <textarea 
              rows="3"
              placeholder="将自动从外部数据库的 track_space 字段查询并填充（仅存原始字符串，例如多边形坐标JSON）"
              onchange="channelConfigs[${index}].track_space = this.value"
              oninput="channelConfigs[${index}].track_space = this.value"
              style="width:100%; font-size:12px; font-family:monospace; white-space:pre;"
            >${ch.track_space ? ("" + ch.track_space) : ""}</textarea>
            <div class="muted" style="font-size:11px;">
              提示：该字段直接保存外部库中的 <code>track_space</code> 原始值，通常为JSON或坐标字符串，可用于后续画停车区域轮廓。
            </div>
          </div>
        </div>
      </div>
    `;
  });
  html += '</div>';
  listDiv.innerHTML = html;
}

/**
 * 自动查询车位坐标（输入SN后自动触发）
 */
let autoFetchTimeout = null;
async function autoFetchParkingSpaces(index) {
  const channel = channelConfigs[index];
  if (!channel || !channel.camera_sn || !channel.camera_sn.trim()) {
    channel.parking_spaces = [];
    renderChannelConfigs();
    return;
  }

  // 防抖：延迟500ms后查询，避免频繁请求
  if (autoFetchTimeout) {
    clearTimeout(autoFetchTimeout);
  }
  
  autoFetchTimeout = setTimeout(async () => {
    await doFetchParkingSpaces(index, false);
  }, 500);
}

/**
 * 自动查询识别停车区域坐标（track_space），随SN输入一起触发
 */
async function autoFetchTrackSpace(index) {
  const channel = channelConfigs[index];
  if (!channel || !channel.camera_sn || !channel.camera_sn.trim()) {
    channel.track_space = "";
    renderChannelConfigs();
    return;
  }
  // 与车位查询共用防抖即可，不再额外设置timeout，直接调用
  await doFetchTrackSpace(index, false);
}

/**
 * 手动查询车位坐标（点击按钮触发）
 */
async function manualFetchParkingSpaces(index) {
  await doFetchParkingSpaces(index, true);
}

/**
 * 手动查询识别停车区域坐标（点击按钮触发）
 */
async function manualFetchTrackSpace(index) {
  await doFetchTrackSpace(index, true);
}

/**
 * 执行查询车位坐标
 */
async function doFetchParkingSpaces(index, showAlert = true) {
  const channel = channelConfigs[index];
  if (!channel || !channel.camera_sn || !channel.camera_sn.trim()) {
    if (showAlert) {
      alert("请先填写摄像头SN");
    }
    return;
  }

  // 获取数据库连接信息
  const dbHost = document.getElementById("nvr-db-host").value.trim();
  const dbUser = document.getElementById("nvr-db-user").value.trim();
  const dbPassword = document.getElementById("nvr-db-password").value.trim();
  const dbPort = parseInt(document.getElementById("nvr-db-port").value) || 3306;
  const dbName = document.getElementById("nvr-db-name").value.trim();

  if (!dbHost || !dbUser || !dbPassword || !dbName) {
    if (showAlert) {
      alert("请先填写完整的数据库连接信息（数据库地址、账号、密码、数据库名称）");
    }
    return;
  }

  try {
    // 显示加载状态
    const channelDiv = document.querySelector(`#channel-config-list > div > div:nth-child(${index + 1})`);
    if (channelDiv) {
      const snInput = channelDiv.querySelector('input[placeholder*="GXSLqj"]');
      if (snInput) {
        snInput.style.borderColor = 'var(--accent)';
      }
    }

    // 使用新的API端点（保存前查询）
    const params = new URLSearchParams({
      camera_sn: channel.camera_sn.trim(),
      db_host: dbHost,
      db_user: dbUser,
      db_password: dbPassword,
      db_port: dbPort.toString(),
      db_name: dbName
    });

    const result = await api(`/api/nvr-configs/fetch-parking-spaces-by-sn?${params.toString()}`, {
      method: "POST"
    });
    
    if (result.parking_spaces && result.parking_spaces.length > 0) {
      channel.parking_spaces = result.parking_spaces;
      renderChannelConfigs();
      if (showAlert) {
        alert(`成功查询到 ${result.parking_spaces.length} 个车位坐标`);
      }
    } else {
      channel.parking_spaces = [];
      renderChannelConfigs();
      if (showAlert) {
        alert("未查询到车位坐标，请检查摄像头SN是否正确");
      }
    }
  } catch (e) {
    console.error("查询车位坐标失败:", e);
    channel.parking_spaces = [];
    renderChannelConfigs();
    if (showAlert) {
      alert("查询失败: " + (e.message || e));
    }
  } finally {
    // 恢复输入框样式
    const channelDiv = document.querySelector(`#channel-config-list > div > div:nth-child(${index + 1})`);
    if (channelDiv) {
      const snInput = channelDiv.querySelector('input[placeholder*="GXSLqj"]');
      if (snInput) {
        snInput.style.borderColor = '';
      }
    }
  }
}

/**
 * 执行查询识别停车区域坐标（track_space）
 */
async function doFetchTrackSpace(index, showAlert = true) {
  const channel = channelConfigs[index];
  if (!channel || !channel.camera_sn || !channel.camera_sn.trim()) {
    if (showAlert) {
      alert("请先填写摄像头SN");
    }
    return;
  }

  // 获取数据库连接信息
  const dbHost = document.getElementById("nvr-db-host").value.trim();
  const dbUser = document.getElementById("nvr-db-user").value.trim();
  const dbPassword = document.getElementById("nvr-db-password").value.trim();
  const dbPort = parseInt(document.getElementById("nvr-db-port").value) || 3306;
  const dbName = document.getElementById("nvr-db-name").value.trim();

  if (!dbHost || !dbUser || !dbPassword || !dbName) {
    if (showAlert) {
      alert("请先填写完整的数据库连接信息（数据库地址、账号、密码、数据库名称）");
    }
    return;
  }

  try {
    // 显示加载状态：高亮SN输入框边框
    const channelDiv = document.querySelector(`#channel-config-list > div > div:nth-child(${index + 1})`);
    if (channelDiv) {
      const snInput = channelDiv.querySelector('input[placeholder*="GXSLqj"]');
      if (snInput) {
        snInput.style.borderColor = 'var(--accent-2)' || 'var(--accent)';
      }
    }

    const params = new URLSearchParams({
      camera_sn: channel.camera_sn.trim(),
      db_host: dbHost,
      db_user: dbUser,
      db_password: dbPassword,
      db_port: dbPort.toString(),
      db_name: dbName
    });

    const result = await api(`/api/nvr-configs/fetch-track-space-by-sn?${params.toString()}`, {
      method: "POST"
    });

    if (result && typeof result.track_space !== "undefined" && result.track_space !== null) {
      channel.track_space = String(result.track_space);
      renderChannelConfigs();
      if (showAlert) {
        alert("成功查询到识别停车区域坐标");
      }
    } else {
      channel.track_space = "";
      renderChannelConfigs();
      if (showAlert) {
        alert("未查询到识别区域坐标，请检查摄像头SN是否正确");
      }
    }
  } catch (e) {
    console.error("查询识别区域坐标失败:", e);
    channel.track_space = "";
    renderChannelConfigs();
    if (showAlert) {
      alert("查询识别区域坐标失败: " + (e.message || e));
    }
  } finally {
    const channelDiv = document.querySelector(`#channel-config-list > div > div:nth-child(${index + 1})`);
    if (channelDiv) {
      const snInput = channelDiv.querySelector('input[placeholder*="GXSLqj"]');
      if (snInput) {
        snInput.style.borderColor = '';
      }
    }
  }
}

/**
 * 从数据库查询车位坐标（已保存的配置使用）
 */
async function fetchParkingSpaces(configId, channelId, index) {
  const channel = channelConfigs[index];
  if (!channel || !channel.camera_sn) {
    alert("请先填写摄像头SN");
    return;
  }

  if (!configId) {
    alert("请先保存NVR配置，然后再查询车位坐标");
    return;
  }

  if (!channelId) {
    alert("请先保存通道配置，然后再查询车位坐标");
    return;
  }

  try {
    const result = await api(`/api/nvr-configs/${configId}/channels/${channelId}/fetch-parking-spaces`, {
      method: "POST"
    });
    
    if (result.parking_spaces && result.parking_spaces.length > 0) {
      channel.parking_spaces = result.parking_spaces;
      renderChannelConfigs();
      alert(`成功查询到 ${result.parking_spaces.length} 个车位坐标`);
    } else {
      alert("未查询到车位坐标");
    }
  } catch (e) {
    console.error("查询车位坐标失败:", e);
    alert("查询失败: " + (e.message || e));
  }
}

/**
 * 保存NVR配置
 */
async function saveNvrConfig() {
  // 验证必填字段
  const nvrIp = document.getElementById("nvr-ip").value.trim();
  const parkingName = document.getElementById("nvr-parking-name").value.trim();
  const nvrUsername = document.getElementById("nvr-username").value.trim();
  const nvrPassword = document.getElementById("nvr-password").value.trim();
  const nvrPort = parseInt(document.getElementById("nvr-port").value) || 554;

  if (!nvrIp || !parkingName || !nvrUsername || !nvrPassword) {
    alert("请填写所有必填字段（NVR IP、车场名称、NVR账号、NVR密码）");
    return;
  }
  
  // 验证至少有一个通道配置
  if (!channelConfigs || channelConfigs.length === 0) {
    alert("请至少添加一个通道配置！\n\n点击\"+ 添加通道\"按钮来添加通道。");
    // 滚动到通道配置区域
    const channelSection = document.querySelector('#channel-config-list')?.parentElement;
    if (channelSection) {
      channelSection.scrollIntoView({ behavior: 'smooth' });
    }
    return;
  }
  
  // 验证每个通道的必填字段
  for (let i = 0; i < channelConfigs.length; i++) {
    const ch = channelConfigs[i];
    
    // 验证通道编号
    if (!ch.channel_code || !ch.channel_code.trim()) {
      alert(`通道 ${i + 1} 的所属通道（通道编号）不能为空！`);
      scrollToChannel(i);
      return;
    }
    
    // 检查通道编号重复
    const duplicate = channelConfigs.find((c, idx) => 
      idx !== i && 
      c.channel_code && 
      c.channel_code.toLowerCase() === ch.channel_code.toLowerCase()
    );
    if (duplicate) {
      alert(`通道编号 "${ch.channel_code}" 重复，请使用不同的通道编号！`);
      scrollToChannel(i);
      return;
    }
    
    // 验证摄像头IP
    if (!ch.camera_ip || !ch.camera_ip.trim()) {
      alert(`通道 ${ch.channel_code} 的摄像头IP不能为空！`);
      scrollToChannel(i);
      return;
    }
    
    // 验证摄像头名称
    if (!ch.camera_name || !ch.camera_name.trim()) {
      alert(`通道 ${ch.channel_code} 的摄像头名称不能为空！`);
      scrollToChannel(i);
      return;
    }
    
    // 验证摄像头SN
    if (!ch.camera_sn || !ch.camera_sn.trim()) {
      alert(`通道 ${ch.channel_code} 的摄像头SN不能为空！`);
      scrollToChannel(i);
      return;
    }
  }
  
  // 辅助函数：滚动到指定通道
  function scrollToChannel(index) {
    setTimeout(() => {
      const channelList = document.getElementById("channel-config-list");
      if (channelList) {
        const channelDivs = channelList.querySelectorAll('div > div');
        if (channelDivs[index]) {
          channelDivs[index].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    }, 100);
  }

  const configData = {
    nvr_ip: nvrIp,
    parking_name: parkingName,
    nvr_username: nvrUsername,
    nvr_password: nvrPassword,
    nvr_port: nvrPort,
    db_host: document.getElementById("nvr-db-host").value.trim() || null,
    db_user: document.getElementById("nvr-db-user").value.trim() || null,
    db_password: document.getElementById("nvr-db-password").value.trim() || null,
    db_port: parseInt(document.getElementById("nvr-db-port").value) || 3306,
    db_name: document.getElementById("nvr-db-name").value.trim() || null,
    channels: channelConfigs.map(ch => ({
      channel_code: ch.channel_code,
      camera_ip: ch.camera_ip || null,
      camera_name: ch.camera_name || null,
      camera_sn: ch.camera_sn || null,
      track_space: ch.track_space || null,
      parking_spaces: ch.parking_spaces || null
    }))
  };

  try {
    if (currentEditingNvrConfigId) {
      // 更新配置
      const updateData = {
        parking_name: configData.parking_name,
        nvr_username: configData.nvr_username,
        nvr_password: configData.nvr_password,
        nvr_port: configData.nvr_port,
        db_host: configData.db_host,
        db_user: configData.db_user,
        db_password: configData.db_password,
        db_port: configData.db_port,
        db_name: configData.db_name
      };
      await api(`/api/nvr-configs/${currentEditingNvrConfigId}`, {
        method: "PUT",
        body: JSON.stringify(updateData)
      });
      
      // 更新通道配置
      for (const ch of channelConfigs) {
        if (ch.id) {
          // 更新现有通道
          await api(`/api/nvr-configs/${currentEditingNvrConfigId}/channels/${ch.id}`, {
            method: "PUT",
            body: JSON.stringify({
              channel_code: ch.channel_code,
              camera_ip: ch.camera_ip || null,
              camera_name: ch.camera_name || null,
              camera_sn: ch.camera_sn || null,
              track_space: ch.track_space || null,
              parking_spaces: ch.parking_spaces || null
            })
          });
        } else {
          // 添加新通道
          await api(`/api/nvr-configs/${currentEditingNvrConfigId}/channels`, {
            method: "POST",
            body: JSON.stringify({
              channel_code: ch.channel_code,
              camera_ip: ch.camera_ip || null,
              camera_name: ch.camera_name || null,
              camera_sn: ch.camera_sn || null,
              track_space: ch.track_space || null,
              parking_spaces: ch.parking_spaces || null
            })
          });
        }
      }
      
      alert("配置更新成功");
    } else {
      // 创建新配置
      await api("/api/nvr-configs", {
        method: "POST",
        body: JSON.stringify(configData)
      });
      alert("配置保存成功");
    }
    
    // 保存成功后，隐藏表单，显示列表
    document.getElementById("nvr-config-form").style.display = "none";
    const listContainer = document.getElementById("nvr-config-list-container");
    if (listContainer) {
      listContainer.style.display = "block";
    }
    
    cancelNvrConfigForm();
    loadNvrConfigs();
  } catch (e) {
    console.error("保存NVR配置失败:", e);
    alert("保存失败: " + (e.message || e));
  }
}
