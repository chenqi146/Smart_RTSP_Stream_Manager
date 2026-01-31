/**
 * 基础参数配置模块
 * 包含参数设置、自动分配配置、NVR配置等相关功能
 */

// 全局变量定义（使用window对象确保全局作用域）
window.autoRulesRefreshInterval = window.autoRulesRefreshInterval || null;

// Tab切换函数
function switchTab(tab) {
  const manualTab = document.getElementById("tab-manual");
  const autoTab = document.getElementById("tab-auto");
  const nvrConfigTab = document.getElementById("tab-nvr-config");
  const manualContent = document.getElementById("tab-content-manual");
  const autoContent = document.getElementById("tab-content-auto");
  const autoRulesContent = document.getElementById("tab-content-auto-rules");
  const nvrConfigContent = document.getElementById("tab-content-nvr-config");
  
  // 清除自动分配配置Tab的定时器（只清理这个Tab相关的定时器）
  if (window.autoRulesRefreshInterval) {
    clearInterval(window.autoRulesRefreshInterval);
    window.autoRulesRefreshInterval = null;
  }
  
  // 重置所有tab样式
  if (manualTab) manualTab.style.borderBottom = "none";
  if (autoTab) autoTab.style.borderBottom = "none";
  if (nvrConfigTab) nvrConfigTab.style.borderBottom = "none";
  
  // 隐藏所有内容
  if (manualContent) manualContent.style.display = "none";
  if (autoContent) autoContent.style.display = "none";
  if (autoRulesContent) autoRulesContent.style.display = "none";
  if (nvrConfigContent) nvrConfigContent.style.display = "none";
  
  if (tab === "manual") {
    if (manualTab) manualTab.style.borderBottom = "2px solid var(--accent)";
    if (manualContent) manualContent.style.display = "block";
    // 每次切回“参数设置”时，重新从数据库加载最新的 NVR 配置和 RTSP 基础地址选项
    if (typeof populateBaseRtspOptions === "function") {
      populateBaseRtspOptions();
    }
  } else if (tab === "auto") {
    if (autoTab) autoTab.style.borderBottom = "2px solid var(--accent)";
    if (autoContent) autoContent.style.display = "block";
    if (autoRulesContent) autoRulesContent.style.display = "block";
    loadAutoRules();
    loadAutoCustomChannels(); // 加载自定义通道
    updateAutoIntervalButton(); // 更新间隔时间按钮高亮
    // 确保自动分配配置里的通道区域，和“参数设置”里一样，直接根据当前 RTSP 基础地址从数据库加载通道
    if (typeof updateAutoChannelsFromSelectedNvr === "function") {
      updateAutoChannelsFromSelectedNvr();
    } else {
      previewAutoRule();
    }
    
    // 启动自动刷新：每30秒刷新一次规则列表，以便同步后端执行状态
    window.autoRulesRefreshInterval = setInterval(() => {
      loadAutoRules();
    }, 30000); // 30秒刷新一次
  } else if (tab === "nvr-config") {
    if (nvrConfigTab) nvrConfigTab.style.borderBottom = "2px solid var(--accent)";
    if (nvrConfigContent) nvrConfigContent.style.display = "block";
    loadNvrConfigs();
  }
}

// 切换日期输入框
function toggleAutoDate() {
  const useToday = document.getElementById("auto-use-today");
  const customDate = document.getElementById("auto-custom-date");
  if (useToday && customDate) {
    customDate.disabled = useToday.checked;
    if (useToday.checked) {
      customDate.value = "";
    }
    previewAutoRule();
  }
}

// 解析OCR裁剪框
function parseCrop() {
  const v = document.getElementById("crop").value.trim();
  if (!v) return null;
  const parts = v.split(",").map(x => parseInt(x, 10)).filter(x => !isNaN(x));
  if (parts.length === 4) return parts;
  alert("裁剪框格式应为: x1,y1,x2,y2"); return null;
}

// 获取所有选中的通道
function getSelectedChannels() {
  const channels = [];
  // 标准通道（根据NVR配置动态生成）
  document.querySelectorAll('.channel-checkbox:checked').forEach(cb => {
    channels.push(cb.value);
  });
  // 自定义通道
  const customChannels = document.querySelectorAll('.custom-channel-checkbox:checked');
  customChannels.forEach(cb => {
    channels.push(cb.value);
  });
  return channels;
}

// 设置间隔时间
function setIntervalTime(minutes) {
  document.getElementById("interval").value = minutes;
  updateIntervalButton();
}

// 更新间隔时间按钮高亮
function updateIntervalButton() {
  const interval = parseInt(document.getElementById("interval").value, 10) || 10;
  document.querySelectorAll('.interval-btn').forEach(btn => {
    if (parseInt(btn.dataset.interval, 10) === interval) {
      btn.style.background = 'var(--accent)';
      btn.style.color = '#000';
    } else {
      btn.style.background = '';
      btn.style.color = '';
    }
  });
}

// 全选通道
function selectAllChannels() {
  document.querySelectorAll('.channel-checkbox').forEach(cb => {
    cb.checked = true;
  });
  document.querySelectorAll('.custom-channel-checkbox').forEach(cb => {
    cb.checked = true;
  });
}

// 清空通道选择
function clearAllChannels() {
  document.querySelectorAll('.channel-checkbox').forEach(cb => {
    cb.checked = false;
  });
  document.querySelectorAll('.custom-channel-checkbox').forEach(cb => {
    cb.checked = false;
  });
}

// 添加自定义通道
function addCustomChannel() {
  const input = document.getElementById("custom-channel-input");
  const channel = input.value.trim().toLowerCase();
  
  if (!channel) {
    alert("请输入通道名称");
    return;
  }
  
  // 验证通道格式（c+数字）
  if (!/^c\d+$/.test(channel)) {
    alert("通道格式应为 c+数字，如 c5, c10");
    return;
  }
  
  const existing = document.querySelector(`.custom-channel-checkbox[value="${channel}"]`);
  if (existing) {
    alert("该自定义通道已添加");
    return;
  }
  
  // 创建复选框
  const container = document.getElementById("custom-channels-container");
  const label = document.createElement("label");
  label.className = "checkbox";
  label.style.cssText = "display:flex; align-items:center; gap:6px;";
  
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.className = "custom-channel-checkbox";
  checkbox.value = channel;
  checkbox.checked = true;
  checkbox.id = `channel-${channel}`;
  
  const span = document.createElement("span");
  span.textContent = channel;
  
  const removeBtn = document.createElement("button");
  removeBtn.className = "ghost";
  removeBtn.style.cssText = "font-size:11px; padding:2px 6px; margin-left:4px;";
  removeBtn.textContent = "×";
  removeBtn.onclick = function() {
    label.remove();
    saveCustomChannels();
  };
  
  label.appendChild(checkbox);
  label.appendChild(span);
  label.appendChild(removeBtn);
  container.appendChild(label);
  
  input.value = "";
  saveCustomChannels();
}

// 保存自定义通道到localStorage
function saveCustomChannels() {
  const customChannels = [];
  document.querySelectorAll('.custom-channel-checkbox').forEach(cb => {
    customChannels.push(cb.value);
  });
  localStorage.setItem('customChannels', JSON.stringify(customChannels));
}

// 从localStorage加载自定义通道
function loadCustomChannels() {
  try {
    const saved = localStorage.getItem('customChannels');
    if (saved) {
      const channels = JSON.parse(saved);
      channels.forEach(ch => {
        // 检查是否已存在
        const existing = document.querySelector(`.custom-channel-checkbox[value="${ch}"]`);
        if (!existing && !['c1', 'c2', 'c3', 'c4'].includes(ch)) {
          const container = document.getElementById("custom-channels-container");
          const label = document.createElement("label");
          label.className = "checkbox";
          label.style.cssText = "display:flex; align-items:center; gap:6px;";
          
          const checkbox = document.createElement("input");
          checkbox.type = "checkbox";
          checkbox.className = "custom-channel-checkbox";
          checkbox.value = ch;
          checkbox.checked = true;
          checkbox.id = `channel-${ch}`;
          
          const span = document.createElement("span");
          span.textContent = ch;
          
          const removeBtn = document.createElement("button");
          removeBtn.className = "ghost";
          removeBtn.style.cssText = "font-size:11px; padding:2px 6px; margin-left:4px;";
          removeBtn.textContent = "×";
          removeBtn.onclick = function() {
            label.remove();
            saveCustomChannels();
          };
          
          label.appendChild(checkbox);
          label.appendChild(span);
          label.appendChild(removeBtn);
          container.appendChild(label);
        }
      });
    }
  } catch (e) {
    console.warn("加载自定义通道失败:", e);
  }
}

// 自动分配配置：根据当前选中的 NVR 基础地址填充标准通道复选框
async function updateAutoChannelsFromSelectedNvr() {
  try {
    const container = document.getElementById("auto-standard-channels-container");
    if (!container) return;

    const baseInput = document.getElementById("auto-base-rtsp");
    const value = baseInput ? (baseInput.value || "").trim() : "";

    if (!value) {
      container.innerHTML = `
        <div class="muted" style="font-size:12px;">
          请先选择上方的 RTSP 基础地址。
        </div>
      `;
      return;
    }

    const params = new URLSearchParams({ base_rtsp: value });
    const channels = await api(`/api/channels/by-base-rtsp?${params.toString()}`);

    if (!channels || channels.length === 0) {
      container.innerHTML = `
        <div class="muted" style="font-size:12px;">
          当前 RTSP 对应的 NVR 暂未配置通道，请在“NVR配置”标签页中添加通道。
        </div>
      `;
      return;
    }

    let html = "";
    channels.forEach(ch => {
      const code = ch.channel_code || "";
      if (!code) return;
      const labelText = ch.camera_name || ch.camera_ip || code;
      html += `
        <label class="checkbox" style="display:flex; align-items:center; gap:6px;">
          <input type="checkbox" class="auto-channel-checkbox" value="${code}" checked onchange="previewAutoRule()" />
          <span>${code}</span>
          <span class="muted" style="font-size:11px;">${labelText}</span>
        </label>
      `;
    });

    html += `
      <button class="ghost" style="font-size:12px; padding:4px 8px;" onclick="selectAllAutoChannels()">全选</button>
      <button class="ghost" style="font-size:12px; padding:4px 8px;" onclick="clearAllAutoChannels()">清空</button>
    `;

    container.innerHTML = html;
    previewAutoRule();
  } catch (e) {
    console.error("根据NVR配置更新自动分配通道列表失败:", e);
  }
}

// 根据当前选中的NVR基础地址，动态填充“参数设置”Tab的标准通道复选框
async function updateChannelsFromSelectedNvr() {
  try {
    const container = document.getElementById("standard-channels-container");
    if (!container) return;

    const baseInput = document.getElementById("base_rtsp");
    const value = baseInput ? (baseInput.value || "").trim() : "";

    if (!value) {
      container.innerHTML = `
        <div class="muted" style="font-size:12px;">
          请先选择上方的 RTSP 基础地址。
        </div>
      `;
      return;
    }

    const params = new URLSearchParams({ base_rtsp: value });
    const channels = await api(`/api/channels/by-base-rtsp?${params.toString()}`);

    if (!channels || channels.length === 0) {
      container.innerHTML = `
        <div class="muted" style="font-size:12px;">
          当前 RTSP 对应的 NVR 暂未配置通道，请先在“NVR配置”标签页中添加通道。
        </div>
      `;
      return;
    }

    let html = "";
    channels.forEach(ch => {
      const code = ch.channel_code || "";
      if (!code) return;
      const labelText = ch.camera_name || ch.camera_ip || code;
      html += `
        <label class="checkbox" style="display:flex; align-items:center; gap:6px;">
          <input type="checkbox" class="channel-checkbox" id="channel-${code}" value="${code}" checked />
          <span>${code}</span>
          <span class="muted" style="font-size:11px;">${labelText}</span>
        </label>
      `;
    });

    html += `
      <button class="ghost" style="font-size:12px; padding:4px 8px;" onclick="selectAllChannels()">全选</button>
      <button class="ghost" style="font-size:12px; padding:4px 8px;" onclick="clearAllChannels()">清空</button>
    `;

    container.innerHTML = html;
  } catch (e) {
    console.error("根据NVR配置更新通道列表失败:", e);
  }
}

// 生成任务
async function createTasks() {
  const baseDate = document.getElementById("date").value.trim();
  if (!baseDate) {
    alert("请先填写日期");
    return;
  }
  
  const selectedChannels = getSelectedChannels();
  if (selectedChannels.length === 0) {
    alert("请至少选择一个通道");
    return;
  }
  
  const base_rtsp = document.getElementById("base_rtsp").value;
  const interval_minutes = parseInt(document.getElementById("interval").value, 10) || 10;
  
  // 批量生成任务（按通道逐个调用后端）
  const results = [];
  let successCount = 0;
  let failCount = 0;
  
  for (const channel of selectedChannels) {
    try {
      const body = {
        date: baseDate,
        base_rtsp: base_rtsp,
        channel: channel,
        interval_minutes: interval_minutes,
      };
      const res = await api("/api/tasks/create", { method: "POST", body: JSON.stringify(body) });
      
      const created = typeof res.created_segments === "number" ? res.created_segments : (res.created_count || 0);
      const existing = typeof res.existing_segments === "number" ? res.existing_segments : (res.existing_count || 0);
      const total = typeof res.total_segments === "number" ? res.total_segments : 0;
      let msg;
      
      if (res.message) {
        // 如果返回了message，说明任务已存在
        msg = res.message;
      } else if (created === 0 && existing > 0) {
        msg = "该通道在该日期/时间段下的任务已全部存在，未重复创建";
      } else if (created > 0 && existing > 0) {
        msg = `新建 ${created} 段任务，已有 ${existing} 段任务存在`;
      } else if (created > 0 && existing === 0) {
        msg = `成功新建 ${created} 段任务`;
      } else if (created === 0 && existing === 0 && total > 0) {
        msg = `已生成 ${total} 段任务配置，但未创建到数据库（可能已全部存在或创建失败）`;
      } else {
        msg = "未生成任务（可能是配置异常）";
      }

      results.push({ channel, success: true, result: res, message: msg });
      successCount++;
    } catch (e) {
      const errorMsg = e.message || e.toString();
      // 检查是否是任务已存在的错误
      if (errorMsg.includes("任务已存在")) {
        results.push({ channel, success: true, message: errorMsg });
        successCount++;
      } else {
        results.push({ channel, success: false, error: errorMsg });
        failCount++;
      }
    }
  }
  
  // 显示结果（如果页面中存在用于调试输出的文本区域，则写入；否则静默跳过）
  const resultText = results.map(r => {
    if (!r.success) {
      return `${r.channel}: 失败${r.error ? ' - ' + r.error : ''}`;
    }
    return `${r.channel}: ${r.message || '成功'}`;
  }).join('\n');
  const tasksDebugArea = document.getElementById("tasks");
  if (tasksDebugArea) {
    tasksDebugArea.value = `批量生成结果:\n成功: ${successCount}, 失败: ${failCount}\n\n${resultText}\n\n详细信息:\n${JSON.stringify(results, null, 2)}`;
  }
  
  // 始终给出弹窗提示，避免用户感知不到是否生成成功
  if (successCount > 0) {
    alert(`任务生成完成：成功 ${successCount} 个通道，失败 ${failCount} 个`);
    // 自动切到任务列表并带入当前日期/RTSP
    gotoTasksFromDashboard();
  } else {
    alert(`任务生成失败：成功 0 个通道，失败 ${failCount} 个。\n请查看页面下方“批量生成结果”区域了解详细原因。`);
  }
}

// 从“参数设置”跳转到任务列表，并带入当前日期/RTSP筛选
function gotoTasksFromDashboard() {
  const date = (document.getElementById("date")?.value || "").trim();
  const baseRtsp = (document.getElementById("base_rtsp")?.value || "").trim();
  // 切换视图
  switchView("tasks");
  // 等待视图渲染后设置筛选条件并搜索
  setTimeout(() => {
    const taskDateInput = document.getElementById("task-date");
    if (taskDateInput && date) taskDateInput.value = date;
    const taskRtspLike = document.getElementById("task-rtsp-like");
    if (taskRtspLike && baseRtsp) taskRtspLike.value = baseRtsp;
    if (typeof searchTasks === "function") {
      searchTasks();
    }
  }, 50);
}

// 运行任务
async function runTasks() {
  const baseDate = document.getElementById("date").value.trim();
  if (!baseDate) {
    alert("请先填写日期");
    return;
  }
  
  const selectedChannels = getSelectedChannels();
  if (selectedChannels.length === 0) {
    alert("请至少选择一个通道");
    return;
  }
  
  const crop = parseCrop();
  if (crop === false) return;
  
  const base_rtsp = document.getElementById("base_rtsp").value;
  const interval_minutes = parseInt(document.getElementById("interval").value, 10) || 10;
  
  // 批量运行任务
  let successCount = 0;
  let failCount = 0;
  
  for (const channel of selectedChannels) {
    try {
      const body = {
        date: baseDate,
        base_rtsp: base_rtsp,
        channel: channel,
        interval_minutes: interval_minutes,
        screenshot_dir: "screenshots",
        crop_ocr_box: crop,
      };
      await api("/api/tasks/run", { method: "POST", body: JSON.stringify(body) });
      successCount++;
    } catch (e) {
      console.error(`运行通道 ${channel} 失败:`, e);
      failCount++;
    }
  }
  
  if (successCount > 0) {
    alert(`已启动 ${successCount} 个通道的任务${failCount > 0 ? `，${failCount} 个失败` : ''}`);
  } else {
    alert("启动失败");
  }
}

// 自动分配配置：获取选中的通道（含自定义）
function getAutoSelectedChannels() {
  const channels = [];
  document.querySelectorAll('.auto-channel-checkbox:checked').forEach(cb => {
    channels.push(cb.value);
  });
  const customChannels = document.querySelectorAll('.auto-custom-channel-checkbox:checked');
  customChannels.forEach(cb => channels.push(cb.value));
  return channels;
}

// 自动分配配置：设置间隔时间
function setAutoIntervalTime(minutes) {
  const input = document.getElementById("auto-interval");
  if (input) input.value = minutes;
  updateAutoIntervalButton();
  previewAutoRule();
}

// 自动分配配置：更新间隔时间按钮高亮
function updateAutoIntervalButton() {
  const intervalEl = document.getElementById("auto-interval");
  const interval = parseInt(intervalEl ? intervalEl.value : 10) || 10;
  document.querySelectorAll('.auto-interval-btn').forEach(btn => {
    if (parseInt(btn.dataset.interval, 10) === interval) {
      btn.style.background = 'var(--accent)';
      btn.style.color = '#000';
    } else {
      btn.style.background = '';
      btn.style.color = '';
    }
  });
}

// 自动分配配置：全选通道
function selectAllAutoChannels() {
  document.querySelectorAll('.auto-channel-checkbox').forEach(cb => cb.checked = true);
  document.querySelectorAll('.auto-custom-channel-checkbox').forEach(cb => cb.checked = true);
  previewAutoRule();
}

// 自动分配配置：清空通道
function clearAllAutoChannels() {
  document.querySelectorAll('.auto-channel-checkbox').forEach(cb => cb.checked = false);
  document.querySelectorAll('.auto-custom-channel-checkbox').forEach(cb => cb.checked = false);
  previewAutoRule();
}

// 自动分配配置：添加自定义通道
function addAutoCustomChannel() {
  const input = document.getElementById("auto-custom-channel-input");
  const channel = input ? input.value.trim().toLowerCase() : "";
  if (!channel) {
    alert("请输入通道名称");
    return;
  }
  if (!/^c\d+$/.test(channel)) {
    alert("通道格式应为 c+数字，如 c5, c10");
    return;
  }
  const container = document.getElementById("auto-custom-channels-container");
  if (!container) return;
  if (container.querySelector(`input[value="${channel}"]`)) {
    alert("该通道已添加");
    return;
  }
  const label = document.createElement("label");
  label.className = "checkbox";
  label.style.display = "flex";
  label.style.alignItems = "center";
  label.style.gap = "6px";

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.value = channel;
  checkbox.className = "auto-custom-channel-checkbox";
  checkbox.checked = true;
  checkbox.onchange = () => previewAutoRule();

  const span = document.createElement("span");
  span.textContent = channel;

  const removeBtn = document.createElement("button");
  removeBtn.className = "ghost";
  removeBtn.style.fontSize = "12px";
  removeBtn.style.padding = "2px 6px";
  removeBtn.textContent = "删除";
  removeBtn.onclick = () => {
    label.remove();
    try {
      const saved = JSON.parse(localStorage.getItem("autoCustomChannels") || "[]");
      const filtered = saved.filter(c => c !== channel);
      localStorage.setItem("autoCustomChannels", JSON.stringify(filtered));
    } catch (e) {
      console.warn("保存自定义通道失败:", e);
    }
    previewAutoRule();
  };

  label.appendChild(checkbox);
  label.appendChild(span);
  label.appendChild(removeBtn);
  container.appendChild(label);

  try {
    const saved = JSON.parse(localStorage.getItem("autoCustomChannels") || "[]");
    if (!saved.includes(channel)) {
      saved.push(channel);
      localStorage.setItem("autoCustomChannels", JSON.stringify(saved));
    }
  } catch (e) {
    console.warn("保存自定义通道失败:", e);
  }

  if (input) input.value = "";
  previewAutoRule();
}

// 自动分配配置：加载自定义通道
function loadAutoCustomChannels() {
  try {
    const saved = JSON.parse(localStorage.getItem("autoCustomChannels") || "[]");
    const container = document.getElementById("auto-custom-channels-container");
    if (!container) return;
    container.innerHTML = "";
    saved.forEach(channel => {
      const label = document.createElement("label");
      label.className = "checkbox";
      label.style.display = "flex";
      label.style.alignItems = "center";
      label.style.gap = "6px";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = channel;
      checkbox.className = "auto-custom-channel-checkbox";
      checkbox.checked = true;
      checkbox.onchange = () => previewAutoRule();

      const span = document.createElement("span");
      span.textContent = channel;

      const removeBtn = document.createElement("button");
      removeBtn.className = "ghost";
      removeBtn.style.fontSize = "12px";
      removeBtn.style.padding = "2px 6px";
      removeBtn.textContent = "删除";
      removeBtn.onclick = () => {
        label.remove();
        const filtered = saved.filter(c => c !== channel);
        localStorage.setItem("autoCustomChannels", JSON.stringify(filtered));
        previewAutoRule();
      };

      label.appendChild(checkbox);
      label.appendChild(span);
      label.appendChild(removeBtn);
      container.appendChild(label);
    });
  } catch (e) {
    console.warn("加载自定义通道失败:", e);
  }
}

// 生成任务预览
function generateTaskPreview(date, baseRtsp, channel, intervalMinutes, previewCount = 5) {
  // 计算日期的时间戳（使用北京时间）
  const dateObj = new Date(date + " 00:00:00");
  // 转换为北京时间（UTC+8）
  const beijingOffset = 8 * 60 * 60 * 1000;
  const startOfDay = Math.floor((dateObj.getTime() - beijingOffset) / 1000);
  const endOfDay = startOfDay + 86400 - 1; // 23:59:59
  
  const previewSegments = [];
  let current = startOfDay;
  let index = 0;
  let totalSegments = 0;
  
  // 计算所有任务段（用于统计）
  while (current < endOfDay) {
    const segmentEnd = Math.min(current + intervalMinutes * 60 - 1, endOfDay);
    totalSegments++;
    
    // 只保存前N条用于预览
    if (previewSegments.length < previewCount) {
      const startDate = new Date((current + 8 * 3600) * 1000); // 转换回北京时间显示
      const endDate = new Date((segmentEnd + 8 * 3600) * 1000);
      
      // 格式化为北京时间字符串
      const startStr = startDate.toLocaleString("zh-CN", {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZone: 'Asia/Shanghai'
      }).replace(/\//g, '-');
      
      const endStr = endDate.toLocaleString("zh-CN", {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZone: 'Asia/Shanghai'
      }).replace(/\//g, '-');
      
      // 使用s1主码流（高分辨率）替代s0子码流（低分辨率）
      // 如果s1不可用，可以尝试移除s参数或使用s0
      const rtspUrl = `${baseRtsp}/${channel}/b${current}/e${segmentEnd}/replay/s1`;
      
      previewSegments.push({
        index: index++,
        start: startStr,
        startTs: current,
        end: endStr,
        endTs: segmentEnd,
        rtsp: rtspUrl
      });
    }
    
    current = segmentEnd + 1;
  }

  // 生成预览文本
  let preview = "============================================================\n";
  preview += "任务生成预览（基于当前参数）\n";
  preview += "============================================================\n\n";
  preview += `日期: ${date}\n`;
  preview += `RTSP基础地址: ${baseRtsp}\n`;
  preview += `通道: ${channel}\n`;
  preview += `间隔: ${intervalMinutes} 分钟\n`;
  preview += `预计生成任务数: ${totalSegments} 个\n`;
  preview += `总时长: 24 小时 (86400 秒)\n`;
  preview += "\n";
  preview += "============================================================\n";
  preview += `前 ${previewCount} 条任务预览:\n`;
  preview += "============================================================\n\n";
  
  previewSegments.forEach(seg => {
    preview += `任务 #${seg.index + 1}\n`;
    preview += `开始时间: ${seg.start} (时间戳: ${seg.startTs})\n`;
    preview += `结束时间: ${seg.end} (时间戳: ${seg.endTs})\n`;
    const duration = seg.endTs - seg.startTs;
    const hours = Math.floor(duration / 3600);
    const minutes = Math.floor((duration % 3600) / 60);
    const seconds = duration % 60;
    preview += `视频时长: ${hours}小时${minutes}分钟${seconds}秒 (${duration} 秒)\n`;
    preview += `RTSP 地址:\n${seg.rtsp}\n`;
    preview += "============================================================\n\n";
  });
  
  if (totalSegments > previewCount) {
    preview += `... 还有 ${totalSegments - previewCount} 个任务未显示\n`;
    preview += "（完整任务列表将在保存规则后生成）\n";
  }
  
  return preview;
}

// 生成自动任务预览（支持多通道）
function generateAutoTaskPreview(date, baseRtsp, channels, intervalMinutes, previewCount = 5) {
  if (channels.length === 0) {
    return "请至少选择一个通道";
  }
  
  // 为第一个通道生成详细预览
  const firstChannelPreview = generateTaskPreview(date, baseRtsp, channels[0], intervalMinutes, previewCount);
  
  // 添加多通道统计信息
  let preview = firstChannelPreview;
  if (channels.length > 1) {
    preview += "\n";
    preview += "============================================================\n";
    preview += `多通道统计（共 ${channels.length} 个通道）:\n`;
    preview += "============================================================\n";
    channels.forEach((ch, idx) => {
      // 计算该通道的任务数
      const dateObj = new Date(date + " 00:00:00");
      const beijingOffset = 8 * 60 * 60 * 1000;
      const startOfDay = Math.floor((dateObj.getTime() - beijingOffset) / 1000);
      const endOfDay = startOfDay + 86400 - 1;
      let taskCount = 0;
      let current = startOfDay;
      while (current < endOfDay) {
        const segmentEnd = Math.min(current + intervalMinutes * 60 - 1, endOfDay);
        taskCount++;
        current = segmentEnd + 1;
      }
      preview += `通道 ${ch}: ${taskCount} 个任务\n`;
    });
    preview += `总计: ${channels.length * (previewCount > 0 ? Math.floor((endOfDay - startOfDay) / (intervalMinutes * 60)) : 0)} 个任务\n`;
  }
  
  return preview;
}

// 预览自动规则
function previewAutoRule() {
  const useTodayEl = document.getElementById("auto-use-today");
  const customDateEl = document.getElementById("auto-custom-date");
  const baseRtspEl = document.getElementById("auto-base-rtsp");
  const autoIntervalEl = document.getElementById("auto-interval");

  const useToday = useTodayEl ? useTodayEl.checked : false;
  const customDate = customDateEl ? customDateEl.value : "";
  const baseRtsp = baseRtspEl ? (baseRtspEl.value || "").trim() : "";
  const selectedChannels = getAutoSelectedChannels();
  const interval = parseInt(autoIntervalEl ? autoIntervalEl.value : 10) || 10;
  
  if (!baseRtsp) {
    document.getElementById("auto-preview").textContent = "请填写RTSP基础地址";
    return;
  }
  
  if (selectedChannels.length === 0) {
    document.getElementById("auto-preview").textContent = "请至少选择一个通道";
    return;
  }

  const date = useToday ? getBeijingToday() : customDate;
  if (!date) {
    document.getElementById("auto-preview").textContent = "请选择日期";
    return;
  }

  // 生成预览（显示前5条，并包含统计信息）
  // 如果有多个通道，显示第一个通道的预览，但统计信息包含所有通道
  const preview = generateAutoTaskPreview(date, baseRtsp, selectedChannels, interval, 5);
  document.getElementById("auto-preview").textContent = preview;
}

// 保存自动规则（支持多通道，每个通道创建一个规则）
async function saveAutoRule() {
  const useTodayEl = document.getElementById("auto-use-today");
  const customDateEl = document.getElementById("auto-custom-date");
  const baseRtspEl = document.getElementById("auto-base-rtsp");
  const autoIntervalEl = document.getElementById("auto-interval");
  const triggerTimeEl = document.getElementById("auto-trigger-time");

  const useToday = useTodayEl ? useTodayEl.checked : false;
  const customDate = customDateEl ? customDateEl.value : "";
  const baseRtsp = baseRtspEl ? (baseRtspEl.value || "").trim() : "";
  const selectedChannels = getAutoSelectedChannels();
  const interval = parseInt(autoIntervalEl ? autoIntervalEl.value : 10) || 10;
  const triggerTime = triggerTimeEl ? triggerTimeEl.value : "";
  
  if (!baseRtsp) {
    alert("请填写RTSP基础地址");
    return;
  }
  if (selectedChannels.length === 0) {
    alert("请至少选择一个通道");
    return;
  }
  if (!triggerTime) {
    alert("请选择触发时间");
    return;
  }
  if (!useToday && !customDate) {
    alert("请选择日期或勾选自动获取当日时间");
    return;
  }

  try {
    // 为每个选中的通道创建一个规则
    const results = [];
    let successCount = 0;
    let failCount = 0;
    
    for (const channel of selectedChannels) {
      try {
        const rule = {
          use_today: useToday,
          custom_date: useToday ? null : customDate,
          base_rtsp: baseRtsp,
          channel: channel,
          interval_minutes: interval,
          trigger_time: triggerTime
        };
        
        const res = await api("/api/auto-schedule/rules", {
          method: "POST",
          body: JSON.stringify(rule)
        });
        
        results.push({ channel, success: true, result: res });
        successCount++;
      } catch (e) {
        results.push({ channel, success: false, error: e.toString() });
        failCount++;
      }
    }
    
    // 显示结果
    if (successCount > 0 && failCount === 0) {
      alert(`规则保存成功！共创建 ${successCount} 个规则（${selectedChannels.join(', ')}）`);
    } else if (successCount > 0 && failCount > 0) {
      const failedChannels = results.filter(r => !r.success).map(r => r.channel).join(', ');
      alert(`部分规则保存成功：成功 ${successCount} 个，失败 ${failCount} 个\n失败的通道: ${failedChannels}`);
    } else {
      const firstErr = (results[0] && results[0].error) ? results[0].error : "未知错误";
      alert(`规则保存失败：${firstErr}`);
      return;
    }
    
    loadAutoRules();
    // 清空表单
    document.getElementById("auto-base-rtsp").value = "";
    // 重置通道选择：根据当前 RTSP 重新加载（会默认全选）
    if (typeof updateAutoChannelsFromSelectedNvr === "function") {
      await updateAutoChannelsFromSelectedNvr();
    }
    document.getElementById("auto-interval").value = "10";
    document.getElementById("auto-trigger-time").value = "18:00";
    document.getElementById("auto-use-today").checked = true;
    document.getElementById("auto-custom-date").value = "";
    document.getElementById("auto-custom-date").disabled = true;
    updateAutoIntervalButton();
    previewAutoRule();
  } catch (e) {
    console.error("保存规则失败:", e);
    alert("保存失败：" + (e.message || e));
  }
}

// 加载已保存的规则
async function loadAutoRules() {
  try {
    const rules = await api("/api/auto-schedule/rules");
    const listDiv = document.getElementById("auto-rules-list");
    if (!listDiv) return;
    
    if (!rules || rules.length === 0) {
      listDiv.innerHTML = '<div class="muted">暂无保存的规则</div>';
      return;
    }
    
    // 生成表格形式的规则列表
    let tableHtml = `
      <table class="data-table" style="width:100%; border-collapse:collapse;">
        <thead>
          <tr style="background:rgba(255,255,255,0.05); border-bottom:1px solid var(--border);">
            <th style="padding:12px; text-align:left; font-weight:600;">规则名称</th>
            <th style="padding:12px; text-align:left; font-weight:600;">启用状态</th>
            <th style="padding:12px; text-align:left; font-weight:600;">日期</th>
            <th style="padding:12px; text-align:left; font-weight:600;">RTSP基础地址</th>
            <th style="padding:12px; text-align:left; font-weight:600;">通道</th>
            <th style="padding:12px; text-align:left; font-weight:600;">间隔</th>
            <th style="padding:12px; text-align:left; font-weight:600;">触发时间</th>
            <th style="padding:12px; text-align:left; font-weight:600;">执行次数</th>
            <th style="padding:12px; text-align:left; font-weight:600;">上次执行</th>
            <th style="padding:12px; text-align:left; font-weight:600;">执行状态</th>
            <th style="padding:12px; text-align:center; font-weight:600;">操作</th>
          </tr>
        </thead>
        <tbody>
    `;
    
    rules.forEach((rule, idx) => {
      const dateStr = rule.use_today ? "当天时间" : rule.custom_date;
      const status = rule.is_enabled ? "启用" : "禁用";
      const statusClass = rule.is_enabled ? "tag completed" : "tag pending";
      const ruleName = rule.name || `规则 #${idx + 1}`;
      
      // 处理执行状态和时间
      let execTimeStr = "-";
      let execStatusStr = "尚未执行";
      let execStatusClass = "tag pending";
      let execErrorHtml = "";
      
      if (rule.last_executed_at) {
        // 转换时间为北京时间
        let utcTimeStr = rule.last_executed_at;
        if (!utcTimeStr.endsWith('Z') && !utcTimeStr.includes('+') && !utcTimeStr.match(/[+-]\d{2}:\d{2}$/)) {
          utcTimeStr = utcTimeStr + 'Z';
        }
        const execDate = new Date(utcTimeStr);
        execTimeStr = execDate.toLocaleString("zh-CN", {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
          timeZone: 'Asia/Shanghai'
        });
        
        // 根据执行状态显示
        if (rule.last_execution_status === "running") {
          execStatusStr = "执行中";
          execStatusClass = "tag playing";
        } else if (rule.last_execution_status === "success") {
          execStatusStr = "成功";
          execStatusClass = "tag completed";
        } else if (rule.last_execution_status === "failed") {
          execStatusStr = "失败";
          execStatusClass = "tag failed";
        }
        
        if (rule.last_execution_error) {
          execErrorHtml = `<div style="color:var(--error); font-size:11px; margin-top:4px;" title="${rule.last_execution_error}">${rule.last_execution_error.length > 30 ? rule.last_execution_error.substring(0, 30) + '...' : rule.last_execution_error}</div>`;
        }
      }
      
      tableHtml += `
        <tr style="border-bottom:1px solid var(--border);">
          <td style="padding:12px;">${ruleName}</td>
          <td style="padding:12px;"><span class="${statusClass}">${status}</span></td>
          <td style="padding:12px;">${dateStr}</td>
          <td style="padding:12px; max-width:250px; word-break:break-all; font-size:11px;">${rule.base_rtsp}</td>
          <td style="padding:12px;">${rule.channel}</td>
          <td style="padding:12px;">${rule.interval_minutes}分钟</td>
          <td style="padding:12px;">${rule.trigger_time}</td>
          <td style="padding:12px;">${rule.execution_count || 0}</td>
          <td style="padding:12px; font-size:11px;">${execTimeStr}</td>
          <td style="padding:12px;">
            <span class="${execStatusClass}">${execStatusStr}</span>
            ${execErrorHtml}
          </td>
          <td style="padding:12px; text-align:center;">
            <button class="ghost" style="padding:4px 8px; font-size:12px; margin-right:4px;" onclick="toggleRule(${rule.id}, ${!rule.is_enabled})">${rule.is_enabled ? "禁用" : "启用"}</button>
            <button class="ghost" style="padding:4px 8px; font-size:12px; color:#ff6b6b;" onclick="deleteRule(${rule.id})">删除</button>
          </td>
        </tr>
      `;
    });
    
    tableHtml += `
        </tbody>
      </table>
    `;
    
    listDiv.innerHTML = tableHtml;
  } catch (e) {
    console.error("加载规则失败:", e);
    document.getElementById("auto-rules-list").innerHTML = '<div class="muted">加载失败</div>';
  }
}

// 切换规则启用状态
async function toggleRule(id, enabled) {
  try {
    await api(`/api/auto-schedule/rules/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_enabled: enabled })
    });
    loadAutoRules();
  } catch (e) {
    alert("操作失败：" + e);
  }
}

// 删除规则
async function deleteRule(id) {
  if (!confirm("确定要删除这条规则吗？")) return;
  try {
    await api(`/api/auto-schedule/rules/${id}`, { method: "DELETE" });
    loadAutoRules();
  } catch (e) {
    alert("删除失败：" + e);
  }
}

// 自动生成并运行
let isAutoRunning = false;
async function autoGenerateAndRun() {
  if (isAutoRunning) return;
  const useNowEl = document.getElementById("auto-use-now");
  const useNow = useNowEl ? useNowEl.checked : false;
  const rtspList = getSelectedRtspList();
  if (!rtspList.length) {
    alert("请至少选择或填写一个 RTSP 基础地址");
    return;
  }
  const btn = document.getElementById("auto-run-btn");
  try {
    isAutoRunning = true;
    if (btn) {
      btn.disabled = true;
      btn.innerText = "运行中...";
    }
    if (useNow) {
      const today = getBeijingToday();
      const dateInput = document.getElementById("date");
      if (dateInput) dateInput.value = today;
    }
    for (const rtsp of rtspList) {
      const baseInput = document.getElementById("base_rtsp");
      if (baseInput) baseInput.value = rtsp;
      await createTasks();
      await runTasks();
    }
    alert("已按当前北京时间为所选地址生成任务并后台运行，请稍后查看任务/图片列表。");
  } catch (e) {
    alert("自动运行失败：" + e);
  } finally {
    isAutoRunning = false;
    if (btn) {
      btn.disabled = false;
      btn.innerText = "一键自动生成并运行";
    }
  }
}

// 管理操作：清空全部数据
async function handleClearAll() {
  if (!confirm("【危险操作】\n\n此操作将清空系统中的所有业务数据：\n- 所有任务记录\n- 所有截图及其物理文件\n- 所有 OCR 结果\n- 所有自动调度规则\n\n该操作不可恢复，仅建议在测试/开发环境执行。\n\n是否确认继续？")) {
    return;
  }
  try {
    const res = await api("/api/admin/clear_all", { method: "POST" });
    alert(res.message || "已清空全部业务数据。");
  } catch (e) {
    alert("清空失败：" + (e.message || e));
  }
}

// 管理操作：重新部署
async function handleRedeploy() {
  if (!confirm("【危险操作】\n\n此操作将重新部署系统，可能导致服务中断。\n\n是否确认继续？")) {
    return;
  }
  try {
    const res = await api("/api/admin/redeploy", { method: "POST" });
    alert(res.message || "系统重新部署中...");
  } catch (e) {
    alert("重新部署失败：" + (e.message || e));
  }
}
