/**
 * 图片列表模块
 * 包含图片列表、图片预览相关的所有功能
 */

// 图片预览与通道元数据相关变量
let currentImages = [];
// 记录“用于下拉筛选的基础图片结果”，即在未按通道精确过滤时最后一次返回的结果。
// 这样可以避免在按某个通道过滤后，通道下拉只剩这一项，无法再选回其它通道。
let baseFilterImages = [];
let currentIndex = 0;
let isPreviewZoomed = false;
let isFirstPreviewOpen = false; // 标记是否是首次打开预览

// 通道元数据（用于展示“c1 高新四路9号枪机”这样的文案）
let imageChannelMetaLoaded = false;
let imageChannelMetaByIpAndCode = new Map(); // key: `${ip}|${code}`
let imageChannelMetaByCode = new Map();      // key: `code`

// 车位元数据（用于在图片下方展示“车位：A01、A02 ...”这样的文案）
let imageParkingSpacesLoaded = false;
let imageParkingSpacesByIpAndCode = new Map(); // key: `${ip}|${code}` -> [spaceName1, spaceName2, ...]

function buildImageChannelKey(ip, code) {
  const ipPart = (ip || "").trim();
  const codePart = (code || "").trim().toLowerCase();
  return `${ipPart}|${codePart}`;
}

async function ensureImageChannelMetaLoaded() {
  if (imageChannelMetaLoaded) return;
  try {
    const channels = await api("/api/channels");
    if (Array.isArray(channels)) {
      channels.forEach(ch => {
        const code = (ch.channel_code || "").trim().toLowerCase();
        if (!code) return;
        const ip = (ch.nvr_ip || "").trim();
        const labelText = ch.camera_name || ch.camera_ip || ch.nvr_ip || code.toUpperCase();
        const meta = {
          code,
          ip,
          label: `${code.toUpperCase()} ${labelText}`,
        };
        const key = buildImageChannelKey(ip, code);
        imageChannelMetaByIpAndCode.set(key, meta);
        if (!imageChannelMetaByCode.has(code)) {
          imageChannelMetaByCode.set(code, meta);
        }
      });
    }
  } catch (e) {
    console.warn("加载图片通道元数据失败:", e);
  } finally {
    imageChannelMetaLoaded = true;
  }
}

function getImageChannelDisplayLabel(ip, code) {
  const normCode = (code || "").trim().toLowerCase();
  if (!normCode) return "";
  const key = buildImageChannelKey(ip, normCode);
  const meta = imageChannelMetaByIpAndCode.get(key) || imageChannelMetaByCode.get(normCode);
  if (meta) return meta.label;
  return normCode.toUpperCase();
}

async function ensureImageParkingSpacesLoaded() {
  if (imageParkingSpacesLoaded) return;
  try {
    const configs = await api("/api/nvr-configs");
    if (Array.isArray(configs)) {
      configs.forEach(cfg => {
        const nvrIp = (cfg.nvr_ip || "").trim();
        const channels = Array.isArray(cfg.channels) ? cfg.channels : [];
        channels.forEach(ch => {
          const code = (ch.channel_code || "").trim().toLowerCase();
          if (!code) return;
          const key = buildImageChannelKey(nvrIp, code);
          const spaces = Array.isArray(ch.parking_spaces) ? ch.parking_spaces : [];
          const names = spaces
            .map(ps => ps.space_name || ps.space_id)
            .filter(Boolean);
          if (names.length === 0) return;
          // 如果同一个 ip+通道 在多个配置中重复出现，则合并去重
          const existing = imageParkingSpacesByIpAndCode.get(key) || [];
          const merged = Array.from(new Set(existing.concat(names)));
          imageParkingSpacesByIpAndCode.set(key, merged);
        });
      });
    }
  } catch (e) {
    console.warn("加载车位元数据失败:", e);
  } finally {
    imageParkingSpacesLoaded = true;
  }
}

function extractChannelCodeFromTaskChannel(raw) {
  const s = (raw || "").toString().trim();
  if (!s) return "";
  const m = s.match(/^([cC]\d+)/);
  return (m ? m[1] : s).trim().toLowerCase();
}

function getParkingSpacesDisplay(ip, taskChannel) {
  const code = extractChannelCodeFromTaskChannel(taskChannel);
  if (!code) return "";
  const key = buildImageChannelKey(ip, code);
  const names = imageParkingSpacesByIpAndCode.get(key);
  if (!names || names.length === 0) return "";
  return names.join("、");
}

/**
 * 获取最新有数据的日期
 */
async function getLatestAvailableDate() {
  try {
    // 先尝试从 available_dates API 获取
    let res = await api("/api/images/available_dates");
    let dates = [];
    
    // 检查不同的响应格式
    if (Array.isArray(res?.dates)) {
      dates = res.dates.map(d => (typeof d === "string" ? d : d.date)).filter(Boolean);
    } else if (Array.isArray(res)) {
      dates = res.map(d => (typeof d === "string" ? d : d.date)).filter(Boolean);
    } else if (res?.items && Array.isArray(res.items)) {
      // 如果返回的是 items 格式，提取日期
      dates = res.items.map(d => (typeof d === "string" ? d : d.date)).filter(Boolean);
    }
    
    // 如果从 available_dates API 没有获取到日期，尝试从图片数据中提取
    if (dates.length === 0) {
      try {
        const imagesRes = await api("/api/images?limit=100");
        if (imagesRes && imagesRes.items && Array.isArray(imagesRes.items)) {
          const dateSet = new Set();
          imagesRes.items.forEach(item => {
            if (item.task_date) {
              dateSet.add(item.task_date);
            }
          });
          dates = Array.from(dateSet);
        }
      } catch (e2) {
        console.warn("从图片数据提取日期失败:", e2);
      }
    }
    
    if (dates && dates.length > 0) {
      // 按日期降序排序，返回最新的日期
      const sortedDates = dates.sort((a, b) => b.localeCompare(a));
      return sortedDates[0];
    }
    return null;
  } catch (e) {
    console.warn("获取最新日期失败:", e);
    return null;
  }
}

/**
 * 加载图片列表
 */
async function loadImages(allowEmpty=false, dateOverride=null) {
  const imgDateEl = document.getElementById("img-date");
  // 这里只使用图片列表自己的日期输入框，不再从基础参数配置的全局日期(#date)兜底，
  // 避免“未在图片列表填写日期却按某天过滤”的问题。
  let dateInput = dateOverride !== null
    ? (dateOverride || "")
    : ((imgDateEl ? imgDateEl.value : "") || "");
  let date = dateInput.trim();
  
  // 如果日期为空且不允许空日期，自动获取最新有数据的日期
  if (!date && !allowEmpty) {
    const latestDate = await getLatestAvailableDate();
    if (latestDate) {
      date = latestDate;
      // 更新日期输入框的值，让用户知道当前显示的是哪一天
      if (imgDateEl) {
        imgDateEl.value = date;
      }
    }
  }
  // 图片列表允许“日期为空”直接搜索，表示不过滤日期，展示所有真实有效图片。
  const msg = document.getElementById("img-msg");
  const grid = document.getElementById("img-grid");
  const loading = document.getElementById("img-loading");
  grid.innerHTML = "";
  if (loading) loading.style.display = "flex";
  msg.className = "muted";
  msg.innerText = date
    ? `正在加载 ${date} 的图片，请稍候...`
    : "正在加载全部图片（可能数据量较大），请稍候...";
  try {
    const ipEl2 = document.getElementById("img-search-ip");
    const channelEl2 = document.getElementById("img-search-channel");
    const taskStatusEl = document.getElementById("img-task-status");
    const ipModeEl2 = document.getElementById("img-ip-mode");
    const channelModeEl2 = document.getElementById("img-channel-mode");

    const ip = ipEl2 ? ipEl2.value.trim() : "";
    const channel = channelEl2 ? channelEl2.value.trim() : "";
    const taskStatus = taskStatusEl ? taskStatusEl.value.trim() : "";
    const ipMode = ipModeEl2 ? ipModeEl2.value : "eq";
    const channelMode = channelModeEl2 ? channelModeEl2.value : "eq";
    
    // 高级搜索参数
    const nameEqEl2 = document.getElementById("img-name-eq");
    const nameLikeEl2 = document.getElementById("img-name-like");
    const startTsGteEl2 = document.getElementById("img-start-ts-gte");
    const startTsLteEl2 = document.getElementById("img-start-ts-lte");
    const endTsGteEl2 = document.getElementById("img-end-ts-gte");
    const endTsLteEl2 = document.getElementById("img-end-ts-lte");
    const taskStatusInEl = document.getElementById("img-task-status-in");
    const statusLabelEl = document.getElementById("img-status-label");
    const statusLabelInEl = document.getElementById("img-status-label-in");
    const missingEl = document.getElementById("img-missing");

    const nameEq = nameEqEl2 ? nameEqEl2.value.trim() : "";
    const nameLike = nameLikeEl2 ? nameLikeEl2.value.trim() : "";
    const startTsGte = startTsGteEl2 ? startTsGteEl2.value.trim() : "";
    const startTsLte = startTsLteEl2 ? startTsLteEl2.value.trim() : "";
    const endTsGte = endTsGteEl2 ? endTsGteEl2.value.trim() : "";
    const endTsLte = endTsLteEl2 ? endTsLteEl2.value.trim() : "";
    const taskStatusIn = taskStatusInEl ? taskStatusInEl.value.trim() : "";
    const statusLabel = statusLabelEl ? statusLabelEl.value.trim() : "";
    const statusLabelIn = statusLabelInEl ? statusLabelInEl.value.trim() : "";
    let missing = missingEl ? missingEl.value.trim() : "";
    
    // 根据日期是否为空选择不同的API路径
    let url = date ? `/api/images/${date}` : `/api/images`;
    const params = [];
    
    // 基础搜索（向后兼容）
    if (ip && ipMode === "eq") params.push(`task_ip=${encodeURIComponent(ip)}`);
    if (ip && ipMode === "like") params.push(`task_ip__like=${encodeURIComponent(ip)}`);
    if (channel && channelMode === "eq") params.push(`task_channel=${encodeURIComponent(channel)}`);
    if (channel && channelMode === "like") params.push(`task_channel__like=${encodeURIComponent(channel)}`);
    if (taskStatus) params.push(`task_status=${encodeURIComponent(taskStatus)}`);
    
    // 高级搜索参数
    if (nameEq) params.push(`name__eq=${encodeURIComponent(nameEq)}`);
    if (nameLike) params.push(`name__like=${encodeURIComponent(nameLike)}`);
    if (startTsGte) params.push(`task_start_ts__gte=${encodeURIComponent(startTsGte)}`);
    if (startTsLte) params.push(`task_start_ts__lte=${encodeURIComponent(startTsLte)}`);
    if (endTsGte) params.push(`task_end_ts__gte=${encodeURIComponent(endTsGte)}`);
    if (endTsLte) params.push(`task_end_ts__lte=${encodeURIComponent(endTsLte)}`);
    if (taskStatusIn) params.push(`task_status__in=${encodeURIComponent(taskStatusIn)}`);
    if (statusLabel) params.push(`status_label=${encodeURIComponent(statusLabel)}`);
    if (statusLabelIn) params.push(`status_label__in=${encodeURIComponent(statusLabelIn)}`);

    // 如果用户按 IP / 通道精确搜索，但没有显式设置缺失状态过滤，则默认只显示"有截图"的记录
    if (!missing && taskStatus === "" && !taskStatusIn && !statusLabel && !statusLabelIn && (ip || channel)) {
      missing = "false";
    }
    if (missing !== "") params.push(`missing=${encodeURIComponent(missing)}`);
    
    if (params.length > 0) url += `?${params.join('&')}`;
    const res = await api(url);
    if (!res || res.detail) {
      msg.className = "info";
      const detailText = res && res.detail ? res.detail : "请确认数据库或截图目录";
      msg.innerText = `暂无图片或加载失败：${detailText}。`;
      grid.innerHTML = "";
      if (loading) loading.style.display = "none";
      return;
    }
    if (!res.items || res.items.length === 0) {
      msg.className = "info";
      msg.innerText = date
        ? `暂无图片。请确认：1）已完成截图任务；2）数据库中存在记录；3）图片位于 screenshots/${date}/ 下。`
        : "暂无图片。可以尝试指定日期或调整搜索条件后再次查询。";
      grid.innerHTML = "";
      if (loading) loading.style.display = "none";
      return;
    }
    
    // 统一封装 OCR 时间显示（字符串优先，其次时间戳）
    const getOcrDisplay = (itm) => {
      if (!itm) return "";
      const str = itm.ocr_corrected_time || itm.ocr_detected_time;
      if (str) return str;
      const ts = (itm.ocr_corrected_timestamp !== undefined && itm.ocr_corrected_timestamp !== null)
        ? itm.ocr_corrected_timestamp
        : itm.ocr_detected_timestamp;
      if (ts !== undefined && ts !== null && ts !== "") {
        return formatTimestampToBeijing(Number(ts));
      }
      return "";
    };

    // 预加载车位元数据（按 NVR IP + 通道编码），用于在图片卡片下方展示车位信息
    await ensureImageParkingSpacesLoaded();

    currentImages = res.items;

    const hasExactChannelFilter = !!channel && channelMode === "eq";
    // 只有在“没有精确通道过滤”的情况下，才更新用于构建下拉选项的基础结果，
    // 确保通道下拉始终展示该日期/IP 条件下的全部通道，而不是当前选中的单一通道。
    if (!hasExactChannelFilter) {
      baseFilterImages = res.items;
    }

    // 根据基础结果动态刷新 IP / 通道筛选下拉
    await refreshImageFilterOptionsFromResult(baseFilterImages && baseFilterImages.length > 0 ? baseFilterImages : res.items);

    msg.className = "info";
    msg.innerText = date
      ? `共 ${res.count} 张，日期：${date}`
      : `共 ${res.count} 张图片，可能包含多天数据，请结合筛选条件查看。`;

    // 展示策略简化：统一使用“扁平列表模式”，确保每张图片按正常宽高比例展示，
    // 避免复杂分组卡片把图片压扁；不再使用时间段分组模式。
    const useTimeGroupView = false;
    const useFlatListView = true;

    grid.innerHTML = "";
    if (loading) loading.style.display = "none";

    // 渲染通道变化概览
    renderChannelOverview(res.items);
    
    // 渲染图片列表（这里简化处理，完整实现需要从index.html迁移）
    // 由于代码量很大，这里先提供基本框架
    renderImages(res.items, useTimeGroupView, useFlatListView, getOcrDisplay);
  } catch (e) {
    console.error("加载图片失败:", e);
    msg.className = "alert";
    msg.innerText = `加载失败: ${e.message || e}`;
    grid.innerHTML = "";
    if (loading) loading.style.display = "none";
  }
}

/**
 * 根据当前图片结果，刷新图片列表的 IP 和通道下拉选项
 * 只展示当前筛选条件下“真正有数据”的 IP 和通道，避免出现无截图数据的通道/IP。
 */
async function refreshImageFilterOptionsFromResult(items) {
  if (!Array.isArray(items)) return;

  await ensureImageChannelMetaLoaded();

  // 刷新 IP 下拉
  const ipSelect = document.getElementById("img-search-ip");
  if (ipSelect) {
    const currentValue = ipSelect.value.trim();
    const ips = Array.from(
      new Set(
        items
          .map(it => it.task_ip)
          .filter(ip => ip && typeof ip === "string")
      )
    );
    const ipOptionsHtml = ips.map(ip => `<option value="${ip}">${ip}</option>`).join("");
    ipSelect.innerHTML = '<option value="">全部IP</option>' + ipOptionsHtml;
    if (currentValue) ipSelect.value = currentValue;
  }

  // 刷新通道下拉：下拉值/文本都是纯通道编码（c1/c2/c3/c4），
  // 具体的“通道+摄像头名称”只在结果列表里展示
  const chSelect = document.getElementById("img-search-channel");
  if (chSelect) {
    const currentValue = chSelect.value.trim();
    const channelSet = new Set();
    const channelLabels = [];
    items.forEach(it => {
      const raw = it.task_channel;
      if (!raw || typeof raw !== "string") return;
      // 从 "c1 高新四路9号枪机" 里解析出通道编码 c1
      const m = raw.trim().match(/^([cC]\d+)/);
      const code = m ? m[1].toLowerCase() : raw.trim().toLowerCase();
      if (!code) return;
      if (channelSet.has(code)) return;
      channelSet.add(code);
      channelLabels.push({ code });
    });
    const chOptionsHtml = channelLabels
      .map(({ code }) => {
        const upper = (code || "").toUpperCase();
        return `<option value="${code}">${upper}</option>`;
      })
      .join("");
    chSelect.innerHTML = '<option value="">全部通道</option>' + chOptionsHtml;
    if (currentValue) chSelect.value = currentValue;
  }
}

/**
 * 渲染图片列表
 */
function renderImages(items, useTimeGroupView, useFlatListView, getOcrDisplay) {
  const grid = document.getElementById("img-grid");
  if (!grid) return;
  
  grid.innerHTML = "";
  
  if (useFlatListView) {
    // 自适应网格缩略图模式：使用 CSS Grid 自动铺满一行
    grid.style.display = "grid";
    grid.style.gridTemplateColumns = "repeat(auto-fill, minmax(220px, 1fr))";
    grid.style.gap = "16px";
    grid.style.alignItems = "stretch";
    grid.style.justifyItems = "stretch";

    items.forEach((item, idx) => {
      const card = document.createElement("div");
      card.className = "img-thumb-card";
      card.style.cssText = `
        background:rgba(15,23,42,0.9);
        border-radius:10px;
        padding:8px;
        box-sizing:border-box;
        display:flex;
        flex-direction:column;
        gap:6px;
        height:100%;
      `;

      let url = item.url;
      if (url && !url.startsWith("http") && (url.startsWith("/api") || url.startsWith("/shots"))) {
        url = `${window.location.origin}${url}`;
      }

      // 车位变化信息
      const parkingChange = item.parking_change || null;
      const hasChange = parkingChange && parkingChange.change_count > 0;
      const changeCount = parkingChange ? (parkingChange.change_count || 0) : 0;
      const changeTime = parkingChange && parkingChange.detected_at 
        ? new Date(parkingChange.detected_at).toLocaleString('zh-CN', { 
            year: 'numeric', month: '2-digit', day: '2-digit', 
            hour: '2-digit', minute: '2-digit', second: '2-digit' 
          })
        : null;
      const snapshotId = parkingChange ? parkingChange.snapshot_id : null;
      
      // 变化徽章（右上角）
      const changeBadge = hasChange 
        ? `<div style="position:absolute; top:4px; right:4px; background:#ef4444; color:#fff; 
                       border-radius:12px; padding:2px 8px; font-size:11px; font-weight:bold;
                       box-shadow:0 2px 4px rgba(0,0,0,0.3); z-index:10; cursor:pointer;"
                onclick="event.stopPropagation(); if(${snapshotId}){ switchView('parking-changes'); setTimeout(()=>{if(typeof openParkingChangeDetail==='function')openParkingChangeDetail(${snapshotId});}, 100); }"
                title="点击查看车位变化详情">
              🔔 ${changeCount}
            </div>`
        : "";

      const imgHtml = url
        ? `<div style="position:relative; width:100%; aspect-ratio:16/9; border-radius:8px; overflow:hidden; background:#000; cursor:pointer;"
                   onclick="openPreview(${idx})">
             <img src="${url}" alt="${item.name || ""}" loading="lazy"
                  style="width:100%; height:100%; object-fit:cover; display:block;"
                  onerror="this.onerror=null; this.style.display='none';" />
             ${changeBadge}
           </div>`
        : `<div style="position:relative; width:100%; aspect-ratio:16/9; border-radius:8px; background:rgba(148,163,184,0.08);
                      display:flex; align-items:center; justify-content:center; color:#9ca3af; font-size:12px;">
             暂无图片
             ${changeBadge}
           </div>`;

      const displayName = formatImageDisplayName(item);
      const channelText = item.task_channel || "";
      const ipText = item.task_ip || "";
      // IP显示：如果有停车场名称，同时显示
      const parkingName = item.task_parking_name || "";
      const ipDisplay = parkingName ? `${ipText || '-'} (${parkingName})` : (ipText || '-');
      const ocrText = getOcrDisplay ? getOcrDisplay(item) : "";
      const parkingText = getParkingSpacesDisplay(item.task_ip || "", item.task_channel || "");
      
      // 如果有变化，添加绿色边框
      if (hasChange) {
        card.style.border = "3px solid #10b981"; // 绿色边框
        card.style.boxShadow = "0 0 8px rgba(16, 185, 129, 0.3)"; // 绿色阴影
      } else {
        // 重置样式（如果没有变化）
        card.style.border = "";
        card.style.boxShadow = "";
      }

      card.innerHTML = `
        ${imgHtml}
        <div style="display:flex; flex-direction:column; gap:2px; margin-top:4px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="font-size:12px; color:#e5e7eb; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1;"
               title="文件名：${displayName}">
            <span style="color:#9ca3af;">文件名：</span>${displayName}
            </div>
            ${hasChange ? `<div style="font-size:10px; color:#10b981; font-weight:bold; margin-left:4px; white-space:nowrap;">
                             有变化
                           </div>` : ""}
          </div>
          <div style="display:flex; flex-direction:column; gap:2px;">
            <div style="font-size:11px; color:#9ca3af; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
                 title="通道：${channelText}">
              <span style="color:#6b7280;">通道：</span>${channelText || '-'}
            </div>
            <div style="font-size:11px; color:#9ca3af; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
                 title="IP：${ipDisplay}">
              <span style="color:#6b7280;">IP：</span>${ipDisplay}
            </div>
            <div style="font-size:11px; color:#9ca3af; white-space:normal; word-break:break-all;"
                 title="车位：${parkingText || '-'}">
              <span style="color:#6b7280;">车位：</span>${parkingText || '-'}
            </div>
            ${hasChange && changeTime ? `<div style="font-size:11px; color:#10b981; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-weight:bold;"
                               title="变化时间：${changeTime}">
                           <span style="color:#6ee7b7;">变化时间：</span>${changeTime}
                         </div>` : ""}
            ${ocrText ? `<div style="font-size:11px; color:#a5b4fc; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
                               title="识别时间：${ocrText}">
                           <span style="color:#818cf8;">识别时间：</span>${ocrText}
                         </div>` : ""}
          </div>
        </div>
      `;

      grid.appendChild(card);
    });
  } else if (useTimeGroupView) {
    // 时间段分组模式：按时间段分组，每个时间段内按通道展示
    const groupsMap = new Map();
    items.forEach((item, idx) => {
      const key = `${item.task_start_ts}_${item.task_end_ts}`;
      if (!groupsMap.has(key)) {
        groupsMap.set(key, {
          start_ts: item.task_start_ts,
          end_ts: item.task_end_ts,
          items: [],
        });
      }
      groupsMap.get(key).items.push({ item, idx });
    });

    const groups = Array.from(groupsMap.values()).sort((a, b) => (a.start_ts || 0) - (b.start_ts || 0));
    const preferredChannels = ["c1", "c2", "c3", "c4"];

    groups.forEach(group => {
      const groupDiv = document.createElement("div");
      groupDiv.className = "img-time-group";

      const startStr = group.start_ts ? formatTimestampToBeijing(group.start_ts) : "";
      const endStr = group.end_ts ? formatTimestampToBeijing(group.end_ts) : "";
      const rangeText = startStr && endStr ? `${startStr} ~ ${endStr}` : "时间未知";
      const totalInGroup = group.items.length;

      groupDiv.innerHTML = `
        <div class="img-time-group-header">
          <div class="img-time-range">${rangeText}</div>
          <div class="img-time-meta">本时间段共 ${totalInGroup} 张（按通道分组展示）</div>
        </div>
        <div class="img-time-group-body"></div>
      `;

      const body = groupDiv.querySelector(".img-time-group-body");

      // 先按通道组织
      const byChannel = {};
      group.items.forEach(({ item, idx }) => {
        const chRaw = item.task_channel || "";
        const ch = String(chRaw).toLowerCase();
        if (!byChannel[ch]) byChannel[ch] = [];
        byChannel[ch].push({ item, idx });
      });

      const renderChannelCard = (data, channelLabel) => {
        const card = document.createElement("div");
        card.className = "img-channel-card";

        if (!data) {
          card.innerHTML = `
            <div class="img-channel-header">
              <div class="img-channel-title">${channelLabel}</div>
              <div class="img-badge-status img-badge-status-pending">无任务/暂无截图</div>
            </div>
            <div class="img-channel-sub">当前时间段该通道没有可用截图</div>
          `;
          return card;
        }

        const { item, idx } = data;
        const displayName = formatImageDisplayName(item);
        const displayTime = getOcrDisplay(item);
        const statusLabel = item.status_label;
        const statusDisplay = item.status_label_display || item.status_label || "正常";

        let statusClass = "img-badge-status-ok";
        if (statusLabel === "missing") statusClass = "img-badge-status-missing";
        else if (statusLabel === "failed") statusClass = "img-badge-status-failed";
        else if (statusLabel === "pending" || statusLabel === "playing") statusClass = "img-badge-status-playing";

        let imgHtml = "";
        let cardStyle = "";

        if (statusLabel === "pending" || statusLabel === "playing") {
          imgHtml = `<div style="width:100%; height:120px; background:rgba(148,163,184,0.06); display:flex; align-items:center; justify-content:center; border-radius:8px; font-size:13px; color:#9ca3af;">
            <div style="text-align:center;">
              <div style="margin-bottom:4px;">${statusDisplay || "截图中"}</div>
              <div style="font-size:11px; opacity:0.8;">请稍候...</div>
            </div>
          </div>`;
          cardStyle = "opacity:0.9;";
        } else if (statusLabel === "missing") {
          imgHtml = `<div style="width:100%; height:120px; background:rgba(251,146,60,0.08); display:flex; align-items:center; justify-content:center; border-radius:8px; font-size:13px; color:#fb923c;">文件缺失</div>`;
          cardStyle = "opacity:0.9;";
        } else if (statusLabel === "failed") {
          imgHtml = `<div style="width:100%; height:120px; background:rgba(248,113,113,0.08); display:flex; align-items:center; justify-content:center; border-radius:8px; font-size:13px; color:#fca5a5;">截图失败</div>`;
          cardStyle = "opacity:0.9;";
        } else if (!item.url || item.url === "") {
          imgHtml = `<div style="width:100%; height:120px; background:rgba(148,163,184,0.06); display:flex; align-items:center; justify-content:center; border-radius:8px; font-size:13px; color:#9ca3af;">暂无图片</div>`;
          cardStyle = "opacity:0.9;";
        } else {
          let url = item.url;
          if (!url.startsWith("http") && (url.startsWith("/api") || url.startsWith("/shots"))) {
            url = `${window.location.origin}${url}`;
          }
          imgHtml = `<img src="${url}" alt="${item.name}" loading="lazy" onclick="openPreview(${idx})" style="width:100%; height:120px; object-fit:cover; border-radius:8px; background:#000; cursor:pointer;" onerror="this.onerror=null; this.style.display='none';" />`;
        }

        let ocrText;
        if (item.ocr_status === "ok" && displayTime) {
          ocrText = `识别时间：${displayTime}`;
        } else if (item.ocr_status === "no_time") {
          ocrText = "识别时间：未识别到";
        } else {
          ocrText = "识别时间：未处理";
        }

        const statusHtml = `<span class="img-badge-status ${statusClass}">${statusDisplay || "正常"}</span>`;
        const ipText = item.task_ip ? `IP: ${item.task_parking_name ? `${item.task_ip} (${item.task_parking_name})` : item.task_ip}` : "";

        card.style.cssText = cardStyle;
        card.innerHTML = `
          <div class="img-channel-header">
            <div class="img-channel-title">${channelLabel}</div>
            <div>${statusHtml}</div>
          </div>
          ${imgHtml}
          <div class="img-channel-sub" title="${item.name || ""}">${displayName}</div>
          <div class="img-channel-ocr">${ocrText}</div>
          <div class="img-channel-footer">
            <div class="img-channel-sub" title="${ipText}">${ipText}</div>
            <div class="img-channel-actions">
              <button type="button" onclick="openPreview(${idx}); event.stopPropagation();">预览</button>
              <button type="button" onclick="copyFilename(); event.stopPropagation();">复制名称</button>
            </div>
          </div>
        `;

        return card;
      };

      if (isExactChannelFilter) {
        // 精确通道过滤下，只渲染被选中的通道，避免显示其它通道的空列
        const key = currentChannelFilter;
        const dataArr = byChannel[key];
        const data = dataArr && dataArr.length > 0 ? dataArr[0] : null;
        const label = key ? key.toUpperCase() : "通道";
        const card = renderChannelCard(data, label);
        body.appendChild(card);
      } else {
        // 固定顺序渲染 c1~c4，再渲染其他通道（如果有）
        preferredChannels.forEach(ch => {
          const key = ch.toLowerCase();
          const dataArr = byChannel[key];
          const data = dataArr && dataArr.length > 0 ? dataArr[0] : null;
          const card = renderChannelCard(data, ch.toUpperCase());
          body.appendChild(card);
        });

        // 其他通道（如自定义 c5 等）
        Object.keys(byChannel)
          .filter(ch => !preferredChannels.includes(ch))
          .forEach(ch => {
            const dataArr = byChannel[ch];
            const data = dataArr && dataArr.length > 0 ? dataArr[0] : null;
            const label = ch || "其他";
            const card = renderChannelCard(data, label);
            body.appendChild(card);
          });
      }

      grid.appendChild(groupDiv);
    });
  } else {
    // 默认模式：简单列表
    items.forEach((item, idx) => {
      const card = document.createElement("div");
      card.className = "img-card";
      let url = item.url;
      if (url && !url.startsWith("http") && (url.startsWith("/api") || url.startsWith("/shots"))) {
        url = `${window.location.origin}${url}`;
      }
      const displayName = formatImageDisplayName(item);
      card.innerHTML = `
        ${url ? `<img src="${url}" alt="${item.name}" loading="lazy" onclick="openPreview(${idx})" />` : '<div style="height:120px; display:flex; align-items:center; justify-content:center; color:#9ca3af;">暂无图片</div>'}
        <div class="img-name">${displayName}</div>
      `;
      grid.appendChild(card);
    });
  }
}

function searchImages() {
  const imgDateEl2 = document.getElementById("img-date");
  // 这里只使用图片列表自己的日期输入框，不再从基础参数配置的全局日期(#date)兜底，
  // 避免“未在图片列表填写日期却按某天过滤”的问题。
  const date = (imgDateEl2 ? imgDateEl2.value : "").trim();
  // 如果用户主动点击搜索，即使日期为空也允许搜索（allowEmpty=true）
  // 但如果没有日期，会自动使用最新日期
  loadImages(false, date || null);
}

function resetImageSearch() {
  document.getElementById("img-date").value = "";
  document.getElementById("img-search-ip").value = "";
  document.getElementById("img-search-channel").value = "";
  document.getElementById("img-task-status").value = "";
  document.getElementById("img-name-eq").value = "";
  document.getElementById("img-name-like").value = "";
  document.getElementById("img-start-ts-gte").value = "";
  document.getElementById("img-start-ts-lte").value = "";
  document.getElementById("img-end-ts-gte").value = "";
  document.getElementById("img-end-ts-lte").value = "";
  document.getElementById("img-task-status-in").value = "";
  document.getElementById("img-status-label").value = "";
  document.getElementById("img-status-label-in").value = "";
  document.getElementById("img-missing").value = "";
  document.getElementById("img-ip-mode").value = "eq";
  document.getElementById("img-channel-mode").value = "eq";
  searchImages();
}

function openPreview(idx) {
  currentIndex = idx;
  isFirstPreviewOpen = true; // 标记为首次打开
  renderPreview();
  const modal = document.getElementById("img-modal");
  if (modal) {
    modal.classList.add("open");
  }
}

/**
 * 通用：根据任意图片 URL 打开预览（供车位变化等其它模块复用）
 * 只构造一个临时的 currentImages[0]，其余逻辑复用现有预览功能。
 */
function openUrlInPreview(url, title, snapshotId) {
  if (!url) return;
  let finalUrl = url;
  if (finalUrl && !finalUrl.startsWith("http") && (finalUrl.startsWith("/api") || finalUrl.startsWith("/shots"))) {
    finalUrl = `${window.location.origin}${finalUrl}`;
  }
  
  // 构建图片对象，如果提供了 snapshotId，则包含 parking_change 信息
  const imageItem = {
    url: finalUrl,
    name: title || "",
    path: "",
    task_ip: "",
    task_channel: "",
  };
  
  // 如果有 snapshotId（且不为0），添加 parking_change 信息以便 renderImageInfo 能够获取变化详情
  if (snapshotId && snapshotId !== 0 && snapshotId !== "0") {
    imageItem.parking_change = {
      snapshot_id: parseInt(snapshotId),
      change_count: 0  // 将在 renderImageInfo 中通过 API 获取实际数量
    };
  }
  
  currentImages = [imageItem];
  currentIndex = 0;
  isFirstPreviewOpen = true;
  renderPreview();
  const modal = document.getElementById("img-modal");
  if (modal) {
    modal.classList.add("open");
  }
}

/**
 * 通用：打开“对比预览”，支持传入 1~N 张图片，
 * 典型场景：车位变化中“上一张对比图 + 当前图”。
 *
 * @param {string[]|string} urls  图片 URL 数组，或单个字符串
 * @param {string[]|string} titles 对应标题数组，可选
 */
function openComparePreview(urls, titles) {
  const list = Array.isArray(urls) ? urls.filter(Boolean) : [urls];
  if (!list.length) return;

  const titleList = Array.isArray(titles) ? titles : [titles || "图片预览"];

  currentImages = list.map((u, idx) => {
    let finalUrl = u;
    if (finalUrl && !finalUrl.startsWith("http") && (finalUrl.startsWith("/api") || finalUrl.startsWith("/shots"))) {
      finalUrl = `${window.location.origin}${finalUrl}`;
    }
    return {
      url: finalUrl,
      name: titleList[idx] || titleList[titleList.length - 1] || "",
      path: "",
      task_ip: "",
      task_channel: "",
    };
  });

  // 如果有两张图（上一张+当前图），默认先看当前图（索引1），否则看第一张
  currentIndex = currentImages.length > 1 ? 1 : 0;
  isFirstPreviewOpen = true;
  renderPreview();
  const modal = document.getElementById("img-modal");
  if (modal) {
    modal.classList.add("open");
  }
}

// 暴露给全局，方便 parking-changes 等模块调用
window.openUrlInPreview = openUrlInPreview;
window.openComparePreview = openComparePreview;

function adjustImageSize(imgEl, imgContainer) {
  if (!imgEl || !imgContainer) return;
  
  // 等待下一帧，确保DOM已更新
  setTimeout(() => {
    // 获取容器的实际尺寸
    const containerRect = imgContainer.getBoundingClientRect();
    const containerWidth = containerRect.width;
    const containerHeight = containerRect.height;
    
    // 获取图片的原始尺寸
    const imgWidth = imgEl.naturalWidth || imgEl.width;
    const imgHeight = imgEl.naturalHeight || imgEl.height;
    
    if (imgWidth > 0 && imgHeight > 0 && containerWidth > 0 && containerHeight > 0) {
      // 计算缩放比例，确保图片完整显示
      const scaleX = containerWidth / imgWidth;
      const scaleY = containerHeight / imgHeight;
      const scale = Math.min(scaleX, scaleY, 1); // 不超过1，不放大
      
      // 设置图片尺寸
      const finalWidth = imgWidth * scale;
      const finalHeight = imgHeight * scale;
      
      imgEl.style.width = `${finalWidth}px`;
      imgEl.style.height = `${finalHeight}px`;
      imgEl.style.maxWidth = `${finalWidth}px`;
      imgEl.style.maxHeight = `${finalHeight}px`;
      imgEl.style.objectFit = "contain";
      imgEl.style.objectPosition = "center";
    } else {
      // 如果无法获取尺寸，使用CSS默认样式
      imgEl.style.width = "auto";
      imgEl.style.height = "auto";
      imgEl.style.maxWidth = "100%";
      imgEl.style.maxHeight = "100%";
      imgEl.style.objectFit = "contain";
      imgEl.style.objectPosition = "center";
    }
  }, 10);
}

function renderPreview() {
  const item = currentImages[currentIndex];
  if (!item) return;
  const imgEl = document.getElementById("modal-img");
  const imgContainer = imgEl ? imgEl.closest(".modal-image-container") : null;
  
  let url = item.url;
  if (url && !url.startsWith("http") && (url.startsWith("/api") || url.startsWith("/shots"))) {
    url = `${window.location.origin}${url}`;
  }
  
  // 重置图片样式
  imgEl.classList.remove("zoomed");
  isPreviewZoomed = false;
  
  // 图片加载完成后，确保图片能够完整显示在容器内
  imgEl.onload = function() {
    adjustImageSize(imgEl, imgContainer);
  };
  
  imgEl.src = url || "";
  
  // 如果图片已经加载完成（从缓存），立即调整尺寸
  if (imgEl.complete && imgEl.naturalWidth > 0) {
    adjustImageSize(imgEl, imgContainer);
  }
  
  const displayName = formatImageDisplayName(item);
  document.getElementById("modal-title").innerHTML = `${displayName}<span class="muted-inline" style="margin-left:8px;">原始: ${item.name || ""}</span>`;

  // 渲染右侧信息面板（异步函数，需要await）
  renderImageInfo(item).catch(e => {
    console.error('渲染图片信息失败:', e);
  });
  
  isFirstPreviewOpen = false; // 重置标志
}

/**
 * 将当前预览图片切换为对应的车位检测图（*_detected.jpg）
 * 注意：后端与磁盘文件命名使用下划线（如 10_1_0_31_..._c4.jpg），若路径中含空格或 %20 会导致 404，
 *       此处以当前已加载的 imgEl.src 或 item.url 为基准，先做规范化（空格/%20 -> 下划线），再按 _cN.jpg -> _cN_detected.jpg 替换。
 */
function showDetectedImage() {
  const item = currentImages[currentIndex];
  const imgEl = document.getElementById("modal-img");
  const imgContainer = imgEl ? imgEl.closest(".modal-image-container") : null;

  if (!item || !imgEl) return;

  // 保存当前弹窗内正在显示的图片地址，用于车位图加载失败时回退
  const fallbackUrl = (imgEl.src || "").trim() || (item.url && !item.url.startsWith("http") && (item.url.startsWith("/api") || item.url.startsWith("/shots"))
    ? `${window.location.origin}${item.url}` : (item.url || ""));

  // 以当前已成功加载的图片地址为基准（避免与列表 item 不同步），无则用 item.url
  let url = (imgEl.src || "").trim() || item.url || "";
  // 一开始就把路径中的空格和 %20 全部换成下划线，避免请求 404（磁盘文件名为下划线格式）
  url = url.replace(/%20/g, "_").replace(/ /g, "_");

  // 如果已经是完整 URL，则只对路径部分做替换
  try {
    const u = new URL(url, window.location.origin);
    let path = u.pathname || "";

    // 再次规范路径（防止 pathname 解码后仍带空格）
    path = path.replace(/%20/g, "_").replace(/ /g, "_");

    // 已经是 detected 图则不再处理
    if (!/_detected\.(jpg|jpeg|png)$/i.test(path)) {
      // 将 ..._c1.jpg 替换为 ..._c1_detected.jpg（兼容路径中已是 _cN 格式）
      const replaced = path.replace(/(_c\d+)(\.(jpg|jpeg|png))$/i, "$1_detected$2");
      if (replaced !== path) {
        path = replaced;
      } else {
        // 若正则未命中（如罕见格式），在扩展名前插入 _detected
        path = path.replace(/(\.(jpg|jpeg|png))$/i, "_detected$1");
      }
    }

    u.pathname = path;
    url = u.toString();
  } catch (e) {
    let norm = url.replace(/%20/g, "_").replace(/ /g, "_");
    if (!/_detected\.(jpg|jpeg|png)$/i.test(norm)) {
      const withSuffix = norm.replace(/(_c\d+)(\.(jpg|jpeg|png))$/i, "$1_detected$2");
      norm = withSuffix !== norm ? withSuffix : norm.replace(/(\.(jpg|jpeg|png))$/i, "_detected$1");
    }
    url = norm;
    if (url && !url.startsWith("http") && (url.startsWith("/api") || url.startsWith("/shots"))) {
      url = `${window.location.origin}${url}`;
    }
  }

  imgEl.onload = function() {
    imgEl.onerror = null;
    adjustImageSize(imgEl, imgContainer);
  };
  // 车位图文件可能尚未生成，加载失败时回退到当前原图，避免红叉与 404 报错
  imgEl.onerror = function() {
    imgEl.onerror = null;
    imgEl.src = fallbackUrl || "";
    if (imgEl.complete && imgEl.naturalWidth > 0) {
      adjustImageSize(imgEl, imgContainer);
    }
  };

  imgEl.src = url || "";

  if (imgEl.complete && imgEl.naturalWidth > 0) {
    adjustImageSize(imgEl, imgContainer);
  }
}

async function renderImageInfo(item) {
  const infoEl = document.getElementById("modal-info");
  if (!infoEl) return;
  
  const displayName = formatImageDisplayName(item);
  const parkingText = getParkingSpacesDisplay(item.task_ip || "", item.task_channel || "");
  
  // 时间信息（使用任务时间段，北京时间显示）
  const startTime = item.task_start_ts ? formatTimestampToBeijing(Number(item.task_start_ts)) : "";
  const endTime = item.task_end_ts ? formatTimestampToBeijing(Number(item.task_end_ts)) : "";
  
  // 截图时间段（用于显示原来OCR识别时间的位置）
  const screenshotTimeRange = startTime && endTime ? `${startTime} ~ ${endTime}` : (startTime || endTime || "时间未知");
  
  // 状态信息
  const statusLabel = item.status_label || "";
  const statusDisplay = item.status_label_display || item.status_label || "正常";
  
  // 车位变化信息
  const parkingChange = item.parking_change || null;
  const snapshotId = parkingChange ? parkingChange.snapshot_id : null;
  
  // 获取详细变化信息（如果有快照ID）
  let changeDetails = null;
  let actualChangeCount = 0;
  if (snapshotId && snapshotId !== 0 && snapshotId !== "0") {
    try {
      const res = await api(`/api/parking_changes/${snapshotId}`);
      if (res && res.changes && Array.isArray(res.changes)) {
        changeDetails = res.changes;
        // 计算实际有变化的数量（change_type 不为空的数量）
        actualChangeCount = changeDetails.filter(c => 
          c.change_type !== null && c.change_type !== undefined
        ).length;
      }
    } catch (e) {
      console.warn('获取变化详情失败:', e);
      // 即使 API 调用失败，也设置 changeDetails 为空数组，以便显示"无变化"
      changeDetails = [];
    }
  }
  
  // 判断是否有变化：优先使用实际获取到的变化详情，其次使用 parkingChange.change_count
  const changeCount = actualChangeCount > 0 ? actualChangeCount : (parkingChange ? (parkingChange.change_count || 0) : 0);
  // 只要有 changeDetails（即使为空数组），或者有 changeCount，都应该显示变化信息部分
  const hasChange = changeCount > 0 || (changeDetails !== null);
  
  // 构建变化信息HTML
  let changeInfoHtml = "";
  // 如果有 snapshotId（且不为0）且获取到了 changeDetails（即使为空数组），都应该显示变化信息部分
  if (snapshotId && snapshotId !== 0 && snapshotId !== "0" && changeDetails !== null) {
    // 从 API 响应中获取 detected_at（如果有）
    let changeTime = "未知";
    if (changeDetails && changeDetails.length > 0 && changeDetails[0].detected_at) {
      changeTime = new Date(changeDetails[0].detected_at).toLocaleString('zh-CN', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }).replace(/\//g, '-');
    } else if (parkingChange && parkingChange.detected_at) {
      changeTime = new Date(parkingChange.detected_at).toLocaleString('zh-CN', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }).replace(/\//g, '-');
    }
    
    if (changeDetails && changeDetails.length > 0 && changeCount > 0) {
      // 有变化详情，显示变化信息
      changeInfoHtml = `
        <div style="background:rgba(16,185,129,0.1); border-left:4px solid #10b981; padding:12px; border-radius:6px; margin-top:8px;">
          <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
            <span style="font-size:18px;">🔔</span>
            <span style="color:#10b981; font-weight:bold; font-size:14px;">检测到 ${changeCount} 个车位变化</span>
          </div>
          <div style="font-size:12px; color:#9ca3af; margin-bottom:8px;">
            <span>检测时间：${changeTime}</span>
          </div>
      `;
      
      if (changeDetails.length > 0) {
      changeInfoHtml += `
        <div style="margin-top:8px;">
          <div style="font-size:12px; color:#9ca3af; margin-bottom:6px;">变化详情：</div>
          <div style="display:flex; flex-direction:column; gap:4px;">
      `;
      
      changeDetails.forEach(change => {
        // 判断是否有实际状态变化（prev_occupied 和 curr_occupied 不同）
        const hasActualStateChange = change.prev_occupied !== null && 
                                     change.prev_occupied !== undefined && 
                                     change.curr_occupied !== null && 
                                     change.curr_occupied !== undefined &&
                                     change.prev_occupied !== change.curr_occupied;
        
        // 判断是否有变化类型标记（change_type 不为空）
        const hasChangeType = change.change_type !== null && change.change_type !== undefined;
        
        // 优先根据 change_type 判断，因为这是系统检测的结果
        let typeLabel = "无变化";
        let typeColor = "#9ca3af";
        let typeIcon = "✓";
        
        if (hasChangeType) {
          // 有变化类型标记，优先显示
          if (change.change_type === "arrive") {
            typeLabel = "进车";
            typeColor = "#10b981";
            typeIcon = "⬆️";
          } else if (change.change_type === "leave") {
            typeLabel = "离开";
            typeColor = "#ef4444";
            typeIcon = "⬇️";
          } else if (change.change_type === "unknown") {
            typeLabel = "未知变化";
            typeColor = "#f59e0b";
            typeIcon = "❓";
          }
        } else if (hasActualStateChange) {
          // change_type 为 null，但状态确实变化了（可能是检测逻辑问题）
          typeLabel = "状态变化";
          typeColor = "#9ca3af";
          typeIcon = "🔄";
        } else {
          // 没有变化类型标记，且状态也没有变化
          typeLabel = "无变化";
          typeColor = "#9ca3af";
          typeIcon = "✓";
        }
        
        const prevStatus = change.prev_occupied === null || change.prev_occupied === undefined ? "未知" : (change.prev_occupied ? "有车" : "空闲");
        const currStatus = change.curr_occupied === null || change.curr_occupied === undefined ? "未知" : (change.curr_occupied ? "有车" : "空闲");
        
        changeInfoHtml += `
          <div style="background:rgba(30,41,59,0.5); padding:8px; border-radius:4px; border-left:3px solid ${typeColor};">
            <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
              <span style="font-size:14px;">${typeIcon}</span>
              <span style="color:${typeColor}; font-weight:bold; font-size:12px;">${change.space_name || `车位${change.space_id || ''}`}</span>
              <span style="color:#9ca3af; font-size:11px;">${typeLabel}</span>
            </div>
            <div style="font-size:11px; color:#9ca3af;">
              ${prevStatus} → ${currStatus}
            </div>
          </div>
        `;
      });
      
        changeInfoHtml += `
          </div>
        </div>
      `;
      }
      
      changeInfoHtml += `
        </div>
      `;
    } else {
      // 没有变化详情，或者 changeCount 为 0，显示"无变化"
      changeInfoHtml = `
        <div style="background:rgba(148,163,184,0.1); border-left:4px solid #94a3b8; padding:12px; border-radius:6px; margin-top:8px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:18px;">✓</span>
            <span style="color:#94a3b8; font-size:14px;">本时间段无车位变化</span>
          </div>
        </div>
      `;
    }
  } else {
    // 没有 snapshotId，不显示变化信息
    changeInfoHtml = "";
  }
  
  // 构建信息HTML
  const infoHtml = `
    <div style="display:flex; flex-direction:column; gap:16px;">
      <div>
        <h3 style="margin:0 0 12px 0; font-size:16px; color:var(--text); border-bottom:1px solid var(--border); padding-bottom:8px;">基本信息</h3>
        <div style="display:flex; flex-direction:column; gap:8px; font-size:13px;">
          <div><span style="color:var(--muted);">文件名：</span><span style="color:var(--text); word-break:break-all;">${displayName}</span></div>
          <div><span style="color:var(--muted);">原始文件名：</span><span style="color:var(--text); word-break:break-all;">${item.name || "-"}</span></div>
        </div>
      </div>
      
      <div>
        <h3 style="margin:0 0 12px 0; font-size:16px; color:var(--text); border-bottom:1px solid var(--border); padding-bottom:8px;">任务信息</h3>
        <div style="display:flex; flex-direction:column; gap:8px; font-size:13px;">
          ${item.task_ip ? `<div><span style="color:var(--muted);">IP地址：</span><span style="color:var(--text);">${item.task_parking_name ? `${item.task_ip} (${item.task_parking_name})` : item.task_ip}</span></div>` : ""}
          ${item.task_channel ? `<div><span style="color:var(--muted);">通道：</span><span style="color:var(--text);">${item.task_channel}</span></div>` : ""}
          ${item.task_date ? `<div><span style="color:var(--muted);">任务日期：</span><span style="color:var(--text);">${item.task_date}</span></div>` : ""}
          ${item.task_status ? `<div><span style="color:var(--muted);">任务状态：</span><span style="color:var(--text);">${(typeof statusMap !== 'undefined' ? (statusMap[item.task_status] || item.task_status) : item.task_status)}</span></div>` : ""}
        </div>
      </div>
      
      ${startTime || endTime ? `
      <div>
        <h3 style="margin:0 0 12px 0; font-size:16px; color:var(--text); border-bottom:1px solid var(--border); padding-bottom:8px;">时间信息</h3>
        <div style="display:flex; flex-direction:column; gap:8px; font-size:13px;">
          ${startTime ? `<div><span style="color:var(--muted);">开始时间：</span><span style="color:var(--text);">${startTime}</span></div>` : ""}
          ${endTime ? `<div><span style="color:var(--muted);">结束时间：</span><span style="color:var(--text);">${endTime}</span></div>` : ""}
          ${startTime && endTime ? `<div><span style="color:var(--muted);">时长：</span><span style="color:var(--text);">${formatDuration(item.task_start_ts, item.task_end_ts)}</span></div>` : ""}
        </div>
      </div>
      ` : ""}
      
      <div>
        <h3 style="margin:0 0 12px 0; font-size:16px; color:var(--text); border-bottom:1px solid var(--border); padding-bottom:8px;">车位变化信息</h3>
        <div style="display:flex; flex-direction:column; gap:8px; font-size:13px;">
          ${changeInfoHtml}
        </div>
      </div>
      
      ${statusLabel ? `
      <div>
        <h3 style="margin:0 0 12px 0; font-size:16px; color:var(--text); border-bottom:1px solid var(--border); padding-bottom:8px;">状态信息</h3>
        <div style="display:flex; flex-direction:column; gap:8px; font-size:13px;">
          <div><span style="color:var(--muted);">状态：</span><span style="color:var(--text);">${statusDisplay}</span></div>
          ${item.missing !== undefined ? `<div><span style="color:var(--muted);">文件缺失：</span><span style="color:${item.missing ? '#fca5a5' : '#86efac'};">${item.missing ? '是' : '否'}</span></div>` : ""}
        </div>
      </div>
      ` : ""}
      
      ${parkingText ? `
      <div>
        <h3 style="margin:0 0 12px 0; font-size:16px; color:var(--text); border-bottom:1px solid var(--border); padding-bottom:8px;">车位信息</h3>
        <div style="display:flex; flex-direction:column; gap:8px; font-size:13px;">
          <div><span style="color:var(--muted);">关联车位：</span><span style="color:var(--text);">${parkingText}</span></div>
        </div>
      </div>
      ` : ""}
      
      ${item.url ? `
      <div>
        <h3 style="margin:0 0 12px 0; font-size:16px; color:var(--text); border-bottom:1px solid var(--border); padding-bottom:8px;">文件信息</h3>
        <div style="display:flex; flex-direction:column; gap:8px; font-size:13px;">
          <div><span style="color:var(--muted);">图片URL：</span><a href="${item.url.startsWith('http') ? item.url : window.location.origin + item.url}" target="_blank" style="color:#60a5fa; word-break:break-all; text-decoration:underline;">${item.url}</a></div>
        </div>
      </div>
      ` : ""}
    </div>
  `;
  
  infoEl.innerHTML = infoHtml;
}

// 格式化时长
function formatDuration(startTs, endTs) {
  if (!startTs || !endTs) return "-";
  const duration = Number(endTs) - Number(startTs);
  if (duration < 0) return "-";
  const seconds = Math.floor(duration);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  if (hours > 0) {
    return `${hours}小时${minutes % 60}分钟${seconds % 60}秒`;
  } else if (minutes > 0) {
    return `${minutes}分钟${seconds % 60}秒`;
  } else {
    return `${seconds}秒`;
  }
}

// 点击图片时：左三分之一=上一张，中间=关闭，右三分之一=下一张
function toggleImageZoom(event) {
  const imgEl = document.getElementById("modal-img");
  if (!imgEl || !event) {
    closePreview();
    return;
  }

  const rect = imgEl.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const third = rect.width / 3;

  if (x < third) {
    // 点击左侧三分之一：上一张
    prevPreview();
  } else if (x > 2 * third) {
    // 点击右侧三分之一：下一张
    nextPreview();
  } else {
    // 点击中间区域：关闭预览
    closePreview();
  }
}

function closePreview() {
  const modal = document.getElementById("img-modal");
  if (modal) {
    modal.classList.remove("open");
  }
  isPreviewZoomed = false;
  isFirstPreviewOpen = false; // 重置首次打开标志
}

function prevPreview() {
  if (currentImages.length === 0) return;
  currentIndex = (currentIndex - 1 + currentImages.length) % currentImages.length;
  renderPreview();
}

function nextPreview() {
  if (currentImages.length === 0) return;
  currentIndex = (currentIndex + 1) % currentImages.length;
  renderPreview();
}

function handlePreviewKeydown(event) {
  const modal = document.getElementById("img-modal");
  if (!modal || !modal.classList.contains("open")) return;

  const key = event.key;
  if (key === "ArrowLeft") {
    event.preventDefault();
    prevPreview();
  } else if (key === "ArrowRight") {
    event.preventDefault();
    nextPreview();
  } else if (key === "Escape" || key === "Esc") {
    event.preventDefault();
    closePreview();
  }
}

// 将函数挂载到window对象，确保全局可访问
window.handlePreviewKeydown = handlePreviewKeydown;
window.showDetectedImage = showDetectedImage;

// 查看订单：打开外部订单管理系统
function viewOrderPage() {
  const url = "http://192.168.54.177:60000/#/admin/order";
  // 在新窗口/新标签打开，避免影响当前监控页面
  window.open(url, "_blank");
}

window.viewOrderPage = viewOrderPage;
window.showDetectedImage = showDetectedImage;

/**
 * 复制文件名
 */
async function copyFilename() {
  const item = currentImages[currentIndex];
  if (!item) {
    alert("无法获取图片信息");
    return;
  }
  
  // 优先使用item.name，如果不存在则尝试从path或url中提取文件名
  let filename = item.name;
  if (!filename && item.path) {
    // 从path中提取文件名
    const pathParts = item.path.split(/[/\\]/);
    filename = pathParts[pathParts.length - 1];
  }
  if (!filename && item.url) {
    // 从url中提取文件名
    try {
      const urlParts = item.url.split("/");
      filename = urlParts[urlParts.length - 1].split("?")[0]; // 移除查询参数
    } catch (e) {
      console.error("从URL提取文件名失败:", e);
    }
  }
  
  if (!filename) {
    alert("无法获取文件名，图片可能没有关联的文件");
    return;
  }
  
  try {
    await navigator.clipboard.writeText(filename);
    alert("文件名已复制：" + filename);
  } catch (e) {
    // 如果clipboard API失败，尝试使用fallback方法
    try {
      const textArea = document.createElement("textarea");
      textArea.value = filename;
      textArea.style.position = "fixed";
      textArea.style.opacity = "0";
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
      alert("文件名已复制：" + filename);
    } catch (fallbackError) {
      alert("复制失败：" + fallbackError.message);
    }
  }
}

function jumpToTaskFromImage() {
  const item = currentImages[currentIndex];
  if (!item) {
    alert("无法获取图片信息");
    return;
  }
  
  if (!item.task_date) {
    alert("该图片没有关联的任务信息，可能来自文件系统扫描");
    return;
  }
  
  // 构建URL参数
  const params = new URLSearchParams();
  params.set("view", "tasks");
  if (item.task_date) params.set("date", item.task_date);
  if (item.task_id) params.set("task_id", item.task_id);
  if (item.name) params.set("name", item.name);
  if (item.task_ip) params.set("ip", item.task_ip);
  if (item.task_channel) params.set("channel", item.task_channel);
  
  // 在新窗口打开任务列表页面
  const url = `${window.location.origin}${window.location.pathname}?${params.toString()}`;
  window.open(url, "_blank");
}

/**
 * 加载图片日期选项
 */
async function loadDateOptions() {
  try {
    const res = await api("/api/images/available_dates");
    const dates = Array.isArray(res?.dates)
      ? res.dates.map(d => (typeof d === "string" ? d : d.date)).filter(Boolean)
      : (Array.isArray(res) ? res : []);
    const datalist = document.getElementById("date-options");
    if (datalist && Array.isArray(dates)) {
      datalist.innerHTML = dates.map(d => `<option value="${d}">`).join("");
    }
  } catch (e) {
    console.warn("加载图片日期选项失败:", e);
  }
}

/**
 * 加载图片IP选项
 */
async function loadImageIpOptions() {
  // 改为使用当前已加载的图片结果刷新 IP 选项，避免额外的后端接口，
  // 并保证只展示真正有数据的 IP。
  const items = (baseFilterImages && baseFilterImages.length > 0) ? baseFilterImages : currentImages || [];
  refreshImageFilterOptionsFromResult(items).catch(e => {
    console.warn("刷新图片IP选项失败:", e);
  });
}

/**
 * 加载图片通道选项
 */
async function loadImageChannelOptions() {
  // 同样基于当前结果刷新通道选项，使通道列表和当前日期/IP/条件下的真实数据保持一致。
  const items = (baseFilterImages && baseFilterImages.length > 0) ? baseFilterImages : currentImages || [];
  refreshImageFilterOptionsFromResult(items).catch(e => {
    console.warn("刷新图片通道选项失败:", e);
  });
}

// 是否只显示有变化的图片
let imageShowChangesOnly = false;

/**
 * 切换"只显示有变化"筛选
 */
function toggleImageChangeFilter() {
  imageShowChangesOnly = !imageShowChangesOnly;
  const btn = document.getElementById("img-filter-changes");
  if (btn) {
    btn.textContent = imageShowChangesOnly ? "显示全部" : "只显示有变化";
    btn.style.background = imageShowChangesOnly ? "rgba(16, 185, 129, 0.2)" : "";
    btn.style.color = imageShowChangesOnly ? "#10b981" : "";
  }
  // 重新渲染图片列表（应用筛选）
  if (currentImages && currentImages.length > 0) {
    const filtered = imageShowChangesOnly 
      ? currentImages.filter(item => item.parking_change && item.parking_change.change_count > 0)
      : currentImages;
    const useTimeGroupView = false;
    const useFlatListView = true;
    const getOcrDisplay = () => ""; // OCR已移除
    renderImages(filtered, useTimeGroupView, useFlatListView, getOcrDisplay);
    
    // 更新消息
    const msg = document.getElementById("img-msg");
    if (msg) {
      const total = currentImages.length;
      const changed = currentImages.filter(item => item.parking_change && item.parking_change.change_count > 0).length;
      if (imageShowChangesOnly) {
        msg.textContent = `共 ${total} 张，其中 ${changed} 张有变化（已筛选）`;
      } else {
        msg.textContent = `共 ${total} 张图片`;
      }
    }
  }
}

/**
 * 渲染通道变化概览
 */
function renderChannelOverview(items) {
  const overviewEl = document.getElementById("img-channel-overview-content");
  if (!overviewEl) return;
  
  if (!Array.isArray(items) || items.length === 0) {
    overviewEl.innerHTML = '<div style="color:#9ca3af; font-size:12px; padding:8px;">暂无数据</div>';
    return;
  }
  
  // 按 IP+通道 分组
  const channelMap = new Map();
  items.forEach(item => {
    const ip = item.task_ip || "";
    const channel = item.task_channel || "";
    // 提取通道编码（如 "c1"）
    const channelCode = (channel.match(/^([cC]\d+)/) || [])[1] || channel.toLowerCase();
    const key = `${ip}|${channelCode}`;
    
    if (!channelMap.has(key)) {
      channelMap.set(key, {
        ip,
        channel: channelCode,
        channelDisplay: channel,
        parkingName: item.task_parking_name || "",
        items: [],
        hasChange: false,
        changeCount: 0,
        lastChangeTime: null,
        snapshotId: null,
      });
    }
    
    const group = channelMap.get(key);
    group.items.push(item);
    
    // 检查是否有变化
    if (item.parking_change && item.parking_change.change_count > 0) {
      group.hasChange = true;
      group.changeCount += item.parking_change.change_count;
      const changeTime = item.parking_change.detected_at 
        ? new Date(item.parking_change.detected_at)
        : null;
      if (changeTime && (!group.lastChangeTime || changeTime > group.lastChangeTime)) {
        group.lastChangeTime = changeTime;
        group.snapshotId = item.parking_change.snapshot_id;
      }
    }
  });
  
  // 转换为数组并排序（有变化的在前）
  const channels = Array.from(channelMap.values()).sort((a, b) => {
    if (a.hasChange !== b.hasChange) return b.hasChange ? 1 : -1;
    return (a.ip + a.channel).localeCompare(b.ip + b.channel);
  });
  
  // 渲染通道卡片
  overviewEl.innerHTML = channels.map(ch => {
    const changeTimeStr = ch.lastChangeTime 
      ? ch.lastChangeTime.toLocaleString('zh-CN', { 
          month: '2-digit', day: '2-digit', 
          hour: '2-digit', minute: '2-digit' 
        })
      : "";
    const bgColor = ch.hasChange ? "rgba(16, 185, 129, 0.15)" : "rgba(148, 163, 184, 0.08)";
    const borderColor = ch.hasChange ? "#10b981" : "rgba(148, 163, 184, 0.2)";
    const textColor = ch.hasChange ? "#10b981" : "#9ca3af";
    
    return `
      <div style="padding:10px; background:${bgColor}; border:2px solid ${borderColor}; border-radius:8px; cursor:pointer;"
           onclick="filterByChannel('${ch.ip}', '${ch.channel}')"
           title="点击筛选该通道的图片">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <div style="font-size:13px; font-weight:bold; color:${textColor};">
            ${ch.channel.toUpperCase()}
          </div>
          ${ch.hasChange ? `<div style="background:#ef4444; color:#fff; border-radius:10px; padding:2px 6px; font-size:10px; font-weight:bold;">
                              ${ch.changeCount}
                            </div>` : ""}
        </div>
        <div style="font-size:11px; color:#9ca3af; margin-bottom:4px;">
          ${ch.ip}
        </div>
        ${ch.hasChange ? `<div style="font-size:10px; color:#10b981; font-weight:bold;">
                            变化时间：${changeTimeStr}
                          </div>` : `<div style="font-size:10px; color:#6b7280;">无变化</div>`}
      </div>
    `;
  }).join("");
}

/**
 * 按通道筛选图片
 */
function filterByChannel(ip, channel) {
  const ipEl = document.getElementById("img-search-ip");
  const channelEl = document.getElementById("img-search-channel");
  const ipModeEl = document.getElementById("img-ip-mode");
  const channelModeEl = document.getElementById("img-channel-mode");
  
  if (ipEl) ipEl.value = ip;
  if (channelEl) channelEl.value = channel;
  if (ipModeEl) ipModeEl.value = "eq";
  if (channelModeEl) channelModeEl.value = "eq";
  
  searchImages();
}

/**
 * 切换通道概览显示/隐藏
 */
function toggleChannelOverview() {
  const overviewEl = document.getElementById("img-channel-overview");
  if (!overviewEl) return;
  
  const isVisible = overviewEl.style.display !== "none";
  overviewEl.style.display = isVisible ? "none" : "block";
  
  // 更新按钮文本
  const btn = event?.target || document.querySelector('[onclick="toggleChannelOverview()"]');
  if (btn) {
    btn.textContent = isVisible ? "通道概览 ▼" : "通道概览 ▲";
  }
}
