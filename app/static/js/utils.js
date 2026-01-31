/**
 * 工具函数模块
 * 提供通用的工具函数，如时间格式化、状态映射等
 */

// NVR 配置缓存（用于参数设置/自动分配中的 RTSP 和通道选择）
let NVR_CONFIG_OPTIONS = [];

// 根据 NVR 配置构造 RTSP 基础地址
function buildBaseRtspFromNvrConfig(config) {
  if (!config) return "";
  // 注意：这里不要对用户名/密码做 URL 编码，
  // 需要保持和任务配置里原来使用的格式完全一致，
  // 否则例如 "admin123=" 会被变成 "admin123%3D"
  const user = config.nvr_username || "";
  const pass = config.nvr_password || "";
  const ip = config.nvr_ip || "";
  const port = config.nvr_port || 554;
  // 保持与任务生成使用的格式一致：rtsp://user:pass@ip:port
  return `rtsp://${user}:${pass}@${ip}:${port}`;
}

// 状态映射
const statusMap = {
  "pending": "待运行",
  "playing": "运行中",
  "screenshot_taken": "完成",
  "completed": "完成",
  "failed": "部分失败",
};

/**
 * 填充RTSP基础地址选项（从后端NVR配置动态加载）
 */
async function populateBaseRtspOptions() {
  try {
    const configs = await api("/api/nvr-configs");
    NVR_CONFIG_OPTIONS = Array.isArray(configs) ? configs : [];

    const baseList = document.getElementById("base-rtsp-options");
    const autoList = document.getElementById("auto-base-rtsp-options");

    const optionsHtml = NVR_CONFIG_OPTIONS.map(cfg => {
      const rtsp = buildBaseRtspFromNvrConfig(cfg);
      cfg._base_rtsp = rtsp;
      const label = `${cfg.parking_name || cfg.nvr_ip || ""} (${cfg.nvr_ip || ""}:${cfg.nvr_port || 554})`;
      return `<option value="${rtsp}" label="${label}">${label}</option>`;
    }).join("");

    if (baseList) {
      baseList.innerHTML = optionsHtml;
    }
    if (autoList) {
      autoList.innerHTML = optionsHtml;
    }

    // 如果基础参数设置中的 RTSP 输入框为空，则默认选中第一个 NVR
    const baseInput = document.getElementById("base_rtsp");
    if (baseInput && !baseInput.value && NVR_CONFIG_OPTIONS.length > 0) {
      baseInput.value = NVR_CONFIG_OPTIONS[0]._base_rtsp || "";
    }

    const autoBaseInput = document.getElementById("auto-base-rtsp");
    if (autoBaseInput && !autoBaseInput.value && NVR_CONFIG_OPTIONS.length > 0) {
      autoBaseInput.value = NVR_CONFIG_OPTIONS[0]._base_rtsp || "";
    }

    // 根据当前选中的 RTSP 更新“参数设置”Tab的通道复选框（如果函数存在）
    if (typeof updateChannelsFromSelectedNvr === "function") {
      updateChannelsFromSelectedNvr();
    }

    // 同时也更新“自动分配配置”Tab里的通道复选框设计，使其与参数设置保持一致
    if (typeof updateAutoChannelsFromSelectedNvr === "function") {
      updateAutoChannelsFromSelectedNvr();
    }
  } catch (e) {
    console.error("加载NVR配置用于RTSP选项失败:", e);
  }
}

/**
 * 获取当前北京时间（YYYY-MM-DD格式）
 */
function getBeijingToday() {
  const now = new Date();
  const utc = now.getTime() + now.getTimezoneOffset() * 60000;
  const bj = new Date(utc + 8 * 3600 * 1000);
  const pad = (n) => n.toString().padStart(2, "0");
  return `${bj.getFullYear()}-${pad(bj.getMonth() + 1)}-${pad(bj.getDate())}`;
}

/**
 * 获取选中的RTSP地址列表
 */
function getSelectedRtspList() {
  const checks = document.querySelectorAll(".rtsp-option:checked");
  const list = Array.from(checks).map(c => c.value);
  if (list.length === 0) {
    const v = (document.getElementById("base_rtsp").value || "").trim();
    if (v) list.push(v);
  }
  return list;
}

/**
 * 将状态文本或状态码映射到CSS类名
 */
function getStatusClass(status) {
  // 如果是中文状态文本，直接返回
  if (["待运行", "运行中", "部分失败", "完成"].includes(status)) {
    return status;
  }
  // 如果是英文状态码，映射到中文状态
  const statusTextMap = {
    "pending": "待运行",
    "playing": "运行中",
    "completed": "完成",
    "screenshot_taken": "完成",
    "failed": "部分失败",
  };
  return statusTextMap[status] || status;
}

/**
 * 将Unix时间戳转换为可读字符串
 */
function tsToStr(ts) {
  if (!ts) return '';
  const d = new Date(ts * 1000);
  const pad = (n) => n.toString().padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

/**
 * 将 Unix 时间戳转为北京时间可读字符串
 */
function formatTimestampToBeijing(ts) {
  if (!ts && ts !== 0) return '';
  const d = new Date(Number(ts) * 1000);
  return d.toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).replace(/\//g, "-");
}

/**
 * 将图片文件名（start_end_channel.jpg）转成易读时间段显示
 * 优先使用任务时间段（task_start_ts/task_end_ts），如果没有则从文件名解析
 */
function formatImageDisplayName(itemOrName) {
  // 如果是对象且有任务时间段，优先使用任务时间段
  if (typeof itemOrName === "object" && itemOrName) {
    if (itemOrName.task_start_ts !== undefined && itemOrName.task_start_ts !== null && 
        itemOrName.task_end_ts !== undefined && itemOrName.task_end_ts !== null) {
      const startTs = Number(itemOrName.task_start_ts);
      const endTs = Number(itemOrName.task_end_ts);
      // 验证时间戳是否有效（不是0或很小的值，避免1970年）
      // 时间戳应该是10位数字（秒级时间戳），例如 1766160000 对应 2025-12-20
      if (startTs > 1000000000 && endTs > 1000000000 && startTs < 9999999999 && endTs < 9999999999) {
        const startStr = formatTimestampToBeijing(startTs);
        const endStr = formatTimestampToBeijing(endTs);
        const ch = itemOrName.task_channel || "";
        return `${startStr} ~ ${endStr}${ch ? ` (${ch})` : ""}`;
      }
    }
  }
  
  // 回退到从文件名解析
  const name = typeof itemOrName === "string" ? itemOrName : ((itemOrName && itemOrName.name) ? itemOrName.name : "");
  if (!name) return "未命名";
  
  // 文件名格式：IP_IP_IP_IP_startTs_endTs_channel.jpg
  // 例如：10_10_11_123_1766160000_1766160599_c1.jpg
  // 需要匹配最后两个数字（时间戳），而不是第一个数字
  const match = /_(\d{10})_(\d{10})(?:_(c\d+))?/i.exec(name);
  if (!match) {
    // 如果匹配失败，尝试简单格式：start_end_channel.jpg
    const simpleMatch = /^(\d{10})_(\d{10})(?:_(c\d+))?/i.exec(name);
    if (simpleMatch) {
      const startTs = Number(simpleMatch[1]);
      const endTs = Number(simpleMatch[2]);
      const ch = simpleMatch[3] || "";
      
      // 验证时间戳是否有效（10位数字，避免1970年）
      if (startTs > 1000000000 && endTs > 1000000000 && startTs < 9999999999 && endTs < 9999999999) {
        const startStr = formatTimestampToBeijing(startTs);
        const endStr = formatTimestampToBeijing(endTs);
        return `${startStr} ~ ${endStr}${ch ? ` (${ch})` : ""}`;
      }
    }
    return name; // 如果无法解析，直接返回文件名
  }
  
  const startTs = Number(match[1]);
  const endTs = Number(match[2]);
  const ch = match[3] || "";
  
  // 验证时间戳是否有效（10位数字，避免1970年）
  if (startTs <= 1000000000 || endTs <= 1000000000 || startTs >= 9999999999 || endTs >= 9999999999) {
    return name; // 如果时间戳无效，直接返回文件名
  }
  
  const startStr = formatTimestampToBeijing(startTs);
  const endStr = formatTimestampToBeijing(endTs);
  return `${startStr} ~ ${endStr}${ch ? ` (${ch})` : ""}`;
}

/**
 * 将UTC时间字符串转换为北京时间（UTC+8）显示
 */
function formatOperationTime(isoString) {
  if (!isoString) return '';
  try {
    // 确保ISO字符串有时区信息（如果没有'Z'，添加它表示UTC）
    let timeStr = isoString;
    if (!timeStr.endsWith('Z') && !timeStr.includes('+') && !timeStr.includes('-', 10)) {
      timeStr = timeStr + 'Z';
    }
    const d = new Date(timeStr);
    
    // 使用 toLocaleString 转换为北京时间
    const beijingStr = d.toLocaleString("zh-CN", {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
    
    // 格式化为 YYYY-MM-DD HH:mm:ss
    // toLocaleString 返回格式可能是 "2025/12/15 10:30:45" 或 "2025-12-15 10:30:45"
    return beijingStr.replace(/\//g, '-');
  } catch (e) {
    console.warn('formatOperationTime error:', e, isoString);
    return isoString;
  }
}

/**
 * 同步日期到各个输入框
 */
function syncDates() {
  const base = document.getElementById("date");
  const d = base ? base.value : '';
  if (d) {
    const taskDate = document.getElementById("task-date");
    if (taskDate) taskDate.value = d;
    const imgDate = document.getElementById("img-date");
    if (imgDate) imgDate.value = d;
    const configDate = document.getElementById("config-date");
    if (configDate) configDate.value = d;
  }
}

/**
 * 搜索所有（任务、图片、OCR）
 */
function searchAll() {
  const date = (document.getElementById("date").value || "").trim();
  if (!date) {
    alert("请先填写日期");
    return;
  }
  loadTasks(true);
  loadImages();
  loadOCR();
}

/**
 * 加载OCR结果
 */
async function loadOCR() {
  const date = (document.getElementById("date").value || "").trim();
  if (!date) {
    alert("请先填写日期");
    return;
  }
  try {
    const res = await api(`/api/ocr/${date}`);
    const ocrEl = document.getElementById("ocr");
    if (ocrEl) {
      ocrEl.value = JSON.stringify(res, null, 2);
    }
  } catch (e) {
    console.error("加载OCR失败:", e);
    const ocrEl = document.getElementById("ocr");
    if (ocrEl) {
      ocrEl.value = `错误: ${e.message || e}`;
    }
  }
}
