/**
 * 主初始化模块
 * 包含视图切换、页面初始化、全局变量定义等
 */

// 全局变量定义（定时器）- 使用window对象确保全局作用域
window.autoRulesRefreshInterval = window.autoRulesRefreshInterval || null;
window.taskConfigsRefreshInterval = window.taskConfigsRefreshInterval || null;
window.taskDetailsRefreshInterval = window.taskDetailsRefreshInterval || null;

// 有数据的日期集合（用于在日期选择器中标记）
let availableDatesSet = new Set();

// 视图切换函数
window.switchView = function(view) {
  // 停止所有自动刷新定时器
  if (window.autoRulesRefreshInterval) {
    clearInterval(window.autoRulesRefreshInterval);
    window.autoRulesRefreshInterval = null;
  }
  if (window.taskConfigsRefreshInterval) {
    clearInterval(window.taskConfigsRefreshInterval);
    window.taskConfigsRefreshInterval = null;
  }
  if (window.taskDetailsRefreshInterval) {
    clearInterval(window.taskDetailsRefreshInterval);
    window.taskDetailsRefreshInterval = null;
  }
  
  ["dashboard","task-configs","tasks","images","parking-changes","parking-changes-list"].forEach(v => {
    const viewEl = document.getElementById(`view-${v}`);
    if (viewEl) {
      viewEl.style.display = v === view ? "block" : "none";
    }
    const navId = v === "task-configs" ? "nav-task-configs" : `nav-${v}`;
    const navEl = document.getElementById(navId);
    if (navEl) navEl.classList.toggle("active", v === view);
  });
  if (view === "task-configs") {
    loadConfigDateOptions();
    loadConfigIpOptions();
    loadConfigChannelOptions();
    // 清空所有搜索条件，确保每次进入都显示默认数据
    const configDateEl = document.getElementById("config-date");
    const configIpEl = document.getElementById("config-ip");
    const configChannelEl = document.getElementById("config-channel");
    const configStatusEl = document.getElementById("config-status");
    const configIpModeEl = document.getElementById("config-ip-mode");
    const configChannelModeEl = document.getElementById("config-channel-mode");
    const configDateLikeEl = document.getElementById("config-date-like");
    const configRtspLikeEl = document.getElementById("config-rtsp-like");
    const configStartTsGteEl = document.getElementById("config-start-ts-gte");
    const configStartTsLteEl = document.getElementById("config-start-ts-lte");
    const configEndTsGteEl = document.getElementById("config-end-ts-gte");
    const configEndTsLteEl = document.getElementById("config-end-ts-lte");
    const configIntervalGteEl = document.getElementById("config-interval-gte");
    const configIntervalLteEl = document.getElementById("config-interval-lte");
    const configOpTimeGteEl = document.getElementById("config-op-time-gte");
    const configOpTimeLteEl = document.getElementById("config-op-time-lte");
    const configStatusInEl = document.getElementById("config-status-in");
    
    if (configDateEl) configDateEl.value = "";
    if (configIpEl) configIpEl.value = "";
    if (configChannelEl) configChannelEl.value = "";
    if (configStatusEl) configStatusEl.value = "";
    if (configIpModeEl) configIpModeEl.value = "eq";
    if (configChannelModeEl) configChannelModeEl.value = "eq";
    if (configDateLikeEl) configDateLikeEl.value = "";
    if (configRtspLikeEl) configRtspLikeEl.value = "";
    if (configStartTsGteEl) configStartTsGteEl.value = "";
    if (configStartTsLteEl) configStartTsLteEl.value = "";
    if (configEndTsGteEl) configEndTsGteEl.value = "";
    if (configEndTsLteEl) configEndTsLteEl.value = "";
    if (configIntervalGteEl) configIntervalGteEl.value = "";
    if (configIntervalLteEl) configIntervalLteEl.value = "";
    if (configOpTimeGteEl) configOpTimeGteEl.value = "";
    if (configOpTimeLteEl) configOpTimeLteEl.value = "";
    if (configStatusInEl) configStatusInEl.value = "";
    
    // 重置分页
    configPage = 1;
    
    // 仅在进入「任务配置列表」视图时加载一次数据，
    // 后续由用户通过手动点击“搜索/刷新”来更新数据，不再自动轮询。
    loadTaskConfigs();
  }
  if (view === "tasks") {
    loadTaskDateOptions();
    loadTaskIpOptions();
    loadTaskChannelOptions();
    
    // 检查URL参数，如果是从图片列表跳转过来的，设置搜索条件
    const urlParams = new URLSearchParams(window.location.search);
    const viewParam = urlParams.get("view");
    if (viewParam === "tasks") {
      // 从URL参数读取搜索条件
      const dateInput = document.getElementById("task-date");
      const nameInput = document.getElementById("task-search-name");
      const ipInput = document.getElementById("task-search-ip");
      const channelInput = document.getElementById("task-search-channel");
      const taskIdInput = document.getElementById("task-search-id");
      
      // 填充搜索条件
      if (dateInput && urlParams.get("date")) {
        dateInput.value = urlParams.get("date");
      }
      if (nameInput && urlParams.get("name")) {
        nameInput.value = urlParams.get("name");
      }
      if (ipInput && urlParams.get("ip")) {
        ipInput.value = urlParams.get("ip");
      }
      if (channelInput && urlParams.get("channel")) {
        channelInput.value = urlParams.get("channel");
      }
      if (urlParams.get("task_id")) {
        // taskIdFromImage 在 tasks.js 中通过立即执行函数已经设置
        if (taskIdInput) {
          taskIdInput.value = urlParams.get("task_id");
        }
      }
      
      // 触发搜索
      setTimeout(() => {
        if (typeof searchTasks === "function") {
          searchTasks();
        } else {
          // 如果没有searchTasks函数，直接调用loadTasks
          const date = dateInput ? dateInput.value : "";
          if (typeof loadTasks === "function") {
            loadTasks(true, true, date || null);
          }
        }
      }, 100);
      
      // 清除URL参数，避免刷新时重复应用
      const newUrl = window.location.pathname;
      window.history.replaceState({}, "", newUrl);
    } else {
      // 确保日期输入框为空，然后加载全部数据
      const taskDateInput = document.getElementById("task-date");
      if (taskDateInput) {
        taskDateInput.value = "";
      }
      // 仅在进入「任务列表/任务详情」视图时加载一次数据，
      // 后续由用户通过手动点击"搜索/刷新"来更新数据，不再自动轮询。
      loadTasks(true, true, ""); // 明确传递空字符串，确保显示全部数据
    }
  }
  if (view === "images") {
    loadDateOptions();
    loadImageIpOptions();
    loadImageChannelOptions();
    // 不设置日期，让 loadImages 自动获取最新日期
    // 如果用户想查看其他日期，可以手动输入日期后搜索
    const imgDateInput = document.getElementById("img-date");
    if (imgDateInput && !imgDateInput.value.trim()) {
      // 如果日期输入框为空，清空它（让 loadImages 自动获取最新日期）
      imgDateInput.value = "";
    }
    loadImages(false, null); // 不传递 allowEmpty=true，会自动使用最新日期
  }
  if (view === "parking-changes") {
    // 加载日期选项（复用图片列表的日期选项）
    loadDateOptions().then(() => {
      // 将日期选项也填充到车位变化页面的 datalist
      const imgDatalist = document.getElementById("date-options");
      const pcDatalist = document.getElementById("pc-date-options");
      if (imgDatalist && pcDatalist) {
        pcDatalist.innerHTML = imgDatalist.innerHTML;
      }
    }).catch(() => {});
    // 初始化车位变化页面的日期选择器
    initDates().then(() => {
      // 日期选择器初始化完成后，先刷新筛选选项，再加载数据
      if (typeof refreshParkingChangeFilterOptions === 'function') {
        refreshParkingChangeFilterOptions().then(() => {
          loadParkingChangeSnapshots();
        }).catch(() => {
          loadParkingChangeSnapshots();
        });
      } else {
        loadParkingChangeSnapshots();
      }
    }).catch(() => {
      // 如果初始化失败，仍然尝试加载数据
      if (typeof refreshParkingChangeFilterOptions === 'function') {
        refreshParkingChangeFilterOptions().then(() => {
          loadParkingChangeSnapshots();
        }).catch(() => {
          loadParkingChangeSnapshots();
        });
      } else {
        loadParkingChangeSnapshots();
      }
    });
  }
  if (view === "parking-changes-list") {
    // 加载日期选项
    loadDateOptions().then(() => {
      const imgDatalist = document.getElementById("date-options");
      const pclDatalist = document.getElementById("pcl-date-options");
      if (imgDatalist && pclDatalist) {
        pclDatalist.innerHTML = imgDatalist.innerHTML;
      }
    }).catch(() => {});
    // 初始化日期选择器
    const pclDateInput = document.getElementById("pcl-date");
    if (pclDateInput && !pclDateInput._flatpickr && window.flatpickr) {
      flatpickr(pclDateInput, {
        dateFormat: "Y-m-d",
        onChange: function(selectedDates, dateStr) {
          // 可以在这里添加其他逻辑
        },
        onReady: function(selectedDates, dateStr, instance) {
          setTimeout(() => {
            if (availableDatesSet && availableDatesSet.size > 0) {
              markAvailableDates(instance);
            }
          }, 100);
        },
        onOpen: function(selectedDates, dateStr, instance) {
          setTimeout(() => {
            if (availableDatesSet && availableDatesSet.size > 0) {
              markAvailableDates(instance);
            }
          }, 50);
        },
        onMonthChange: function(selectedDates, dateStr, instance) {
          setTimeout(() => {
            if (availableDatesSet && availableDatesSet.size > 0) {
              markAvailableDates(instance);
            }
          }, 50);
        }
      });
    }
    // 加载数据
    if (typeof loadParkingChangeList === 'function') {
      loadParkingChangeList();
    }
  }
};

// 页面初始化
document.addEventListener("DOMContentLoaded", () => {
  populateBaseRtspOptions();
  // 加载自定义通道
  loadCustomChannels();
  // 加载自动分配配置的自定义通道
  loadAutoCustomChannels();
  // 初始化间隔时间按钮高亮
  updateIntervalButton();
  // 初始化自动分配配置的间隔时间按钮高亮
  updateAutoIntervalButton();
  
  // 确保 RTSP 输入框点击时能显示所有 datalist 选项
  const baseRtspInput = document.getElementById("base_rtsp");
  if (baseRtspInput) {
    let originalValue = baseRtspInput.value;
    baseRtspInput.addEventListener("focus", function() {
      // 保存原始值
      originalValue = this.value;
      // 清空当前值，让 datalist 下拉能够显示所有选项
      this.value = "";
    });
    baseRtspInput.addEventListener("blur", function() {
      // 如果用户没有修改就失去焦点，恢复原始值
      if (this.value === "" && originalValue) {
        this.value = originalValue;
      }
    });
    // 当选择的RTSP基础地址改变时，根据NVR配置更新通道列表
    baseRtspInput.addEventListener("change", function() {
      if (typeof updateChannelsFromSelectedNvr === "function") {
        updateChannelsFromSelectedNvr();
      }
    });
  }

  // 自动分配配置中的 RTSP 输入框也需要相同的交互：点击时展示所有选项
  const autoBaseRtspInput = document.getElementById("auto-base-rtsp");
  if (autoBaseRtspInput) {
    let originalAutoValue = autoBaseRtspInput.value;
    autoBaseRtspInput.addEventListener("focus", function() {
      originalAutoValue = this.value;
      this.value = "";
    });
    autoBaseRtspInput.addEventListener("blur", function() {
      if (this.value === "" && originalAutoValue) {
        this.value = originalAutoValue;
      }
    });
    autoBaseRtspInput.addEventListener("change", function() {
      if (typeof updateAutoChannelsFromSelectedNvr === "function") {
        updateAutoChannelsFromSelectedNvr();
      }
    });
  }
  
  // 初始视图：加载日期/IP/通道并自动填充最新日期后直接加载数据
  // 确保在 DOM 加载完成后再初始化日期选择器
  // 检查URL参数，如果有view参数，切换到对应视图
  const urlParams = new URLSearchParams(window.location.search);
  const viewParam = urlParams.get("view");
  if (viewParam === "tasks") {
    initDates().then(() => switchView("tasks"));
  } else {
    initDates().then(() => switchView("dashboard"));
  }

  // 注册图片预览键盘事件（左右切换、Esc 关闭）
  document.addEventListener("keydown", window.handlePreviewKeydown);
});

// RTSP 播放 (HLS 代理 + hls.js)
let hlsInstance = null;
let currentMinuteSegments = []; // 当前视频的分钟分段列表
let currentPlayingMinute = null; // 当前播放的分钟（null表示播放完整流）

/**
 * 解析 RTSP URL，提取 base、channel、start_ts、end_ts
 * 格式：rtsp://user:pass@ip:port/channel/b{start_ts}/e{end_ts}/replay/s1
 */
function parseRtspUrl(rtspUrl) {
  try {
    // 匹配格式：rtsp://.../channel/b{start_ts}/e{end_ts}/replay/s1
    const match = rtspUrl.match(/^(rtsp:\/\/[^\/]+)\/([^\/]+)\/b(\d+)\/e(\d+)\/(.+)$/);
    if (!match) {
      return null;
    }
    return {
      base: match[1],           // rtsp://admin:admin123=@10.10.11.123:10081
      channel: match[2],        // c3
      start_ts: parseInt(match[3], 10),  // 1766591400
      end_ts: parseInt(match[4], 10),    // 1766591999
      suffix: match[5]          // replay/s1
    };
  } catch (e) {
    console.error("解析 RTSP URL 失败:", e);
    return null;
  }
}

/**
 * 生成按分钟分割的 RTSP URL 列表
 */
function generateMinuteSegments(base, channel, start_ts, end_ts, suffix) {
  const segments = [];
  const totalDuration = end_ts - start_ts; // 总时长（秒）
  const totalMinutes = Math.ceil(totalDuration / 60); // 总分钟数
  
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
 * 渲染分钟列表
 */
function renderMinuteList(segments, activeMinute) {
  const listContainer = document.getElementById("video-minute-list");
  if (!listContainer) return;
  
  // 清除旧的事件监听器
  listContainer.innerHTML = "";
  
  if (!segments || segments.length === 0) {
    listContainer.innerHTML = '<div class="muted" style="padding:12px; text-align:center;">无分段数据</div>';
    return;
  }
  
  // 使用事件委托，避免在 HTML 中直接使用 onclick
  segments.forEach(seg => {
    const isActive = activeMinute === seg.minute;
    const item = document.createElement("div");
    item.className = `video-minute-item ${isActive ? 'active' : ''}`;
    item.dataset.minute = seg.minute;
    item.dataset.rtspUrl = seg.rtsp_url;
    
    // 创建内容结构：标题 + 时间
    const titleDiv = document.createElement("div");
    titleDiv.textContent = `视频第${seg.minute}分钟`;
    titleDiv.style.fontWeight = "bold";
    titleDiv.style.marginBottom = "4px";
    
    const timeDiv = document.createElement("div");
    timeDiv.textContent = `${seg.start_time} ~ ${seg.end_time}`;
    timeDiv.style.fontSize = "11px";
    timeDiv.style.color = "var(--muted)";
    timeDiv.style.opacity = "0.8";
    
    item.appendChild(titleDiv);
    item.appendChild(timeDiv);
    
    item.addEventListener("click", () => {
      switchToMinute(seg.minute, seg.rtsp_url);
    });
    listContainer.appendChild(item);
  });
}

/**
 * 切换到指定分钟的视频流
 */
async function switchToMinute(minute, rtspUrl) {
  if (currentPlayingMinute === minute) {
    return; // 已经在播放这个分钟了
  }
  
  // 更新高亮状态
  const listItems = document.querySelectorAll(".video-minute-item");
  listItems.forEach(item => {
    if (parseInt(item.dataset.minute) === minute) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });
  
  currentPlayingMinute = minute;
  
  // 播放对应时间段的流
  await playRtsp(rtspUrl, false); // false 表示不重新生成列表
}

// RTSP 播放 (HLS 代理 + hls.js)
async function playRtsp(rtspUrl, generateSegments = true) {
  try {
    const res = await api(`/api/hls/start?rtsp_url=${encodeURIComponent(rtspUrl)}`);
    if (!res || !res.m3u8) {
      alert("无法启动HLS代理");
      return;
    }
    const video = document.getElementById("rtsp-player");
    const modal = document.getElementById("video-modal");
    const link = document.getElementById("video-link");
    // 清理旧实例与 src
    if (hlsInstance) {
      hlsInstance.destroy();
      hlsInstance = null;
    }
    video.src = "";
    // 设置 m3u8 URL
    const m3u8Url = res.m3u8.startsWith("http") ? res.m3u8 : `${window.location.origin}${res.m3u8}`;
    link.href = m3u8Url;
    link.textContent = "m3u8";
    // 使用 hls.js 播放
    if (window.Hls && window.Hls.isSupported()) {
      hlsInstance = new window.Hls();
      hlsInstance.loadSource(m3u8Url);
      hlsInstance.attachMedia(video);
      hlsInstance.on(window.Hls.Events.MANIFEST_PARSED, () => {
        video.play().catch(e => console.warn("自动播放失败:", e));
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // Safari 原生支持 HLS
      video.src = m3u8Url;
      video.play().catch(e => console.warn("自动播放失败:", e));
    } else {
      alert("浏览器不支持HLS播放");
      return;
    }
    // 显示模态框
    modal.classList.add("open");
    document.getElementById("video-title").textContent = `RTSP: ${rtspUrl}`;
    
    // 如果 generateSegments 为 true，解析 RTSP URL 并生成分钟列表
    if (generateSegments) {
      const parsed = parseRtspUrl(rtspUrl);
      if (parsed) {
        currentMinuteSegments = generateMinuteSegments(
          parsed.base,
          parsed.channel,
          parsed.start_ts,
          parsed.end_ts,
          parsed.suffix
        );
        currentPlayingMinute = null; // 播放完整流
        renderMinuteList(currentMinuteSegments, null);
      } else {
        // 如果无法解析，清空列表
        currentMinuteSegments = [];
        renderMinuteList([], null);
      }
    }
  } catch (e) {
    alert("播放失败：" + (e.message || e));
  }
}

function closeVideoModal() {
  const modal = document.getElementById("video-modal");
  const video = document.getElementById("rtsp-player");
  if (hlsInstance) {
    hlsInstance.destroy();
    hlsInstance = null;
  }
  video.pause();
  video.src = "";
  modal.classList.remove("open");
  
  // 清理分钟列表
  currentMinuteSegments = [];
  currentPlayingMinute = null;
  const listContainer = document.getElementById("video-minute-list");
  if (listContainer) {
    listContainer.innerHTML = "";
  }
}

/**
 * 加载有数据的日期列表（从任务和图片API获取）
 */
async function loadAvailableDates() {
  try {
    const [tasksRes, imagesRes] = await Promise.all([
      api("/api/tasks/available_dates").catch(() => ({ dates: [] })),
      api("/api/images/available_dates").catch(() => ({ dates: [] }))
    ]);
    
    availableDatesSet.clear();
    
    // 从任务日期中提取
    if (tasksRes && tasksRes.dates) {
      tasksRes.dates.forEach(item => {
        const dateStr = typeof item === 'string' ? item : (item.date || item);
        if (dateStr) availableDatesSet.add(dateStr);
      });
    }
    
    // 从图片日期中提取
    if (imagesRes && imagesRes.dates) {
      imagesRes.dates.forEach(item => {
        const dateStr = typeof item === 'string' ? item : (item.date || item);
        if (dateStr) availableDatesSet.add(dateStr);
      });
    }
    
    console.log(`[initDates] 已加载 ${availableDatesSet.size} 个有数据的日期`);
    
    // 标记所有已初始化的日期选择器
    markAllDatePickers();
  } catch (e) {
    console.warn("加载有数据的日期失败:", e);
  }
}

/**
 * 标记日期选择器中有数据的日期
 */
function markAvailableDates(instance) {
  if (!instance || !instance.calendarContainer) return;
  if (availableDatesSet.size === 0) return;
  
  // 清除之前的标记
  const days = instance.calendarContainer.querySelectorAll('.flatpickr-day');
  days.forEach(day => {
    day.classList.remove('has-data');
  });
  
  // 标记有数据的日期
  let markedCount = 0;
  const dayElements = instance.calendarContainer.querySelectorAll('.flatpickr-day:not(.flatpickr-disabled)');
  
  // 获取当前显示的年份和月份
  const currentYear = instance.currentYear;
  const currentMonth = instance.currentMonth; // Flatpickr 的月份是 0-11
  
  // 月份名称映射（英文）
  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 
                      'July', 'August', 'September', 'October', 'November', 'December'];
  
  availableDatesSet.forEach(dateStr => {
    // 解析日期字符串 YYYY-MM-DD
    const parts = dateStr.split('-');
    if (parts.length !== 3) return;
    
    const targetYear = parseInt(parts[0], 10);
    const targetMonth = parseInt(parts[1], 10); // 1-12
    const targetDay = parseInt(parts[2], 10);
    
    if (isNaN(targetYear) || isNaN(targetMonth) || isNaN(targetDay)) return;
    
    // 只标记当前显示的月份
    if (currentYear !== targetYear || (currentMonth + 1) !== targetMonth) {
      return;
    }
    
    // 查找匹配的日期元素
    dayElements.forEach(day => {
      if (day.classList.contains('flatpickr-disabled')) return;
      
      const ariaLabel = day.getAttribute('aria-label') || '';
      const dayText = day.textContent.trim();
      const dayNum = parseInt(dayText, 10);
      
      if (isNaN(dayNum) || dayNum !== targetDay) return;
      
      let isMatch = false;
      
      if (ariaLabel) {
        // 支持英文格式： "December 19, 2025" 或 "December 19,2025"
        const englishMatch = ariaLabel.match(/(\w+)\s+(\d{1,2}),?\s*(\d{4})/);
        if (englishMatch) {
          const monthName = englishMatch[1];
          const labelDay = parseInt(englishMatch[2], 10);
          const labelYear = parseInt(englishMatch[3], 10);
          const monthIndex = monthNames.indexOf(monthName);
          
          if (monthIndex !== -1 && 
              labelYear === targetYear && 
              (monthIndex + 1) === targetMonth && 
              labelDay === targetDay) {
            isMatch = true;
          }
        } else {
          // 支持中文格式： "2025年12月19日" 或 "2025年12月19"
          const chineseMatch = ariaLabel.match(/(\d{4})[年\s]+(\d{1,2})[月\s]+(\d{1,2})/);
          if (chineseMatch) {
            const labelYear = parseInt(chineseMatch[1], 10);
            const labelMonth = parseInt(chineseMatch[2], 10);
            const labelDay = parseInt(chineseMatch[3], 10);
            
            if (labelYear === targetYear && labelMonth === targetMonth && labelDay === targetDay) {
              isMatch = true;
            }
          }
        }
      } else {
        // 如果没有 aria-label，只根据当前月份和日期数字匹配（可能不够精确，但作为备选）
        if (currentYear === targetYear && (currentMonth + 1) === targetMonth && dayNum === targetDay) {
          isMatch = true;
        }
      }
      
      if (isMatch) {
        day.classList.add('has-data');
        markedCount++;
      }
    });
  });
  
  if (markedCount > 0) {
    console.log(`[markAvailableDates] 已标记 ${markedCount} 个有数据的日期`);
  }
}

/**
 * 标记所有已初始化的日期选择器
 */
function markAllDatePickers() {
  const dateInputs = [
    document.getElementById("date"),
    document.getElementById("task-date"),
    document.getElementById("img-date"),
    document.getElementById("config-date"),
    document.getElementById("auto-custom-date"),
    document.getElementById("pc-date"),
    document.getElementById("pcl-date")
  ];
  
  dateInputs.forEach(input => {
    if (input && input._flatpickr) {
      markAvailableDates(input._flatpickr);
    }
  });
}

/**
 * 初始化日期选择器
 */
async function initDates() {
  // 先加载有数据的日期列表
  await loadAvailableDates();
  
  // 如果Flatpickr已加载，初始化所有日期输入框
  if (window.flatpickr) {
    // 初始化基础日期选择器
    const dateInput = document.getElementById("date");
    if (dateInput && !dateInput._flatpickr) {
      flatpickr(dateInput, {
        dateFormat: "Y-m-d",
        defaultDate: getBeijingToday(),
        onChange: function(selectedDates, dateStr) {
          syncDates();
        }
      });
    }
    
    // 初始化任务日期选择器
    const taskDateInput = document.getElementById("task-date");
    if (taskDateInput && !taskDateInput._flatpickr) {
      flatpickr(taskDateInput, {
        dateFormat: "Y-m-d",
        onChange: function(selectedDates, dateStr) {
          // 可以在这里添加其他逻辑
        },
        onReady: function(selectedDates, dateStr, instance) {
          setTimeout(() => markAvailableDates(instance), 50);
        },
        onOpen: function(selectedDates, dateStr, instance) {
          setTimeout(() => markAvailableDates(instance), 50);
        }
      });
    }
    
    // 初始化图片日期选择器
    const imgDateInput = document.getElementById("img-date");
    if (imgDateInput && !imgDateInput._flatpickr) {
      flatpickr(imgDateInput, {
        dateFormat: "Y-m-d",
        onChange: function(selectedDates, dateStr) {
          // 可以在这里添加其他逻辑
        },
        onReady: function(selectedDates, dateStr, instance) {
          setTimeout(() => {
            if (availableDatesSet && availableDatesSet.size > 0) {
              markAvailableDates(instance);
            }
          }, 100);
        },
        onOpen: function(selectedDates, dateStr, instance) {
          setTimeout(() => {
            if (availableDatesSet && availableDatesSet.size > 0) {
              markAvailableDates(instance);
            }
          }, 50);
        },
        onMonthChange: function(selectedDates, dateStr, instance) {
          setTimeout(() => {
            if (availableDatesSet && availableDatesSet.size > 0) {
              markAvailableDates(instance);
            }
          }, 50);
        }
      });
    }
    
    // 初始化配置日期选择器
    const configDateInput = document.getElementById("config-date");
    if (configDateInput && !configDateInput._flatpickr) {
      flatpickr(configDateInput, {
        dateFormat: "Y-m-d",
        onChange: function(selectedDates, dateStr) {
          // 可以在这里添加其他逻辑
        },
        onReady: function(selectedDates, dateStr, instance) {
          setTimeout(() => markAvailableDates(instance), 50);
        },
        onOpen: function(selectedDates, dateStr, instance) {
          setTimeout(() => markAvailableDates(instance), 50);
        }
      });
    }
    
    // 初始化自动分配配置日期选择器
    const autoDateInput = document.getElementById("auto-custom-date");
    if (autoDateInput && !autoDateInput._flatpickr) {
      flatpickr(autoDateInput, {
        dateFormat: "Y-m-d",
        onChange: function(selectedDates, dateStr) {
          previewAutoRule();
        },
        onReady: function(selectedDates, dateStr, instance) {
          setTimeout(() => {
            if (availableDatesSet && availableDatesSet.size > 0) {
              markAvailableDates(instance);
            }
          }, 100);
        },
        onOpen: function(selectedDates, dateStr, instance) {
          setTimeout(() => {
            if (availableDatesSet && availableDatesSet.size > 0) {
              markAvailableDates(instance);
            }
          }, 50);
        },
        onMonthChange: function(selectedDates, dateStr, instance) {
          setTimeout(() => {
            if (availableDatesSet && availableDatesSet.size > 0) {
              markAvailableDates(instance);
            }
          }, 50);
        }
      });
    }
    
    // 初始化车位变化日期选择器
    const pcDateInput = document.getElementById("pc-date");
    if (pcDateInput && !pcDateInput._flatpickr) {
      flatpickr(pcDateInput, {
        dateFormat: "Y-m-d",
        onChange: function(selectedDates, dateStr) {
          // 可以在这里添加其他逻辑
        },
        onReady: function(selectedDates, dateStr, instance) {
          setTimeout(() => markAvailableDates(instance), 50);
        },
        onOpen: function(selectedDates, dateStr, instance) {
          setTimeout(() => markAvailableDates(instance), 50);
        }
      });
    }
  } else {
    // 如果Flatpickr未加载，等待一段时间后重试
    if (window.FLATPICKR_LOADING) {
      return new Promise((resolve) => {
        const checkInterval = setInterval(() => {
          if (window.flatpickr || !window.FLATPICKR_LOADING) {
            clearInterval(checkInterval);
            initDates().then(resolve);
          }
        }, 100);
        setTimeout(() => {
          clearInterval(checkInterval);
          resolve(); // 超时后也resolve，避免阻塞
        }, 5000);
      });
    }
  }
  return Promise.resolve();
}

/**
 * 图片预览键盘事件处理
 * 注意：此函数在images.js中已定义并挂载到window对象
 * 这里只是确保在images.js加载前也能使用
 */
if (typeof window.handlePreviewKeydown === 'undefined') {
  window.handlePreviewKeydown = function(event) {
    const modal = document.getElementById("img-modal");
    if (!modal || !modal.classList.contains("open")) return;

    const key = event.key;
    if (key === "ArrowLeft") {
      event.preventDefault();
      if (typeof prevPreview === 'function') prevPreview();
    } else if (key === "ArrowRight") {
      event.preventDefault();
      if (typeof nextPreview === 'function') nextPreview();
    } else if (key === "Escape" || key === "Esc") {
      event.preventDefault();
      if (typeof closePreview === 'function') closePreview();
    }
  };
}
