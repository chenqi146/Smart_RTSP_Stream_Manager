/**
 * 任务列表模块
 * 包含任务列表、任务详情相关的所有功能
 */

// 任务列表分页变量
let taskPage = 1;
let taskPageSize = 20;
let taskTotalPages = 1;
let taskSearchName = "";
let taskIdFromImage = null; // 从图片列表跳转时携带的 task_id

// 页面加载时检查URL参数，设置taskIdFromImage
(function() {
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("task_id")) {
    taskIdFromImage = urlParams.get("task_id");
  }
})();

// 任务配置列表分页变量
let configPage = 1;
let configPageSize = 20;
let configTotalPages = 1;

// 自动刷新定时器 - 使用window对象确保全局作用域
window.taskConfigsRefreshInterval = window.taskConfigsRefreshInterval || null;
window.taskDetailsRefreshInterval = window.taskDetailsRefreshInterval || null;

/**
 * 加载任务列表
 */
async function loadTasks(useTable=false, allowEmpty=false, dateOverride=null) {
  const dateEl = document.getElementById("task-date");
  // 这里只按任务列表自己的日期输入框来决定是否带 date 查询参数，
  // 不再从基础参数配置里的全局日期(#date)兜底，避免“没填任务日期也按某天过滤”的情况。
  const dateInput = dateOverride !== null
    ? (dateOverride || "")
    : ((dateEl ? dateEl.value : "") || "");
  const date = dateInput.trim();
  
  // 如果使用表格显示，允许日期为空（显示全部数据）
  if (useTable) {
    // 继续执行，即使日期为空
  } else {
    // 非表格模式，如果日期为空则提示
    if (!date) {
      if (!allowEmpty) alert("请先填写日期");
      return;
    }
    try {
      const res = await api(`/api/tasks/${date}`);
      const text = JSON.stringify(res, null, 2);
      document.getElementById("tasks").value = text;
    } catch (e) {
      console.error("加载任务失败:", e);
      document.getElementById("tasks").value = `错误: ${e.message || e}`;
    }
    return;
  }
  
  // load paged for table
  const nameEl = document.getElementById("task-search-name");
  const taskIdEl = document.getElementById("task-search-id");
  const ipEl = document.getElementById("task-search-ip");
  const channelEl = document.getElementById("task-search-channel");
  const statusEl = document.getElementById("task-status");
  const ipModeEl = document.getElementById("task-ip-mode");
  const channelModeEl = document.getElementById("task-channel-mode");
  const nameEqEl = document.getElementById("task-name-eq");
  const nameLikeEl = document.getElementById("task-name-like");
  const rtspEqEl = document.getElementById("task-rtsp-eq");
  const rtspLikeEl = document.getElementById("task-rtsp-like");
  const startTsGteEl = document.getElementById("task-start-ts-gte");
  const startTsLteEl = document.getElementById("task-start-ts-lte");
  const endTsGteEl = document.getElementById("task-end-ts-gte");
  const endTsLteEl = document.getElementById("task-end-ts-lte");
  const opTimeGteEl = document.getElementById("task-op-time-gte");
  const opTimeLteEl = document.getElementById("task-op-time-lte");
  const statusInEl = document.getElementById("task-status-in");
  const errorLikeEl = document.getElementById("task-error-like");

  const name = nameEl ? nameEl.value.trim() : "";
  const taskIdInputVal = taskIdEl ? taskIdEl.value.trim() : "";
  const taskId = taskIdFromImage || taskIdInputVal;
  const ip = ipEl ? ipEl.value.trim() : "";
  const channel = channelEl ? channelEl.value.trim() : "";
  const status = statusEl ? statusEl.value.trim() : "";
  const ipMode = ipModeEl ? ipModeEl.value : "eq";
  const channelMode = channelModeEl ? channelModeEl.value : "eq";
  
  // 高级搜索参数
  const nameEq = nameEqEl ? nameEqEl.value.trim() : "";
  const nameLike = nameLikeEl ? nameLikeEl.value.trim() : "";
  const rtspEq = rtspEqEl ? rtspEqEl.value.trim() : "";
  const rtspLike = rtspLikeEl ? rtspLikeEl.value.trim() : "";
  const startTsGte = startTsGteEl ? startTsGteEl.value.trim() : "";
  const startTsLte = startTsLteEl ? startTsLteEl.value.trim() : "";
  const endTsGte = endTsGteEl ? endTsGteEl.value.trim() : "";
  const endTsLte = endTsLteEl ? endTsLteEl.value.trim() : "";
  const opTimeGte = opTimeGteEl ? opTimeGteEl.value.trim() : "";
  const opTimeLte = opTimeLteEl ? opTimeLteEl.value.trim() : "";
  const statusIn = statusInEl ? statusInEl.value.trim() : "";
  const errorLike = errorLikeEl ? errorLikeEl.value.trim() : "";
  
  const pageSizeEl = document.getElementById("task-page-size");
  taskPageSize = pageSizeEl ? parseInt(pageSizeEl.value, 10) : 20;
  taskSearchName = name;
  
  // 修改API路径，date作为查询参数而不是路径参数
  let url = `/api/tasks/paged?page=${taskPage}&page_size=${taskPageSize}`;
  // 如果提供了日期，则添加到查询参数中
  if (date) {
    url += `&date=${encodeURIComponent(date)}`;
  }
  if (taskId) {
    url += `&task_id=${encodeURIComponent(taskId)}`;
  }
  
  // 基础搜索（向后兼容）
  if (name && !nameEq && !nameLike) url += `&screenshot_name=${encodeURIComponent(name)}`;
  if (ip && ipMode === "eq") url += `&ip=${encodeURIComponent(ip)}`;
  if (ip && ipMode === "like") url += `&ip__like=${encodeURIComponent(ip)}`;
  if (channel && channelMode === "eq") url += `&channel__eq=${encodeURIComponent(channel)}`;
  if (channel && channelMode === "like") url += `&channel__like=${encodeURIComponent(channel)}`;
  if (status) url += `&status=${encodeURIComponent(status)}`;
  
  // 高级搜索参数
  if (nameEq) url += `&screenshot_name__eq=${encodeURIComponent(nameEq)}`;
  if (nameLike) url += `&screenshot_name__like=${encodeURIComponent(nameLike)}`;
  if (rtspEq) url += `&rtsp_url__eq=${encodeURIComponent(rtspEq)}`;
  if (rtspLike) url += `&rtsp_url__like=${encodeURIComponent(rtspLike)}`;
  if (startTsGte) url += `&start_ts__gte=${encodeURIComponent(startTsGte)}`;
  if (startTsLte) url += `&start_ts__lte=${encodeURIComponent(startTsLte)}`;
  if (endTsGte) url += `&end_ts__gte=${encodeURIComponent(endTsGte)}`;
  if (endTsLte) url += `&end_ts__lte=${encodeURIComponent(endTsLte)}`;
  if (opTimeGte) {
    const ts = new Date(opTimeGte).toISOString();
    url += `&operation_time__gte=${encodeURIComponent(ts)}`;
  }
  if (opTimeLte) {
    const ts = new Date(opTimeLte).toISOString();
    url += `&operation_time__lte=${encodeURIComponent(ts)}`;
  }
  if (statusIn) url += `&status__in=${encodeURIComponent(statusIn)}`;
  if (errorLike) url += `&error__like=${encodeURIComponent(errorLike)}`;
  
  try {
    const paged = await api(url);
    renderTasksTable(paged);
    // 每次加载任务表格后，根据最新结果刷新通道下拉（与当前筛选条件保持一致）
    if (useTable) {
      loadTaskChannelOptions().catch(e => console.warn("加载任务后刷新通道选项失败:", e));
    }
  } catch (e) {
    console.error("加载任务列表失败:", e);
    const wrap = document.getElementById("tasks-table-wrap");
    if (wrap) {
      wrap.innerHTML = `<div class="muted">加载失败: ${e.message || e}</div>`;
    }
  }
}

/**
 * 渲染任务表格
 */
function renderTasksTable(data) {
  const wrap = document.getElementById("tasks-table-wrap");
  if (!data.items || data.items.length === 0) {
    wrap.innerHTML = '<div class="muted">暂无任务，请先生成或运行。</div>';
    const prevBtn = document.getElementById("task-prev");
    const nextBtn = document.getElementById("task-next");
    taskTotalPages = 1;
    if (prevBtn) prevBtn.disabled = true;
    if (nextBtn) nextBtn.disabled = true;
    document.getElementById("task-page-info").innerText = `第 ${data.page || 1} 页 / 共 1 页 (总计 0 条)`;
    return;
  }
  const rows = data.items.map(item => {
    const readableStart = tsToStr(item.start_ts);
    const readableEnd = tsToStr(item.end_ts);
    const rawStatus = item.status || "pending";
    const statusCn = statusMap[rawStatus] || rawStatus;
    const statusClass = getStatusClass(rawStatus);
    const fname = item.screenshot_path ? item.screenshot_path.split('/').pop() : '';
    
    // 优化状态显示：图标 + 文字 + 错误信息（如果有）
    let statusIcon = "";
    let statusHtml = "";
    const status = item.status || "pending";
    
    if (status === "completed" || status === "screenshot_taken") {
      statusIcon = "✓";
      statusHtml = '<span class="task-status-badge task-status-success" title="任务已完成，截图已生成">' +
        '<span class="status-icon">' + statusIcon + '</span>' +
        '<span class="status-text">' + statusCn + '</span>' +
        '</span>';
    } else if (status === "playing") {
      statusIcon = "⟳";
      statusHtml = '<span class="task-status-badge task-status-running" title="任务正在执行中">' +
        '<span class="status-icon status-icon-spin">' + statusIcon + '</span>' +
        '<span class="status-text">' + statusCn + '</span>' +
        '</span>';
    } else if (status === "pending") {
      statusIcon = "○";
      statusHtml = '<span class="task-status-badge task-status-pending" title="任务等待执行">' +
        '<span class="status-icon">' + statusIcon + '</span>' +
        '<span class="status-text">' + statusCn + '</span>' +
        '</span>';
    } else if (status === "failed") {
      statusIcon = "✗";
      const errorMsg = item.error ? ('<div class="status-error-detail" title="' + item.error.replace(/"/g, '&quot;') + '">' + 
        (item.error.length > 30 ? item.error.substring(0, 30) + '...' : item.error) + '</div>') : '';
      statusHtml = '<div class="task-status-wrapper">' +
        '<span class="task-status-badge task-status-failed" title="任务执行失败">' +
        '<span class="status-icon">' + statusIcon + '</span>' +
        '<span class="status-text">' + statusCn + '</span>' +
        '</span>' +
        errorMsg +
        '</div>';
    } else {
      statusHtml = '<span class="tag ' + statusClass + '">' + statusCn + '</span>';
    }
    
    // 构造截图预览图片 URL（如果有截图路径）
    let screenshotHtml = "-";
    if (item.screenshot_path) {
      let url = item.screenshot_path;
      // 相对路径统一走 /shots 静态目录
      if (!url.startsWith("http")) {
        if (!url.startsWith("/")) {
          url = `/shots/${url}`;
        }
        url = `${window.location.origin}${url}`;
      }
      screenshotHtml = `
        <img src="${url}" alt="${fname}" 
             style="max-width: 160px; max-height: 100px; border-radius:4px; cursor:pointer;"
             onclick="openTaskImage('${encodeURIComponent(url)}')"
             onerror="this.onerror=null; this.style.display='none'; this.parentElement.innerText='图片加载失败';"
        />
        <div class="muted-inline" style="max-width:180px; word-break:break-all;">${fname}</div>
      `;
    }
    const rtsp = item.rtsp_url || '';
    
    // IP 展示：优先后端 ip 字段，兜底从 RTSP 解析（必须在生成播放按钮之前定义）
    let ipText = item.ip || "";
    if (!ipText && rtsp) {
      const m = /@([0-9.]+)(?::\d+)?\//.exec(rtsp);
      ipText = m ? m[1] : "";
    }
    if (!ipText) ipText = "-";
    
    // 转义参数，避免 onclick 中的字符串问题
    const rtspEscaped = rtsp.replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const dateEscapedForPlay = (item.date || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const ipEscapedForPlay = ipText.replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const channelEscapedForPlay = (item.channel || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const startTs = item.start_ts || 0;
    const endTs = item.end_ts || 0;
    // 获取截图路径和任务ID（用于截图浏览弹窗）
    const screenshotPathEscaped = (item.screenshot_path || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const taskId = item.id || 0;
    const statusEscapedForPlay = rawStatus.replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const rtspHtml = rtsp
      ? '<a class="link" href="javascript:void(0)" onclick="openScreenshotBrowser(\''
        + dateEscapedForPlay + '\', ' + startTs + ', ' + endTs + ', \''
        + ipEscapedForPlay + '\', \'' + channelEscapedForPlay + '\', \''
        + rtspEscaped + '\', ' + taskId + ', \'' + statusEscapedForPlay
        + '\')">播放</a><br/><div class="muted-inline">' + rtsp + '</div>'
      : '';

    // 通道展示：使用通道元数据，显示为“c1 高新四路9号枪机”
    const channelLabel = getTaskChannelDisplayLabel(item.channel);
    // 获取原始通道值（用于重新运行功能）
    const channelValue = item.channel || '';
    // 转义单引号，避免 onclick 中的字符串问题
    const channelEscaped = channelValue.replace(/'/g, "\\'");
    const ipEscaped = ipText.replace(/'/g, "\\'");
    const dateEscaped = item.date.replace(/'/g, "\\'");

    const operationTime = formatOperationTime(item.operation_time);
    return `
      <tr>
        <td>${item.index}</td>
        <td>${readableStart}<br/><span class="muted-inline">${item.start_ts}</span></td>
        <td>${readableEnd}<br/><span class="muted-inline">${item.end_ts}</span></td>
        <td>${(item.parking_name ? `${ipText} (${item.parking_name})` : ipText)}</td>
        <td>${channelLabel}</td>
        <td style="min-width:120px;">${statusHtml}</td>
        <td>${screenshotHtml}</td>
        <td style="max-width:260px; word-break: break-all;">${rtspHtml}</td>
        <td>${operationTime || '-'}</td>
        <td>
          <button class="ghost" style="padding:4px 8px; margin-right:4px;" onclick="rerunTask('${dateEscaped}', '${ipEscaped}', '${channelEscaped}')">重新运行</button>
          <button class="ghost" style="padding:4px 8px; color:#ff6b6b;" onclick="deleteTask(${item.id}, '${item.date}')">删除</button>
        </td>
      </tr>
    `;
  }).join("");
  wrap.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>序号</th>
          <th>开始时间</th>
          <th>结束时间</th>
          <th>IP 地址</th>
          <th>通道</th>
          <th>状态</th>
          <th>截图文件</th>
          <th>视频流地址</th>
          <th>操作时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  const total = data.total || 0;
  const pageSize = data.page_size || taskPageSize;
  taskTotalPages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = data.page || 1;
  document.getElementById("task-page-info").innerText = `第 ${currentPage} 页 / 共 ${taskTotalPages} 页 (总计 ${total} 条)`;
  const prevBtn = document.getElementById("task-prev");
  const nextBtn = document.getElementById("task-next");
  if (prevBtn) prevBtn.disabled = currentPage <= 1;
  if (nextBtn) nextBtn.disabled = currentPage >= taskTotalPages;
}

function prevPage() {
  if (taskPage > 1) taskPage -= 1;
  loadTasks(true);
}

function nextPage() {
  if (taskPage < taskTotalPages) {
    taskPage += 1;
    loadTasks(true);
  }
}

function openTaskImage(encodedUrl) {
  try {
    const url = decodeURIComponent(encodedUrl);
    if (url) {
      window.open(url, "_blank");
    }
  } catch (e) {
    console.error("打开截图失败:", e);
  }
}

async function rerunTask(date, rtspIp, channel) {
  if (!confirm(`确定要重新运行该配置下的所有任务吗？\n日期: ${date}\nIP: ${rtspIp}\n通道: ${channel}\n\n这将重新执行所有匹配任务的截图操作并更新任务状态。`)) {
    return;
  }
  
  try {
    const body = { date: date };
    if (rtspIp && rtspIp.trim() && rtspIp !== '-') {
      body.rtsp_ip = rtspIp.trim();
    }
    if (channel && channel.trim()) {
      body.channel = channel.trim();
    }
    const res = await api(`/api/tasks/configs/rerun`, { 
      method: "POST",
      body: JSON.stringify(body)
    });
    alert(res.message || `已加入重新运行队列，共 ${res.count} 个任务`);
    setTimeout(() => {
      loadTasks(true);
    }, 1000);
  } catch (e) {
    const errorMsg = e.message || e.toString() || JSON.stringify(e);
    console.error("重新运行失败:", e);
    alert("重新运行失败：" + errorMsg);
  }
}

async function deleteTask(taskId, date) {
  if (!confirm(`确定要删除该任务吗？\n任务ID: ${taskId}\n\n警告：删除后将同时删除：\n- 该任务记录\n- 关联的截图记录\n- 关联的OCR结果\n\n此操作不可恢复！`)) {
    return;
  }
  
  try {
    const res = await api(`/api/tasks/${taskId}`, { method: "DELETE" });
    alert(res.message || "任务已删除");
    setTimeout(() => {
      searchTasks();
    }, 500);
  } catch (e) {
    console.error("删除任务失败:", e);
    alert("删除失败：" + (e.message || e));
  }
}

/**
 * 加载任务配置列表
 */
async function loadTaskConfigs() {
  const dateEl = document.getElementById("config-date");
  const ipEl = document.getElementById("config-ip");
  const channelEl = document.getElementById("config-channel");
  const statusEl = document.getElementById("config-status");
  const ipModeEl = document.getElementById("config-ip-mode");
  const channelModeEl = document.getElementById("config-channel-mode");
  
  const date = dateEl ? dateEl.value.trim() : "";
  const ip = ipEl ? ipEl.value.trim() : "";
  const channel = channelEl ? channelEl.value.trim() : "";
  const status = statusEl ? statusEl.value.trim() : "";
  const ipMode = ipModeEl ? ipModeEl.value : "eq";
  const channelMode = channelModeEl ? channelModeEl.value : "eq";
  
  // 如果任务配置的高级搜索面板当前是收起状态，则自动清空高级搜索条件，
  // 避免历史高级条件在用户未展开时继续生效。
  const advEl = document.getElementById("config-advanced-search");
  if (advEl) {
    const visible = advEl.style.display !== "none" && window.getComputedStyle(advEl).display !== "none";
    if (!visible) {
      const dateLikeEl = document.getElementById("config-date-like");
      const rtspLikeEl = document.getElementById("config-rtsp-like");
      const startTsGteEl3 = document.getElementById("config-start-ts-gte");
      const startTsLteEl3 = document.getElementById("config-start-ts-lte");
      const endTsGteEl3 = document.getElementById("config-end-ts-gte");
      const endTsLteEl3 = document.getElementById("config-end-ts-lte");
      const intervalGteEl = document.getElementById("config-interval-gte");
      const intervalLteEl = document.getElementById("config-interval-lte");
      const opTimeGteEl2 = document.getElementById("config-op-time-gte");
      const opTimeLteEl2 = document.getElementById("config-op-time-lte");
      const statusInEl2 = document.getElementById("config-status-in");

      if (dateLikeEl) dateLikeEl.value = "";
      if (rtspLikeEl) rtspLikeEl.value = "";
      if (startTsGteEl3) startTsGteEl3.value = "";
      if (startTsLteEl3) startTsLteEl3.value = "";
      if (endTsGteEl3) endTsGteEl3.value = "";
      if (endTsLteEl3) endTsLteEl3.value = "";
      if (intervalGteEl) intervalGteEl.value = "";
      if (intervalLteEl) intervalLteEl.value = "";
      if (opTimeGteEl2) opTimeGteEl2.value = "";
      if (opTimeLteEl2) opTimeLteEl2.value = "";
      if (statusInEl2) statusInEl2.value = "";
    }
  }
  
  // 高级搜索参数
  const dateLikeEl = document.getElementById("config-date-like");
  const rtspLikeEl = document.getElementById("config-rtsp-like");
  const startTsGteEl3 = document.getElementById("config-start-ts-gte");
  const startTsLteEl3 = document.getElementById("config-start-ts-lte");
  const endTsGteEl3 = document.getElementById("config-end-ts-gte");
  const endTsLteEl3 = document.getElementById("config-end-ts-lte");
  const intervalGteEl = document.getElementById("config-interval-gte");
  const intervalLteEl = document.getElementById("config-interval-lte");
  const opTimeGteEl2 = document.getElementById("config-op-time-gte");
  const opTimeLteEl2 = document.getElementById("config-op-time-lte");
  const statusInEl2 = document.getElementById("config-status-in");

  const dateLike = dateLikeEl ? dateLikeEl.value.trim() : "";
  const rtspLike = rtspLikeEl ? rtspLikeEl.value.trim() : "";
  const startTsGte = startTsGteEl3 ? startTsGteEl3.value.trim() : "";
  const startTsLte = startTsLteEl3 ? startTsLteEl3.value.trim() : "";
  const endTsGte = endTsGteEl3 ? endTsGteEl3.value.trim() : "";
  const endTsLte = endTsLteEl3 ? endTsLteEl3.value.trim() : "";
  const intervalGte = intervalGteEl ? intervalGteEl.value.trim() : "";
  const intervalLte = intervalLteEl ? intervalLteEl.value.trim() : "";
  const opTimeGte = opTimeGteEl2 ? opTimeGteEl2.value.trim() : "";
  const opTimeLte = opTimeLteEl2 ? opTimeLteEl2.value.trim() : "";
  const statusIn = statusInEl2 ? statusInEl2.value.trim() : "";
  
  const wrap = document.getElementById("task-configs-table-wrap");
  const pager = document.getElementById("config-pager");
  if (!wrap) return;
  
  wrap.innerHTML = '<div class="muted">正在加载...</div>';
  if (pager) pager.style.display = "none";
  
  try {
    const pageSizeEl = document.getElementById("config-page-size");
    configPageSize = pageSizeEl ? parseInt(pageSizeEl.value, 10) : 20;
    
    let url = `/api/tasks/configs?page=${configPage}&page_size=${configPageSize}`;
    
    // 基础搜索
    if (date) url += `&date=${encodeURIComponent(date)}`;
    if (ip && ipMode === "eq") url += `&ip=${encodeURIComponent(ip)}`;
    if (ip && ipMode === "like") url += `&ip__like=${encodeURIComponent(ip)}`;
    if (channel && channelMode === "eq") url += `&channel=${encodeURIComponent(channel)}`;
    if (channel && channelMode === "like") url += `&channel__like=${encodeURIComponent(channel)}`;
    if (status) url += `&status=${encodeURIComponent(status)}`;
    
    // 高级搜索参数
    if (dateLike) url += `&date__like=${encodeURIComponent(dateLike)}`;
    if (rtspLike) url += `&rtsp_base__like=${encodeURIComponent(rtspLike)}`;
    if (startTsGte) url += `&start_ts__gte=${encodeURIComponent(startTsGte)}`;
    if (startTsLte) url += `&start_ts__lte=${encodeURIComponent(startTsLte)}`;
    if (endTsGte) url += `&end_ts__gte=${encodeURIComponent(endTsGte)}`;
    if (endTsLte) url += `&end_ts__lte=${encodeURIComponent(endTsLte)}`;
    if (intervalGte) url += `&interval_minutes__gte=${encodeURIComponent(intervalGte)}`;
    if (intervalLte) url += `&interval_minutes__lte=${encodeURIComponent(intervalLte)}`;
    if (opTimeGte) {
      const ts = new Date(opTimeGte).toISOString();
      url += `&operation_time__gte=${encodeURIComponent(ts)}`;
    }
    if (opTimeLte) {
      const ts = new Date(opTimeLte).toISOString();
      url += `&operation_time__lte=${encodeURIComponent(ts)}`;
    }
    if (statusIn) url += `&status__in=${encodeURIComponent(statusIn)}`;
    
    const res = await api(url);
    
    if (!res || !res.items || res.items.length === 0) {
      wrap.innerHTML = '<div class="muted">暂无任务配置，请先在基础参数配置中生成任务。</div>';
      if (pager) pager.style.display = "none";
      return;
    }
    
    const rows = res.items.map(item => {
      const startTime = tsToStr(item.start_ts);
      const endTime = tsToStr(item.end_ts);
      const statusClass = item.status;
      
      const rtspMatch = item.rtsp_base && item.rtsp_base.match(/@([\d.]+)/);
      const rtspIp = rtspMatch && rtspMatch[1] ? rtspMatch[1] : "";
      const ip = item.ip || rtspIp || "";
      // IP显示：如果有停车场名称，同时显示
      const parkingName = item.parking_name || "";
      const ipDisplay = parkingName ? `${ip || '-'} (${parkingName})` : (ip || '-');
      const operationTime = formatOperationTime(item.operation_time);
      return `
        <tr>
          <td style="cursor:pointer;" onclick="jumpToTaskDetail('${item.date}', '${ip}', '${item.channel}')">${item.index}</td>
          <td style="cursor:pointer;" onclick="jumpToTaskDetail('${item.date}', '${ip}', '${item.channel}')">${startTime}</td>
          <td style="cursor:pointer;" onclick="jumpToTaskDetail('${item.date}', '${ip}', '${item.channel}')">${endTime}</td>
          <td style="cursor:pointer; max-width:250px; word-break: break-all;" onclick="jumpToTaskDetail('${item.date}', '${ip}', '${item.channel}')">${item.rtsp_base}</td>
          <td style="cursor:pointer;" onclick="jumpToTaskDetail('${item.date}', '${ip}', '${item.channel}')">${ipDisplay}</td>
          <td style="cursor:pointer;" onclick="jumpToTaskDetail('${item.date}', '${ip}', '${item.channel}')">${item.channel}</td>
          <td style="cursor:pointer;" onclick="jumpToTaskDetail('${item.date}', '${ip}', '${item.channel}')">${item.interval_minutes}</td>
          <td style="cursor:pointer;" onclick="jumpToTaskDetail('${item.date}', '${ip}', '${item.channel}')"><span class="tag ${statusClass}">${item.status}</span><br/><span class="muted-inline">${item.status_detail}</span></td>
          <td style="cursor:pointer;" onclick="jumpToTaskDetail('${item.date}', '${ip}', '${item.channel}')">${operationTime || '-'}</td>
          <td onclick="event.stopPropagation();">
            <button class="ghost" style="padding:4px 8px; margin-right:4px;" onclick="rerunConfigTasks('${item.date}', '${ip}', '${item.channel}')">重新运行</button>
            <button class="ghost" style="padding:4px 8px; color:#ff6b6b;" onclick="deleteConfigTasks('${item.date}', '${ip}', '${item.channel}')">删除</button>
          </td>
        </tr>
      `;
    }).join("");
    
    wrap.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>序号</th>
            <th>开始时间</th>
            <th>结束时间</th>
            <th>RTSP 基础地址</th>
            <th>IP 地址</th>
            <th>通道</th>
            <th>间隔(分钟)</th>
            <th>任务状态</th>
            <th>操作时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
    
    if (pager) {
      const total = res.total || 0;
      const pageSize = res.page_size || configPageSize;
      configTotalPages = Math.max(1, Math.ceil(total / pageSize));
      const currentPage = res.page || 1;
      document.getElementById("config-page-info").innerText = `第 ${currentPage} 页 / 共 ${configTotalPages} 页 (总计 ${total} 条)`;
      const prevBtn = document.getElementById("config-prev");
      const nextBtn = document.getElementById("config-next");
      if (prevBtn) prevBtn.disabled = currentPage <= 1;
      if (nextBtn) nextBtn.disabled = currentPage >= configTotalPages;
      pager.style.display = "flex";
      
      // 每次加载配置列表后，根据最新结果刷新通道下拉（与当前筛选条件保持一致）
      loadConfigChannelOptions().catch(e => console.warn("加载配置后刷新通道选项失败:", e));
    }
  } catch (e) {
    wrap.innerHTML = `<div class="muted">加载失败：${e.message || e}</div>`;
    if (pager) pager.style.display = "none";
  }
}

function prevConfigPage() {
  if (configPage > 1) {
    configPage -= 1;
    loadTaskConfigs();
  }
}

function nextConfigPage() {
  if (configPage < configTotalPages) {
    configPage += 1;
    loadTaskConfigs();
  }
}

function jumpToTaskDetail(date, rtspIp, channel) {
  switchView("tasks");
  setTimeout(() => {
    const dateInput = document.getElementById("task-date");
    const ipInput = document.getElementById("task-search-ip");
    const channelInput = document.getElementById("task-search-channel");
    if (dateInput) dateInput.value = date;
    if (ipInput && rtspIp) ipInput.value = rtspIp;
    if (channelInput && channel) channelInput.value = channel;
    searchTasks();
  }, 100);
}

async function rerunConfigTasks(date, rtspIp, channel) {
  if (!confirm(`确定要重新运行该配置下的所有任务吗？\n日期: ${date}\nIP: ${rtspIp}\n通道: ${channel}\n\n这将重新执行所有匹配任务的截图操作并更新任务状态。`)) {
    return;
  }
  
  try {
    const body = { date: date };
    if (rtspIp && rtspIp.trim()) {
      body.rtsp_ip = rtspIp.trim();
    }
    if (channel && channel.trim()) {
      body.channel = channel.trim();
    }
    const res = await api(`/api/tasks/configs/rerun`, { 
      method: "POST",
      body: JSON.stringify(body)
    });
    alert(res.message || `已加入重新运行队列，共 ${res.count} 个任务`);
    setTimeout(() => {
      loadTaskConfigs();
    }, 1000);
  } catch (e) {
    const errorMsg = e.message || e.toString() || JSON.stringify(e);
    console.error("重新运行失败:", e);
    alert("重新运行失败：" + errorMsg);
  }
}

async function deleteConfigTasks(date, rtspIp, channel) {
  if (!confirm(`确定要删除该配置下的所有任务吗？\n日期: ${date}\nIP: ${rtspIp}\n通道: ${channel}\n\n警告：删除后将同时删除：\n- 所有匹配的任务记录\n- 关联的截图记录\n- 关联的OCR结果\n- 截图物理文件\n\n此操作不可恢复！`)) {
    return;
  }
  
  try {
    const params = new URLSearchParams({
      date: date,
      rtsp_ip: rtspIp,
      channel: channel
    });
    const res = await api(`/api/tasks/configs?${params.toString()}`, { method: "DELETE" });
    alert(res.message || `已删除 ${res.count} 个任务及其关联数据`);
    setTimeout(() => {
      loadTaskConfigs();
    }, 500);
  } catch (e) {
    alert("删除失败：" + (e.message || e));
  }
}

function searchTasks() {
  const taskDateEl = document.getElementById("task-date");
  // 这里只使用任务列表自己的日期输入框，不再从基础参数配置的全局日期(#date)兜底，
  // 避免“未在任务列表填写日期却按某天过滤”的问题。
  const date = (taskDateEl ? taskDateEl.value : "").trim();
  // 如果任务列表的高级搜索面板当前是收起状态，则自动清空高级搜索条件，
  // 避免历史高级条件“隐身生效”导致搜索结果不符合预期。
  const advEl = document.getElementById("tasks-advanced-search");
  if (advEl) {
    const visible = advEl.style.display !== "none" && window.getComputedStyle(advEl).display !== "none";
    if (!visible) {
      const nameEqEl = document.getElementById("task-name-eq");
      const nameLikeEl = document.getElementById("task-name-like");
      const rtspEqEl = document.getElementById("task-rtsp-eq");
      const rtspLikeEl = document.getElementById("task-rtsp-like");
      const startTsGteEl = document.getElementById("task-start-ts-gte");
      const startTsLteEl = document.getElementById("task-start-ts-lte");
      const endTsGteEl = document.getElementById("task-end-ts-gte");
      const endTsLteEl = document.getElementById("task-end-ts-lte");
      const opTimeGteEl = document.getElementById("task-op-time-gte");
      const opTimeLteEl = document.getElementById("task-op-time-lte");
      const statusInEl = document.getElementById("task-status-in");
      const errorLikeEl = document.getElementById("task-error-like");

      if (nameEqEl) nameEqEl.value = "";
      if (nameLikeEl) nameLikeEl.value = "";
      if (rtspEqEl) rtspEqEl.value = "";
      if (rtspLikeEl) rtspLikeEl.value = "";
      if (startTsGteEl) startTsGteEl.value = "";
      if (startTsLteEl) startTsLteEl.value = "";
      if (endTsGteEl) endTsGteEl.value = "";
      if (endTsLteEl) endTsLteEl.value = "";
      if (opTimeGteEl) opTimeGteEl.value = "";
      if (opTimeLteEl) opTimeLteEl.value = "";
      if (statusInEl) statusInEl.value = "";
      if (errorLikeEl) errorLikeEl.value = "";
    }
  }
  taskPage = 1;
  loadTasks(true, true, date || null).then(() => {
    // 任务列表更新后，重新根据当前结果刷新通道下拉
    loadTaskChannelOptions().catch(e => console.warn("搜索后刷新任务通道选项失败:", e));
  }).catch(() => {});
}

function resetTaskSearch() {
  document.getElementById("task-date").value = "";
  document.getElementById("task-search-name").value = "";
  const taskIdInput = document.getElementById("task-search-id");
  if (taskIdInput) taskIdInput.value = "";
  taskIdFromImage = null;
  document.getElementById("task-search-ip").value = "";
  document.getElementById("task-search-channel").value = "";
  document.getElementById("task-status").value = "";
  document.getElementById("task-name-eq").value = "";
  document.getElementById("task-name-like").value = "";
  document.getElementById("task-rtsp-eq").value = "";
  document.getElementById("task-rtsp-like").value = "";
  document.getElementById("task-start-ts-gte").value = "";
  document.getElementById("task-start-ts-lte").value = "";
  document.getElementById("task-end-ts-gte").value = "";
  document.getElementById("task-end-ts-lte").value = "";
  document.getElementById("task-op-time-gte").value = "";
  document.getElementById("task-op-time-lte").value = "";
  document.getElementById("task-status-in").value = "";
  document.getElementById("task-error-like").value = "";
  document.getElementById("task-ip-mode").value = "eq";
  document.getElementById("task-channel-mode").value = "eq";
  taskPage = 1;
  searchTasks();
}

function resetConfigSearch() {
  document.getElementById("config-date").value = "";
  document.getElementById("config-ip").value = "";
  document.getElementById("config-channel").value = "";
  document.getElementById("config-status").value = "";
  document.getElementById("config-date-like").value = "";
  document.getElementById("config-rtsp-like").value = "";
  document.getElementById("config-start-ts-gte").value = "";
  document.getElementById("config-start-ts-lte").value = "";
  document.getElementById("config-end-ts-gte").value = "";
  document.getElementById("config-end-ts-lte").value = "";
  document.getElementById("config-interval-gte").value = "";
  document.getElementById("config-interval-lte").value = "";
  document.getElementById("config-op-time-gte").value = "";
  document.getElementById("config-op-time-lte").value = "";
  document.getElementById("config-status-in").value = "";
  document.getElementById("config-ip-mode").value = "eq";
  document.getElementById("config-channel-mode").value = "eq";
  configPage = 1;
  loadTaskConfigs();
}

function toggleAdvancedSearch(view) {
  const el = document.getElementById(`${view}-advanced-search`);
  if (el) {
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
    const btn = event.target;
    if (btn) {
      btn.textContent = el.style.display === 'none' ? '高级搜索 ▼' : '高级搜索 ▲';
    }
  }
}

/**
 * 加载任务日期选项
 */
async function loadTaskDateOptions() {
  try {
    const res = await api("/api/tasks/available_dates");
    const dates = Array.isArray(res?.dates) ? res.dates : res;
    const datalist = document.getElementById("task-date-options");
    if (datalist && dates) {
      datalist.innerHTML = dates.map(d => `<option value="${d}">`).join("");
    }
  } catch (e) {
    console.warn("加载任务日期选项失败:", e);
  }
}

/**
 * 加载任务IP选项
 */
async function loadTaskIpOptions() {
  try {
    const res = await api("/api/tasks/available_ips");
    const ips = Array.isArray(res?.ips)
      ? res.ips.map(x => (typeof x === "string" ? x : x.ip)).filter(Boolean)
      : (Array.isArray(res) ? res : []);
    const select = document.getElementById("task-search-ip");
    if (select && ips) {
      const currentValue = select.value;
      select.innerHTML = '<option value="">全部IP</option>' + ips.map(ip => `<option value="${ip}">${ip}</option>`).join("");
      if (currentValue) select.value = currentValue;
    }
  } catch (e) {
    console.warn("加载任务IP选项失败:", e);
  }
}

// 通道元数据缓存（用于在下拉中显示 “c1 高新四路9号枪机”）
let taskChannelMetaLoaded = false;
let taskChannelMetaByCode = new Map(); // key: 通道code小写 -> label

async function ensureTaskChannelMetaLoaded() {
  if (taskChannelMetaLoaded) return;
  try {
    const channels = await api("/api/channels");
    if (Array.isArray(channels)) {
      channels.forEach(ch => {
        const code = (ch.channel_code || "").trim().toLowerCase();
        if (!code) return;
        const labelText = ch.camera_name || ch.camera_ip || ch.nvr_ip || code.toUpperCase();
        const label = `${code.toUpperCase()} ${labelText}`;
        if (!taskChannelMetaByCode.has(code)) {
          taskChannelMetaByCode.set(code, label);
        }
      });
    }
  } catch (e) {
    console.warn("加载任务通道元数据失败:", e);
  } finally {
    taskChannelMetaLoaded = true;
  }
}

function getTaskChannelDisplayLabel(code) {
  const norm = (code || "").trim().toLowerCase();
  if (!norm) return "";
  return taskChannelMetaByCode.get(norm) || norm.toUpperCase();
}

/**
 * 加载任务通道选项
 */
async function loadTaskChannelOptions() {
  try {
    const ipSelect = document.getElementById("task-search-ip");
    const currentIp = ipSelect ? (ipSelect.value || "").trim() : "";
    const dateEl = document.getElementById("task-date");
    const baseDateEl3 = document.getElementById("date");
    const date = ((dateEl ? dateEl.value : "") || (baseDateEl3 ? baseDateEl3.value : "") || "").trim();

    let realChannels = new Set();

    // 如果用户已经选择了日期或 IP，从当前搜索结果中提取“纯通道编码”（c1/c2/c3...）
    if (date || currentIp) {
      try {
        const params = new URLSearchParams();
        if (date) params.append("date", date);
        if (currentIp) params.append("ip", currentIp);
        // 为了获取所有通道，请求一个较大的 page_size
        params.append("page_size", "1000");
        const res = await api(`/api/tasks/paged?${params.toString()}`);
        if (res && Array.isArray(res.items)) {
          res.items.forEach(it => {
            if (it.channel) {
              const code = String(it.channel).trim().toLowerCase();
              if (code) realChannels.add(code);
            }
          });
        }
      } catch (e) {
        console.warn("根据当前IP/日期推导任务通道失败:", e);
      }
    }

    // 如果没有筛选条件，或者从搜索结果中提取的通道为空，回退到“所有可用通道编码”
    if (realChannels.size === 0) {
      try {
        const res = await api("/api/tasks/available_channels");
        // 后端返回格式: {"channels": [{"channel": "c1"}, {"channel": "c2"}, ...]}
        if (res && res.channels && Array.isArray(res.channels)) {
          res.channels.forEach(ch => {
            const code = String(ch.channel || ch || "").trim().toLowerCase();
            if (code) realChannels.add(code);
          });
        } else if (Array.isArray(res)) {
          // 兼容直接返回数组的情况
          res.forEach(ch => {
            const code = String(ch.channel || ch || "").trim().toLowerCase();
            if (code) realChannels.add(code);
          });
        }
      } catch (e) {
        console.warn("获取所有可用通道失败:", e);
      }
    }

    const select = document.getElementById("task-search-channel");
    if (select) {
      const currentValue = select.value;

      if (realChannels.size === 0) {
        // 如果仍然没有任何通道，只显示“全部通道”
        select.innerHTML = '<option value="">全部通道</option>';
        return;
      }

      const channelsArray = Array.from(realChannels).sort();
      // 下拉框里只显示 c1/c2/c3/c4，value 也是纯通道编码
      const optionsHtml = channelsArray.map(code => {
        const upper = (code || "").toUpperCase();
        return `<option value="${code}">${upper}</option>`;
      }).join("");

      select.innerHTML = '<option value="">全部通道</option>' + optionsHtml;
      if (currentValue) select.value = currentValue;
    }
  } catch (e) {
    console.warn("加载任务通道选项失败:", e);
  }
}

/**
 * 加载配置日期选项
 */
async function loadConfigDateOptions() {
  try {
    const res = await api("/api/tasks/available_dates");
    const dates = Array.isArray(res?.dates) ? res.dates : res;
    const datalist = document.getElementById("config-date-options");
    if (datalist && dates) {
      datalist.innerHTML = dates.map(d => `<option value="${d}">`).join("");
    }
  } catch (e) {
    console.warn("加载配置日期选项失败:", e);
  }
}

/**
 * 加载配置IP选项
 */
async function loadConfigIpOptions() {
  try {
    const res = await api("/api/tasks/available_ips");
    const ips = Array.isArray(res?.ips)
      ? res.ips.map(x => (typeof x === "string" ? x : x.ip)).filter(Boolean)
      : (Array.isArray(res) ? res : []);
    const select = document.getElementById("config-ip");
    if (select && ips) {
      const currentValue = select.value;
      select.innerHTML = '<option value="">全部IP</option>' + ips.map(ip => `<option value="${ip}">${ip}</option>`).join("");
      if (currentValue) select.value = currentValue;
    }
  } catch (e) {
    console.warn("加载配置IP选项失败:", e);
  }
}

/**
 * 加载配置通道选项
 */
async function loadConfigChannelOptions() {
  try {
    const ipSelect = document.getElementById("config-ip");
    const currentIp = ipSelect ? (ipSelect.value || "").trim() : "";
    const dateEl = document.getElementById("config-date");
    const baseDateEl3 = document.getElementById("date");
    const date = ((dateEl ? dateEl.value : "") || (baseDateEl3 ? baseDateEl3.value : "") || "").trim();

    let realChannels = new Set();

    // 如果用户已经选择了日期或 IP，从当前搜索结果中提取“纯通道编码”（c1/c2/c3...）
    if (date || currentIp) {
      try {
        const params = new URLSearchParams();
        if (date) params.append("date", date);
        if (currentIp) params.append("ip", currentIp);
        params.append("page_size", "1000");
        const res = await api(`/api/tasks/configs?${params.toString()}`);
        if (res && Array.isArray(res.items)) {
          res.items.forEach(it => {
            if (it.channel) {
              const code = String(it.channel).trim().toLowerCase();
              if (code) realChannels.add(code);
            }
          });
        }
      } catch (e) {
        console.warn("根据当前IP/日期推导配置通道失败:", e);
      }
    }

    // 如果没有筛选条件，或者从搜索结果中提取的通道为空，回退到“所有可用通道编码”
    if (realChannels.size === 0) {
      try {
        const res = await api("/api/tasks/available_channels");
        // 后端返回格式: {"channels": [{"channel": "c1"}, {"channel": "c2"}, ...]}
        if (res && res.channels && Array.isArray(res.channels)) {
          res.channels.forEach(ch => {
            const code = String(ch.channel || ch || "").trim().toLowerCase();
            if (code) realChannels.add(code);
          });
        } else if (Array.isArray(res)) {
          // 兼容旧格式
          res.forEach(ch => {
            const code = String(ch.channel || ch || "").trim().toLowerCase();
            if (code) realChannels.add(code);
          });
        }
      } catch (e) {
        console.warn("获取所有可用通道失败:", e);
      }
    }

    const select = document.getElementById("config-channel");
    if (select) {
      const currentValue = select.value;

      if (realChannels.size === 0) {
        select.innerHTML = '<option value="">全部通道</option>';
        return;
      }

      const channelsArray = Array.from(realChannels).sort();
      // 下拉框里只显示 c1/c2/c3/c4，value 也是纯通道编码
      const optionsHtml = channelsArray.map(code => {
        const upper = (code || "").toUpperCase();
        return `<option value="${code}">${upper}</option>`;
      }).join("");

      select.innerHTML = '<option value="">全部通道</option>' + optionsHtml;
      if (currentValue) select.value = currentValue;
    }
  } catch (e) {
    console.warn("加载配置通道选项失败:", e);
  }
}

// ==================== 截图浏览功能 ====================

let screenshotBrowserData = {
  date: '',
  start_ts: 0,
  end_ts: 0,
  ip: '',
  channel: '',
  base_rtsp: '',
  minuteSegments: [],
  currentIndex: 0
};

/**
 * 打开截图浏览弹窗
 * @param {string} date - 日期
 * @param {number} start_ts - 开始时间戳
 * @param {number} end_ts - 结束时间戳
 * @param {string} ip - IP地址
 * @param {string} channel - 通道（可能包含描述性文本）
 * @param {string} rtspUrl - RTSP URL
 * @param {number} task_id - 任务ID（用于获取每分钟截图）
 * @param {string} task_status - 任务状态（目前仅用于调试/展示，可选）
 */
async function openScreenshotBrowser(date, start_ts, end_ts, ip, channel, rtspUrl, task_id, task_status) {
  try {
    // 解析RTSP URL获取基础信息
    const parsed = parseRtspUrl(rtspUrl);
    if (!parsed) {
      alert("无法解析RTSP URL");
      return;
    }

    // 从channel参数中提取纯通道代码（如从"C2 高新四路7号枪机"提取"c2"）
    // 或者从RTSP URL中提取通道代码
    let channelCode = parsed.channel || channel;
    // 如果channel包含描述性文本，尝试提取通道代码
    if (channel && channel.length > 2) {
      const channelMatch = channel.match(/\b([cC]\d+)\b/);
      if (channelMatch) {
        channelCode = channelMatch[1].toLowerCase();
      }
    }
    // 确保channelCode是小写的
    if (channelCode) {
      channelCode = channelCode.toLowerCase();
    }

    // 生成分钟分段
    const minuteSegments = generateMinuteSegments(
      parsed.base,
      parsed.channel,
      start_ts,
      end_ts,
      parsed.suffix
    );

    // 获取每分钟截图信息
    let minuteScreenshots = [];
    if (task_id) {
      try {
        console.log(`[DEBUG] 获取每分钟截图: task_id=${task_id}`);
        const response = await fetch(`/api/tasks/${task_id}/minute-screenshots`);
        if (response.ok) {
          const data = await response.json();
          minuteScreenshots = data.minute_screenshots || [];
          console.log(`[DEBUG] API返回的每分钟截图数量: ${minuteScreenshots.length}`, minuteScreenshots);
          // 将截图路径信息合并到分钟分段中（使用minute_index匹配）
          const minuteScreenshotMap = {};
          minuteScreenshots.forEach(ms => {
            minuteScreenshotMap[ms.minute_index] = ms;
          });
          minuteSegments.forEach((segment, index) => {
            const ms = minuteScreenshotMap[index];
            if (ms) {
              segment.file_path = ms.file_path;
              segment.image_url = ms.image_url;
              segment.status = ms.status;
              segment.rtsp_url = ms.rtsp_url;
              console.log(`[DEBUG] 合并截图信息: index=${index}, file_path=${ms.file_path}, image_url=${ms.image_url}, status=${ms.status}`);
            } else {
              console.log(`[DEBUG] 未找到第${index}分钟的截图信息`);
            }
          });
        } else {
          const errorText = await response.text();
          console.warn(`获取每分钟截图失败: HTTP ${response.status}`, errorText);
        }
      } catch (e) {
        console.warn("获取每分钟截图失败:", e);
      }
    }

    // 保存数据
    screenshotBrowserData = {
      date: date,
      start_ts: start_ts,
      end_ts: end_ts,
      ip: ip,
      channel: channelCode, // 使用提取的纯通道代码
      base_rtsp: parsed.base,
      minuteSegments: minuteSegments,
      currentIndex: 0,
      task_id: task_id || null
    };

    // 显示弹窗
    const modal = document.getElementById("screenshot-browser-modal");
    if (modal) {
      modal.classList.add("open");
      document.getElementById("screenshot-browser-title").textContent = 
        `截图浏览 - ${date} ${ip} ${channel}`;
      
      // 添加键盘事件监听（左右箭头键切换）
      document.addEventListener('keydown', handleScreenshotBrowserKeydown);
      
      // 渲染右侧分钟列表
      renderScreenshotMinuteList(minuteSegments, 0);
      
      // 等待一下确保数据合并完成，然后加载第一张截图（不播放视频）
      await new Promise(resolve => setTimeout(resolve, 100));
      await loadScreenshot(0);
    }
  } catch (e) {
    console.error("打开截图浏览失败:", e);
    alert("打开截图浏览失败：" + (e.message || e));
  }
}

/**
 * 关闭截图浏览弹窗
 */
function closeScreenshotBrowser() {
  const modal = document.getElementById("screenshot-browser-modal");
  if (modal) {
    modal.classList.remove("open");
  }
  // 移除键盘事件监听
  document.removeEventListener('keydown', handleScreenshotBrowserKeydown);
  // 清理数据
  screenshotBrowserData = {
    date: '',
    start_ts: 0,
    end_ts: 0,
    ip: '',
    channel: '',
    base_rtsp: '',
    minuteSegments: [],
    currentIndex: 0
  };
}

/**
 * 处理截图浏览弹窗的键盘事件
 */
function handleScreenshotBrowserKeydown(event) {
  const modal = document.getElementById("screenshot-browser-modal");
  if (!modal || !modal.classList.contains("open")) {
    return;
  }
  
  // 左右箭头键切换截图
  if (event.key === 'ArrowLeft') {
    event.preventDefault();
    navigateScreenshot(-1);
  } else if (event.key === 'ArrowRight') {
    event.preventDefault();
    navigateScreenshot(1);
  } else if (event.key === 'Escape') {
    event.preventDefault();
    closeScreenshotBrowser();
  }
}

/**
 * 加载指定索引的截图
 */
async function loadScreenshot(index) {
  if (!screenshotBrowserData.minuteSegments || screenshotBrowserData.minuteSegments.length === 0) {
    return;
  }

  if (index < 0 || index >= screenshotBrowserData.minuteSegments.length) {
    return;
  }

  screenshotBrowserData.currentIndex = index;
  const segment = screenshotBrowserData.minuteSegments[index];

  // 显示加载状态
  const loadingEl = document.getElementById("screenshot-loading");
  const imgEl = document.getElementById("screenshot-display-img");
  const infoEl = document.getElementById("screenshot-info");
  const counterEl = document.getElementById("screenshot-counter");

  if (loadingEl) loadingEl.style.display = "block";
  if (imgEl) imgEl.style.display = "none";

  // 生成截图路径：优先使用接口返回的 image_url（仅当 status=completed 且文件存在时后端才返回，可避免 404）
  let screenshotUrl = "";
  if (segment.image_url) {
    screenshotUrl = segment.image_url;
    console.log(`[DEBUG] 使用每分钟截图 image_url: ${screenshotUrl}, status: ${segment.status}`);
  } else if (segment.file_path && segment.status === "completed") {
    const path = segment.file_path;
    if (path.startsWith("/")) {
      screenshotUrl = path;
    } else if (path.startsWith("http")) {
      screenshotUrl = path;
    } else {
      screenshotUrl = `/shots/${path}`;
    }
    console.log(`[DEBUG] 使用每分钟截图路径: ${screenshotUrl}, status: ${segment.status}`);
  } else if (segment.status === "pending" || segment.status === "processing") {
    screenshotUrl = "";
    console.log(`[DEBUG] 该分钟截图未就绪，不请求图片: status=${segment.status}`);
  } else {
    // 兜底：尝试生成路径（可能 404）
    const ipSuffix = screenshotBrowserData.ip.replace(/\./g, "_");
    const channelSuffix = screenshotBrowserData.channel || "c";
    const screenshotPath = `${screenshotBrowserData.date}/${ipSuffix}_${segment.start_ts}_${segment.end_ts}_${channelSuffix}.jpg`;
    screenshotUrl = `/shots/${screenshotPath}`;
    console.log(`[DEBUG] 生成截图路径: ${screenshotUrl}, segment:`, segment);
  }
  
  // 如果截图正在生成中，显示加载状态
  if (segment.status === "processing") {
    if (loadingEl) {
      loadingEl.textContent = "正在生成截图...";
      loadingEl.style.display = "block";
    }
    // 轮询检查截图是否生成完成
    setTimeout(() => {
      if (screenshotBrowserData.task_id) {
        checkMinuteScreenshotStatus(screenshotBrowserData.task_id, index);
      }
    }, 2000);
  } else if (segment.status === "failed") {
    if (loadingEl) {
      loadingEl.textContent = `截图生成失败: ${segment.error || "未知错误"}`;
      loadingEl.style.display = "block";
    }
  }

  // 更新计数器
  if (counterEl) {
    counterEl.textContent = `${index + 1} / ${screenshotBrowserData.minuteSegments.length}`;
  }

  // 更新信息
  if (infoEl) {
    infoEl.textContent = `第${segment.minute}分钟 - ${segment.start_time} ~ ${segment.end_time}`;
  }

  // 更新右侧列表高亮
  updateScreenshotMinuteListHighlight(index);

  // 尝试加载截图
  if (imgEl) {
    imgEl.onload = function() {
      console.log(`[DEBUG] 截图加载成功: ${screenshotUrl}`);
      if (loadingEl) loadingEl.style.display = "none";
      imgEl.style.display = "block";
      // 确保图片可见且可点击
      imgEl.style.cursor = "pointer";
    };
    imgEl.onerror = function() {
      console.warn(`[DEBUG] 截图加载失败: ${screenshotUrl}, segment:`, segment);
      if (loadingEl) {
        if (segment.status === "completed" && segment.file_path) {
          loadingEl.textContent = "截图文件不存在或已删除";
        } else {
          loadingEl.textContent = "该时间段无截图";
        }
        loadingEl.style.display = "block";
      }
      imgEl.style.display = "none";
    };
    // 先清空src，避免显示旧图片
    imgEl.src = "";
    // 然后设置新的src
    if (screenshotUrl) {
      imgEl.src = screenshotUrl;
      console.log(`[DEBUG] 设置截图URL: ${screenshotUrl}`);
    }
  }
}

/**
 * 检查每分钟截图的状态
 */
async function checkMinuteScreenshotStatus(task_id, minute_index) {
  try {
    const response = await fetch(`/api/tasks/${task_id}/minute-screenshots`);
    if (response.ok) {
      const data = await response.json();
      const minuteScreenshot = data.minute_screenshots[minute_index];
      if (minuteScreenshot) {
        // 更新segment信息
        if (screenshotBrowserData.minuteSegments[minute_index]) {
          screenshotBrowserData.minuteSegments[minute_index].file_path = minuteScreenshot.file_path;
          screenshotBrowserData.minuteSegments[minute_index].image_url = minuteScreenshot.image_url;
          screenshotBrowserData.minuteSegments[minute_index].status = minuteScreenshot.status;
        }
        
        // 如果当前显示的就是这个分钟，重新加载
        if (screenshotBrowserData.currentIndex === minute_index) {
          if (minuteScreenshot.status === "completed" && (minuteScreenshot.image_url || minuteScreenshot.file_path)) {
            await loadScreenshot(minute_index);
          } else if (minuteScreenshot.status === "processing") {
            // 继续轮询
            setTimeout(() => {
              checkMinuteScreenshotStatus(task_id, minute_index);
            }, 2000);
          }
        }
      }
    }
  } catch (e) {
    console.warn("检查每分钟截图状态失败:", e);
  }
}

/**
 * 切换截图（左右导航）
 */
function navigateScreenshot(direction) {
  const newIndex = screenshotBrowserData.currentIndex + direction;
  if (newIndex >= 0 && newIndex < screenshotBrowserData.minuteSegments.length) {
    loadScreenshot(newIndex);
  }
}

/**
 * 播放当前分钟的视频
 * 点击截图中间区域播放视频，点击左右区域切换截图
 */
async function playCurrentMinuteVideo(event) {
  // 阻止事件冒泡
  event.stopPropagation();
  
  // 检查点击位置，如果在左右15%区域内，则切换截图
  const displayArea = event.currentTarget;
  const rect = displayArea.getBoundingClientRect();
  const clickX = event.clientX - rect.left;
  const width = rect.width;
  
  // 左侧15%区域：切换上一张
  if (clickX < width * 0.15) {
    navigateScreenshot(-1);
    return;
  }
  
  // 右侧15%区域：切换下一张
  if (clickX > width * 0.85) {
    navigateScreenshot(1);
    return;
  }
  
  // 中间区域（15% - 85%）：播放视频
  const segment = screenshotBrowserData.minuteSegments[screenshotBrowserData.currentIndex];
  if (segment && segment.rtsp_url) {
    // 关闭截图浏览弹窗
    closeScreenshotBrowser();
    // 播放视频
    await playRtsp(segment.rtsp_url, false);
  }
}

/**
 * 解析RTSP URL（从main.js复制）
 */
function parseRtspUrl(rtspUrl) {
  try {
    const match = rtspUrl.match(/^(rtsp:\/\/[^\/]+)\/([^\/]+)\/b(\d+)\/e(\d+)\/(.+)$/);
    if (!match) {
      return null;
    }
    return {
      base: match[1],
      channel: match[2],
      start_ts: parseInt(match[3], 10),
      end_ts: parseInt(match[4], 10),
      suffix: match[5]
    };
  } catch (e) {
    console.error("解析 RTSP URL 失败:", e);
    return null;
  }
}

/**
 * 生成分钟分段（从main.js复制并修改）
 */
function generateMinuteSegments(base, channel, start_ts, end_ts, suffix) {
  const segments = [];
  const totalDuration = end_ts - start_ts;
  const totalMinutes = Math.ceil(totalDuration / 60);
  
  for (let i = 0; i < totalMinutes; i++) {
    const segmentStart = start_ts + i * 60;
    const segmentEnd = Math.min(start_ts + (i + 1) * 60, end_ts);
    const rtspUrl = `${base}/${channel}/b${segmentStart}/e${segmentEnd}/${suffix}`;
    
    // 格式化时间为北京时间
    const startTimeStr = typeof formatTimestampToBeijing !== 'undefined' 
      ? formatTimestampToBeijing(segmentStart) 
      : new Date(segmentStart * 1000).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
    const endTimeStr = typeof formatTimestampToBeijing !== 'undefined'
      ? formatTimestampToBeijing(segmentEnd)
      : new Date(segmentEnd * 1000).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
    
    segments.push({
      minute: i + 1,
      start_ts: segmentStart,
      end_ts: segmentEnd,
      rtsp_url: rtspUrl,
      start_time: startTimeStr,
      end_time: endTimeStr
    });
  }
  
  return segments;
}

/**
 * 渲染右侧分钟列表
 */
function renderScreenshotMinuteList(segments, activeIndex) {
  const listContainer = document.getElementById("screenshot-minute-list");
  if (!listContainer) return;
  
  listContainer.innerHTML = "";
  
  if (!segments || segments.length === 0) {
    listContainer.innerHTML = '<div class="muted" style="padding:12px; text-align:center;">无分段数据</div>';
    return;
  }
  
  segments.forEach((seg, index) => {
    const isActive = index === activeIndex;
    const item = document.createElement("div");
    item.className = `screenshot-minute-item ${isActive ? 'active' : ''}`;
    item.dataset.index = index;
    item.dataset.minute = seg.minute;
    
    // 创建内容结构：标题 + 时间
    const titleDiv = document.createElement("div");
    titleDiv.textContent = `视频第${seg.minute}分钟`;
    
    const timeDiv = document.createElement("div");
    timeDiv.textContent = `${seg.start_time} ~ ${seg.end_time}`;
    
    item.appendChild(titleDiv);
    item.appendChild(timeDiv);
    
    // 点击列表项也可以切换截图
    item.addEventListener("click", () => {
      loadScreenshot(index);
    });
    
    listContainer.appendChild(item);
  });
}

/**
 * 更新右侧分钟列表的高亮状态
 */
function updateScreenshotMinuteListHighlight(activeIndex) {
  const listContainer = document.getElementById("screenshot-minute-list");
  if (!listContainer) return;
  
  const items = listContainer.querySelectorAll(".screenshot-minute-item");
  items.forEach((item, index) => {
    if (index === activeIndex) {
      item.classList.add("active");
      // 滚动到可见区域
      item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } else {
      item.classList.remove("active");
    }
  });
}
