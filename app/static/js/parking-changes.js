/**
 * 车位变化视图
 * 使用 /api/parking_changes 列表 + 详情接口
 */

let parkingChangeSnapshots = [];
let parkingChangePage = 1;
let parkingChangePageSize = 20;

async function loadParkingChangeSnapshots() {
  const dateEl = document.getElementById("pc-date");
  const ipEl = document.getElementById("pc-search-ip");
  const ipModeEl = document.getElementById("pc-ip-mode");
  const channelEl = document.getElementById("pc-search-channel");
  const channelModeEl = document.getElementById("pc-channel-mode");
  const parkingNameEl = document.getElementById("pc-parking-name");
  const taskStatusEl = document.getElementById("pc-task-status");
  const changeTypeEl = document.getElementById("pc-change-type");
  const spaceNameEl = document.getElementById("pc-space-name");
  const startTsGteEl = document.getElementById("pc-start-ts-gte");
  const startTsLteEl = document.getElementById("pc-start-ts-lte");
  const endTsGteEl = document.getElementById("pc-end-ts-gte");
  const endTsLteEl = document.getElementById("pc-end-ts-lte");
  const taskStatusInEl = document.getElementById("pc-task-status-in");
  const nameEqEl = document.getElementById("pc-name-eq");
  const nameLikeEl = document.getElementById("pc-name-like");
  const statusLabelEl = document.getElementById("pc-status-label");
  const statusLabelInEl = document.getElementById("pc-status-label-in");
  const missingEl = document.getElementById("pc-missing");
  const msgEl = document.getElementById("pc-msg");
  const groupedView = document.getElementById("pc-grouped-view");

  const params = new URLSearchParams();
  
  // 日期
  if (dateEl && dateEl.value.trim()) params.append("date", dateEl.value.trim());
  
  // IP（精准/模糊）
  const ip = ipEl ? ipEl.value.trim() : "";
  const ipMode = ipModeEl ? ipModeEl.value : "eq";
  if (ip && ipMode === "eq") params.append("ip", ip);
  if (ip && ipMode === "like") params.append("ip__like", ip);
  
  // 通道（精准/模糊）
  const channel = channelEl ? channelEl.value.trim() : "";
  const channelMode = channelModeEl ? channelModeEl.value : "eq";
  if (channel && channelMode === "eq") params.append("channel", channel);
  if (channel && channelMode === "like") params.append("channel__like", channel);
  
  // 车场名称
  if (parkingNameEl && parkingNameEl.value.trim()) params.append("parking_name", parkingNameEl.value.trim());
  
  // 任务状态
  if (taskStatusEl && taskStatusEl.value.trim()) params.append("task_status", taskStatusEl.value.trim());
  
  // 变化类型
  if (changeTypeEl && changeTypeEl.value.trim()) params.append("change_type", changeTypeEl.value.trim());
  
  // 高级搜索参数
  if (spaceNameEl && spaceNameEl.value.trim()) params.append("space_name", spaceNameEl.value.trim());
  if (startTsGteEl && startTsGteEl.value.trim()) params.append("task_start_ts__gte", startTsGteEl.value.trim());
  if (startTsLteEl && startTsLteEl.value.trim()) params.append("task_start_ts__lte", startTsLteEl.value.trim());
  if (endTsGteEl && endTsGteEl.value.trim()) params.append("task_end_ts__gte", endTsGteEl.value.trim());
  if (endTsLteEl && endTsLteEl.value.trim()) params.append("task_end_ts__lte", endTsLteEl.value.trim());
  if (taskStatusInEl && taskStatusInEl.value.trim()) params.append("task_status__in", taskStatusInEl.value.trim());
  // 注意：分组API不支持 name__eq, name__like, status_label, status_label__in, missing 等参数
  // 这些参数是图片列表特有的，车位变化分组API不需要
  // 分组API也不支持分页参数（page, page_size）

  if (msgEl) msgEl.textContent = "正在加载车位变化数据...";
  if (groupedView) groupedView.innerHTML = "";

  try {
    // 使用新的分组API
    const res = await api(`/api/parking_changes/grouped?${params.toString()}`);
    const channels = Array.isArray(res.channels) ? res.channels : [];

    if (channels.length === 0) {
      if (msgEl) msgEl.textContent = "暂无车位变化记录，可以调整日期或筛选条件后再次查询。";
      if (groupedView) groupedView.innerHTML = "";
      // 即使没有数据，也要尝试刷新筛选选项
      await refreshParkingChangeFilterOptions();
      return;
    }

    // 计算总记录数
    const totalCount = channels.reduce((sum, ch) => sum + (ch.snapshots?.length || 0), 0);
    if (msgEl) msgEl.textContent = `共 ${channels.length} 个通道，${totalCount} 条变化记录`;
    
    // 调试：打印接收到的数据
    console.log("收到车位变化数据:", channels);
    if (channels.length > 0 && channels[0].snapshots && channels[0].snapshots.length > 0) {
      console.log("第一个快照数据示例:", channels[0].snapshots[0]);
      console.log("图片URL:", channels[0].snapshots[0].image_url);
      console.log("上一张图片URL:", channels[0].snapshots[0].prev_image_url);
    }
    
    // 渲染按通道分组的对比图
    renderParkingChangesGroupedByChannel(channels);
    
    // 加载数据后刷新筛选选项（IP 和通道下拉）
    refreshParkingChangeFilterOptionsFromGroupedChannels(channels);
  } catch (e) {
    console.error("加载车位变化列表失败:", e);
    if (msgEl) msgEl.textContent = `加载失败：${e.message || e}`;
    if (groupedView) groupedView.innerHTML = "";
    // 即使加载失败，也尝试刷新筛选选项
    await refreshParkingChangeFilterOptions();
  }
}

function renderParkingChangeList(items) {
  const listEl = document.getElementById("pc-list");
  listEl.innerHTML = "";

  items.forEach((it, idx) => {
    let url = it.image_url || "";
    if (url && !url.startsWith("http") && (url.startsWith("/api") || url.startsWith("/shots"))) {
      url = `${window.location.origin}${url}`;
    }
    const card = document.createElement("div");
    card.className = "pc-card";
    
    // 根据变化数量添加边框颜色
    const changeCount = it.change_count || 0;
    const borderColor = changeCount > 0 ? "#10b981" : "rgba(148,163,184,0.2)";
    const borderWidth = changeCount > 0 ? "2px" : "1px";
    
    card.style.cssText = `
      background:rgba(15,23,42,0.9);
      border-radius:10px;
      padding:12px;
      display:flex;
      gap:12px;
      cursor:pointer;
      border:${borderWidth} solid ${borderColor};
      transition:all 0.2s;
    `;
    card.onmouseenter = () => {
      if (changeCount > 0) {
        card.style.boxShadow = "0 0 12px rgba(16, 185, 129, 0.3)";
        card.style.transform = "translateY(-2px)";
      }
    };
    card.onmouseleave = () => {
      card.style.boxShadow = "";
      card.style.transform = "";
    };
    card.onclick = () => openParkingChangeDetail(it.id);

    // 生成图片ID用于错误处理
    const imgId = `pc-img-${it.id || idx}`;
    
    // 如果URL包含 _detected.jpg，准备回退URL（移除 _detected）
    const fallbackUrl = url && url.includes('_detected.jpg') 
      ? url.replace('_detected.jpg', '.jpg').replace('_detected.jpeg', '.jpeg').replace('_detected.png', '.png')
      : null;
    
    const thumbHtml = url
      ? `<div style="width:200px; flex-shrink:0; border-radius:8px; overflow:hidden; background:#000; position:relative;">
           <img id="${imgId}" src="${url}" alt="" loading="lazy"
                style="width:100%; height:140px; object-fit:cover; display:block; cursor:pointer;"
                onclick="event.stopPropagation(); window.openUrlInPreview && window.openUrlInPreview('${url}', '车位变化截图');"
                onerror="(function(img, fallback) {
                  if (fallback && !img.dataset.fallbackTried) {
                    img.dataset.fallbackTried = 'true';
                    img.src = fallback;
                    return;
                  }
                  img.style.display = 'none';
                  const fallbackDiv = img.parentElement.querySelector('.img-fallback');
                  if (fallbackDiv) fallbackDiv.style.display = 'flex';
                })(this, ${fallbackUrl ? `'${fallbackUrl}'` : 'null'});" />
           <div class="img-fallback" style="display:none; width:100%; height:140px; align-items:center; justify-content:center; color:#9ca3af; font-size:12px; background:rgba(148,163,184,0.12);">
             图片加载失败
           </div>
           ${changeCount > 0 ? `<div style="position:absolute; top:4px; right:4px; background:#ef4444; color:#fff; 
                                 border-radius:12px; padding:2px 8px; font-size:11px; font-weight:bold;
                                 box-shadow:0 2px 4px rgba(0,0,0,0.3); z-index:10;">
                                 🔔 ${changeCount}
                               </div>` : ""}
         </div>`
      : `<div style="width:200px; flex-shrink:0; height:140px; border-radius:8px; background:rgba(148,163,184,0.12);
                    display:flex; align-items:center; justify-content:center; color:#9ca3af; font-size:12px;">
           暂无图片
         </div>`;

    const timeText = it.detected_at || "";
    const dateText = it.task_date || "";
    const ipText = it.ip || "-";
    const chText = it.channel ? it.channel.toUpperCase() : "-";
    const parkingName = it.parking_name || "-";
    
    // 处理变化详情
    const changeDetails = it.change_details || [];
    const changeDetailsHtml = changeDetails.length > 0
      ? changeDetails.map(cd => {
          const typeLabel = cd.change_type === "arrive" ? "进车" : "离开";
          const typeColor = cd.change_type === "arrive" ? "#10b981" : "#ef4444";
          const typeIcon = cd.change_type === "arrive" ? "⬆️" : "⬇️";
          return `<span style="display:inline-block; background:${typeColor}20; color:${typeColor}; 
                             border:1px solid ${typeColor}; border-radius:4px; padding:2px 6px; 
                             font-size:11px; margin-right:4px; margin-bottom:4px;">
                    ${typeIcon} ${cd.space_name} (${typeLabel})
                  </span>`;
        }).join("")
      : '<span style="color:#9ca3af; font-size:11px;">暂无变化详情</span>';

    card.innerHTML = `
      ${thumbHtml}
      <div style="flex:1; display:flex; flex-direction:column; gap:6px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div style="font-size:13px; color:#e5e7eb;">
            <span style="color:#9ca3af;">日期：</span>${dateText || "-"}
            <span style="margin-left:10px; color:#9ca3af;">时间：</span>${timeText || "-"}
          </div>
          <div style="font-size:12px; color:#a5b4fc; font-weight:bold;">
            🔔 <strong>${it.change_count || 0}</strong> 个变化
          </div>
        </div>
        <div style="font-size:12px; color:#9ca3af;">
          <span style="color:#6b7280;">IP：</span>${ipText}
          <span style="margin-left:10px; color:#6b7280;">通道：</span><strong style="color:#e5e7eb;">${chText}</strong>
        </div>
        <div style="font-size:12px; color:#9ca3af;">
          <span style="color:#6b7280;">车场：</span>${parkingName}
        </div>
        <div style="margin-top:4px; padding-top:6px; border-top:1px solid rgba(148,163,184,0.2);">
          <div style="font-size:11px; color:#6b7280; margin-bottom:4px;">变化车位：</div>
          <div style="display:flex; flex-wrap:wrap; gap:4px;">
            ${changeDetailsHtml}
          </div>
        </div>
      </div>
    `;

    listEl.appendChild(card);
  });
}

/**
 * 在canvas上绘制跟踪区域和停车位坐标
 */
function drawParkingAreasOnCanvas(canvas, img, trackSpace, parkingSpaces) {
  const ctx = canvas.getContext("2d");
  
  // 设置canvas尺寸与图片一致
  canvas.width = img.naturalWidth || img.width;
  canvas.height = img.naturalHeight || img.height;
  
  // 绘制图片
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  
  // 绘制跟踪区域（红色）
  if (trackSpace) {
    try {
      // track_space可能是JSON字符串，尝试解析
      let trackData = trackSpace;
      if (typeof trackSpace === "string") {
        try {
          trackData = JSON.parse(trackSpace);
        } catch {
          // 如果不是JSON，可能是其他格式，暂时跳过
          trackData = null;
        }
      }
      
      if (trackData) {
        ctx.strokeStyle = "#ff0000";  // 红色
        ctx.lineWidth = 3;
        
        // 处理不同的数据格式
        if (Array.isArray(trackData)) {
          // 如果是数组，可能是多个区域
          trackData.forEach(area => {
            if (Array.isArray(area) && area.length >= 4) {
              // [x1, y1, x2, y2] 格式
              const [x1, y1, x2, y2] = area;
              ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
            } else if (area && typeof area === "object") {
              // 对象格式，可能有bbox字段
              if (area.bbox && Array.isArray(area.bbox) && area.bbox.length >= 4) {
                const [x1, y1, x2, y2] = area.bbox;
                ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
              } else if (area.x1 !== undefined && area.y1 !== undefined && area.x2 !== undefined && area.y2 !== undefined) {
                ctx.strokeRect(area.x1, area.y1, area.x2 - area.x1, area.y2 - area.y1);
              }
            }
          });
        } else if (trackData.bbox && Array.isArray(trackData.bbox) && trackData.bbox.length >= 4) {
          // 单个bbox格式
          const [x1, y1, x2, y2] = trackData.bbox;
          ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        } else if (trackData.x1 !== undefined && trackData.y1 !== undefined && trackData.x2 !== undefined && trackData.y2 !== undefined) {
          // 对象格式 {x1, y1, x2, y2}
          ctx.strokeRect(trackData.x1, trackData.y1, trackData.x2 - trackData.x1, trackData.y2 - trackData.y1);
        }
      }
    } catch (e) {
      console.warn("绘制跟踪区域失败:", e);
    }
  }
  
  // 不再绘制停车位坐标（黄色），因为 _detected.jpg 图片已经包含了检测区域标记
}

// 原始配置坐标的基准分辨率（后端配置停车位/跟踪区域时使用的分辨率）
// 当前你的配置是基于 1920x1080，这里写死为常量
const PARKING_COORD_ORIGINAL_WIDTH = 1920;
const PARKING_COORD_ORIGINAL_HEIGHT = 1080;

async function openParkingChangeDetail(snapshotId) {
  const detailPanel = document.getElementById("pc-detail");
  const detailTitle = document.getElementById("pc-detail-title");
  const detailImg = document.getElementById("pc-detail-img");
  const detailImgPrev = document.getElementById("pc-detail-img-prev");
  const detailMeta = document.getElementById("pc-detail-meta");
  const detailPrevMeta = document.getElementById("pc-detail-prev-meta");
  const detailTableBody = document.getElementById("pc-detail-table-body");

  detailTitle.textContent = "加载中...";
  detailImg.src = "";
  detailImgPrev.src = "";
  detailMeta.textContent = "";
  detailPrevMeta.textContent = "";
  detailTableBody.innerHTML = "";

  try {
    const res = await api(`/api/parking_changes/${snapshotId}`);
    const snap = res.snapshot || {};
    const prevShot = res.prev_screenshot || null;
    const drawingData = res.drawing_data || {};
    const changes = Array.isArray(res.changes) ? res.changes : [];

    // 当前图
    let url = snap.image_url || "";
    if (url && !url.startsWith("http") && (url.startsWith("/api") || url.startsWith("/shots"))) {
      url = `${window.location.origin}${url}`;
    }
    
    // 创建canvas用于绘制当前图
    const canvasContainer = detailImg.parentElement;
    let canvas = canvasContainer.querySelector("canvas");
    if (!canvas) {
      canvas = document.createElement("canvas");
      canvas.style.cssText = "max-width:100%; max-height:260px; object-fit:contain; display:block; width:100%; height:auto;";
      canvasContainer.insertBefore(canvas, detailImg);
    }
    canvas.style.display = "block";
    
    if (url) {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        // 计算缩放比例，保持图片在容器内
        const containerWidth = canvasContainer.clientWidth;
        const containerHeight = 260;
        const imgAspect = img.naturalWidth / img.naturalHeight;
        const containerAspect = containerWidth / containerHeight;
        
        let displayWidth, displayHeight;
        if (imgAspect > containerAspect) {
          displayWidth = containerWidth;
          displayHeight = containerWidth / imgAspect;
        } else {
          displayHeight = containerHeight;
          displayWidth = containerHeight * imgAspect;
        }
        
        canvas.width = displayWidth;
        canvas.height = displayHeight;
        
        const ctx = canvas.getContext("2d");
        // 绘制图片（缩放）
        ctx.drawImage(img, 0, 0, displayWidth, displayHeight);
        
        // 坐标缩放比例：配置分辨率(1920x1080) -> 实际显示尺寸
        const coordScaleX = displayWidth / PARKING_COORD_ORIGINAL_WIDTH;
        const coordScaleY = displayHeight / PARKING_COORD_ORIGINAL_HEIGHT;
        
        // 绘制跟踪区域（红色）
        if (drawingData.track_space) {
          try {
            let trackData = drawingData.track_space;
            if (typeof drawingData.track_space === "string") {
              try {
                trackData = JSON.parse(drawingData.track_space);
              } catch {
                trackData = null;
              }
            }
            
            if (trackData) {
              ctx.strokeStyle = "#ff0000";
              ctx.lineWidth = 3;
              
              if (Array.isArray(trackData)) {
                trackData.forEach(area => {
                  if (Array.isArray(area) && area.length >= 4) {
                    const [x1, y1, x2, y2] = area;
                    ctx.strokeRect(x1 * coordScaleX, y1 * coordScaleY, (x2 - x1) * coordScaleX, (y2 - y1) * coordScaleY);
                  } else if (area && typeof area === "object") {
                    if (area.bbox && Array.isArray(area.bbox) && area.bbox.length >= 4) {
                      const [x1, y1, x2, y2] = area.bbox;
                      ctx.strokeRect(x1 * coordScaleX, y1 * coordScaleY, (x2 - x1) * coordScaleX, (y2 - y1) * coordScaleY);
                    } else if (area.x1 !== undefined) {
                      ctx.strokeRect(
                        area.x1 * coordScaleX,
                        area.y1 * coordScaleY,
                        (area.x2 - area.x1) * coordScaleX,
                        (area.y2 - area.y1) * coordScaleY
                      );
                    }
                  }
                });
              } else if (trackData.bbox && Array.isArray(trackData.bbox) && trackData.bbox.length >= 4) {
                const [x1, y1, x2, y2] = trackData.bbox;
                ctx.strokeRect(x1 * coordScaleX, y1 * coordScaleY, (x2 - x1) * coordScaleX, (y2 - y1) * coordScaleY);
              } else if (trackData.x1 !== undefined) {
                ctx.strokeRect(
                  trackData.x1 * coordScaleX,
                  trackData.y1 * coordScaleY,
                  (trackData.x2 - trackData.x1) * coordScaleX,
                  (trackData.y2 - trackData.y1) * coordScaleY
                );
              }
            }
          } catch (e) {
            console.warn("绘制跟踪区域失败:", e);
          }
        }
        
        // 不再绘制停车位坐标（黄色），因为 _detected.jpg 图片已经包含了检测区域标记
      };
      img.onerror = () => {
        detailImg.src = url;
        if (canvas) canvas.style.display = "none";
        detailImg.style.display = "block";
      };
      // 点击当前图 canvas：如果有上一张，则打开“对比预览”（上一张 + 当前图）
      canvas.onclick = () => {
        if (window.openComparePreview && prevShot && prevShot.image_url) {
          let prevUrlFull = prevShot.image_url;
          if (prevUrlFull && !prevUrlFull.startsWith("http") && (prevUrlFull.startsWith("/api") || prevUrlFull.startsWith("/shots"))) {
            prevUrlFull = `${window.location.origin}${prevUrlFull}`;
          }
          window.openComparePreview(
            [prevUrlFull, url],
            ["上一张对比图", "当前变化图"]
          );
        } else if (window.openUrlInPreview) {
          window.openUrlInPreview(url, "车位变化当前图");
        }
      };
      img.src = url;
      detailImg.style.display = "none";
    } else {
      detailImg.removeAttribute("src");
      if (canvas) canvas.style.display = "none";
    }

    // 上一张图
    if (prevShot && prevShot.image_url) {
      let prevUrl = prevShot.image_url;
      if (prevUrl && !prevUrl.startsWith("http") && (prevUrl.startsWith("/api") || prevUrl.startsWith("/shots"))) {
        prevUrl = `${window.location.origin}${prevUrl}`;
      }
      
      // 为上一张图也创建canvas
      const prevCanvasContainer = detailImgPrev.parentElement;
      let prevCanvas = prevCanvasContainer.querySelector("canvas");
      if (!prevCanvas) {
        prevCanvas = document.createElement("canvas");
        prevCanvas.style.cssText = "max-width:100%; max-height:260px; object-fit:contain; display:block; width:100%; height:auto;";
        prevCanvasContainer.insertBefore(prevCanvas, detailImgPrev);
      }
      prevCanvas.style.display = "block";
      
      if (prevUrl) {
        const prevImg = new Image();
        prevImg.crossOrigin = "anonymous";
        prevImg.onload = () => {
          const containerWidth = prevCanvasContainer.clientWidth;
          const containerHeight = 260;
          const imgAspect = prevImg.naturalWidth / prevImg.naturalHeight;
          const containerAspect = containerWidth / containerHeight;
          
          let displayWidth, displayHeight;
          if (imgAspect > containerAspect) {
            displayWidth = containerWidth;
            displayHeight = containerWidth / imgAspect;
          } else {
            displayHeight = containerHeight;
            displayWidth = containerHeight * imgAspect;
          }
          
          prevCanvas.width = displayWidth;
          prevCanvas.height = displayHeight;
          
          const ctx = prevCanvas.getContext("2d");
          ctx.drawImage(prevImg, 0, 0, displayWidth, displayHeight);
          
          // 上一张图同样基于 1920x1080 配置坐标，按相同逻辑缩放
          const coordScaleX = displayWidth / PARKING_COORD_ORIGINAL_WIDTH;
          const coordScaleY = displayHeight / PARKING_COORD_ORIGINAL_HEIGHT;
          
          // 绘制跟踪区域和停车位（复用当前图的绘制逻辑）
          if (drawingData.track_space) {
            try {
              let trackData = drawingData.track_space;
              if (typeof drawingData.track_space === "string") {
                try {
                  trackData = JSON.parse(drawingData.track_space);
                } catch {
                  trackData = null;
                }
              }
              
              if (trackData) {
                ctx.strokeStyle = "#ff0000";
                ctx.lineWidth = 3;
                
                if (Array.isArray(trackData)) {
                  trackData.forEach(area => {
                    if (Array.isArray(area) && area.length >= 4) {
                      const [x1, y1, x2, y2] = area;
                      ctx.strokeRect(x1 * coordScaleX, y1 * coordScaleY, (x2 - x1) * coordScaleX, (y2 - y1) * coordScaleY);
                    } else if (area && typeof area === "object") {
                      if (area.bbox && Array.isArray(area.bbox) && area.bbox.length >= 4) {
                        const [x1, y1, x2, y2] = area.bbox;
                        ctx.strokeRect(x1 * coordScaleX, y1 * coordScaleY, (x2 - x1) * coordScaleX, (y2 - y1) * coordScaleY);
                    } else if (area.x1 !== undefined) {
                      ctx.strokeRect(
                        area.x1 * coordScaleX,
                        area.y1 * coordScaleY,
                        (area.x2 - area.x1) * coordScaleX,
                        (area.y2 - area.y1) * coordScaleY
                      );
                    }
                    }
                  });
                } else if (trackData.bbox && Array.isArray(trackData.bbox) && trackData.bbox.length >= 4) {
                  const [x1, y1, x2, y2] = trackData.bbox;
                  ctx.strokeRect(x1 * coordScaleX, y1 * coordScaleY, (x2 - x1) * coordScaleX, (y2 - y1) * coordScaleY);
                } else if (trackData.x1 !== undefined) {
                  ctx.strokeRect(
                    trackData.x1 * coordScaleX,
                    trackData.y1 * coordScaleY,
                    (trackData.x2 - trackData.x1) * coordScaleX,
                    (trackData.y2 - trackData.y1) * coordScaleY
                  );
                }
              }
            } catch (e) {
              console.warn("绘制跟踪区域失败:", e);
            }
          }
          
          // 不再绘制停车位坐标（黄色），因为 _detected.jpg 图片已经包含了检测区域标记
        };
        prevImg.onerror = () => {
          detailImgPrev.src = prevUrl;
          if (prevCanvas) prevCanvas.style.display = "none";
          detailImgPrev.style.display = "block";
        };
        // 点击上一张图 canvas：同样打开“对比预览”（上一张 + 当前图）
        prevCanvas.onclick = () => {
          if (window.openComparePreview) {
            window.openComparePreview(
              [prevUrl, url],
              ["上一张对比图", "当前变化图"]
            );
          } else if (window.openUrlInPreview) {
            window.openUrlInPreview(prevUrl, "车位变化上一张图");
          }
        };
        prevImg.src = prevUrl;
        detailImgPrev.style.display = "none";
        detailPrevMeta.textContent = "上一张对比图";
      } else {
        detailImgPrev.removeAttribute("src");
        if (prevCanvas) prevCanvas.style.display = "none";
        detailPrevMeta.textContent = "无上一张图";
      }
    } else {
      detailImgPrev.removeAttribute("src");
      detailPrevMeta.textContent = "无上一张图（第一张图）";
    }

    detailTitle.textContent = `车位变化详情（共 ${snap.change_count || changes.length} 个车位变化）`;
    detailMeta.textContent = `当前图：${snap.task_date || "-"} ${snap.detected_at || "-"}`;

    if (changes.length === 0) {
      detailTableBody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:#9ca3af; padding:8px;">暂无车位变化记录</td></tr>`;
      return;
    }

    changes.forEach(c => {
      const tr = document.createElement("tr");
      const prevText = c.prev_occupied === null || c.prev_occupied === undefined ? "未知" : (c.prev_occupied ? "有车" : "无车");
      const currText = c.curr_occupied ? "有车" : "无车";
      
      // 判断是否有实际状态变化（prev_occupied 和 curr_occupied 不同）
      const hasActualStateChange = c.prev_occupied !== null && 
                                   c.prev_occupied !== undefined && 
                                   c.curr_occupied !== null && 
                                   c.curr_occupied !== undefined &&
                                   c.prev_occupied !== c.curr_occupied;
      
      // 判断是否有变化类型标记（change_type 不为空）
      const hasChangeType = c.change_type !== null && c.change_type !== undefined;
      
      // 变化类型：arrive=进车，leave=离开，null/undefined/其他=无变化
      let changeLabel = "无变化";
      let changeIcon = "✓";
      let rowBgColor = "";
      let changeColor = "#9ca3af";
      
      // 优先根据 change_type 判断，因为这是系统检测的结果
      if (hasChangeType) {
        if (c.change_type === "arrive") {
          changeLabel = "进车";
          changeIcon = "⬆️";
          changeColor = "#10b981";
          rowBgColor = "rgba(16, 185, 129, 0.1)";  // 绿色背景
        } else if (c.change_type === "leave") {
          changeLabel = "离开";
          changeIcon = "⬇️";
          changeColor = "#ef4444";
          rowBgColor = "rgba(239, 68, 68, 0.1)";  // 红色背景
        } else if (c.change_type === "unknown") {
          changeLabel = "未知变化";
          changeIcon = "❓";
          changeColor = "#f59e0b";
          rowBgColor = "rgba(245, 158, 11, 0.1)";  // 橙色背景
        }
      } else if (hasActualStateChange) {
        // change_type 为 null，但状态确实变化了（可能是检测逻辑问题）
        changeLabel = "状态变化";
        changeIcon = "🔄";
        changeColor = "#9ca3af";
      } else {
        // 没有变化类型标记，且状态也没有变化
        changeLabel = "无变化";
        changeIcon = "✓";
        changeColor = "#9ca3af";
      }
      
      // 如果有变化类型标记，高亮整行
      if (hasChangeType) {
        tr.style.backgroundColor = rowBgColor;
        tr.style.borderLeft = `3px solid ${changeColor}`;
      }
      
      // 置信度显示
      const confidenceText = c.detection_confidence !== null && c.detection_confidence !== undefined
        ? `<span style="color:#6b7280; font-size:10px;"> (${(c.detection_confidence * 100).toFixed(0)}%)</span>`
        : "";

      tr.innerHTML = `
        <td style="font-weight:${c.change_type ? 'bold' : 'normal'}; color:${c.change_type ? changeColor : '#e5e7eb'};">
          ${c.space_name || c.space_id || "-"}
        </td>
        <td>${prevText}</td>
        <td>${currText}${confidenceText}</td>
        <td style="color:${changeColor}; font-weight:${c.change_type ? 'bold' : 'normal'};">
          ${changeIcon} ${changeLabel}
        </td>
      `;
      detailTableBody.appendChild(tr);
    });
  } catch (e) {
    detailTitle.textContent = "加载失败";
    detailMeta.textContent = e.message || e;
  }
}

function searchParkingChanges() {
  parkingChangePage = 1;
  loadParkingChangeSnapshots();
}

/**
 * 渲染按通道分组的对比图（重新设计，优化图片展示）
 */
function renderParkingChangesGroupedByChannel(channels) {
  const groupedView = document.getElementById("pc-grouped-view");
  if (!groupedView) return;
  
  groupedView.innerHTML = "";
  
  if (!channels || channels.length === 0) {
    groupedView.innerHTML = '<div style="text-align:center; color:#9ca3af; padding:40px; font-size:14px;">暂无车位变化数据，请调整筛选条件后重新搜索。</div>';
    return;
  }
  
  channels.forEach(channel => {
    const snapshots = channel.snapshots || [];
    if (snapshots.length === 0) return;
    
    // 通道卡片
    const channelCard = document.createElement("div");
    channelCard.style.cssText = `
      background:rgba(15,23,42,0.95);
      border-radius:12px;
      padding:20px;
      border:2px solid rgba(148,163,184,0.3);
      margin-bottom:24px;
      box-shadow:0 4px 12px rgba(0,0,0,0.3);
    `;
    
    const channelTitle = `${channel.channel?.toUpperCase() || ""} - ${channel.ip || ""}${channel.parking_name ? ` (${channel.parking_name})` : ""}`;
    const snapshotCount = snapshots.length;
    const totalChanges = snapshots.reduce((sum, s) => sum + (s.change_count || 0), 0);
    
    const channelConfigId = channel.channel_config_id;
    const analysisBtnId = `pc-analysis-btn-${channelConfigId || Math.random().toString(36).substr(2, 9)}`;
    
    channelCard.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; padding-bottom:12px; border-bottom:2px solid rgba(148,163,184,0.2);">
        <div>
          <h4 style="margin:0 0 4px 0; font-size:18px; color:#e5e7eb; font-weight:bold;">
            📹 ${channelTitle}
          </h4>
          <div style="font-size:12px; color:#9ca3af; margin-top:4px;">
            共 <strong style="color:#a5b4fc;">${snapshotCount}</strong> 个变化快照，<strong style="color:#10b981;">${totalChanges}</strong> 次车位变化
          </div>
        </div>
        <div style="display:flex; align-items:center; gap:12px;">
          ${channelConfigId ? `<button id="${analysisBtnId}" class="ghost" style="font-size:13px; padding:6px 16px; cursor:pointer; border-color:#a5b4fc; color:#a5b4fc;" 
                                      onclick="showChannelAnalysis(${channelConfigId}, '${channel.channel || ''}', '${channel.ip || ''}')">
                                    📊 详细分析报告
                                  </button>` : ''}
        </div>
      </div>
      <div class="pc-channel-snapshots" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(600px, 1fr)); gap:16px;">
        <!-- 动态生成对比图 -->
      </div>
      <!-- 详细分析报告模态框 -->
      <div id="pc-analysis-modal-${channelConfigId || ''}" onclick="if(event.target.id === 'pc-analysis-modal-${channelConfigId || ''}') closeAnalysisModal(${channelConfigId || 'null'})" style="display:none; position:fixed; top:0; left:0; right:0; bottom:0; z-index:1000; background:rgba(0,0,0,0.85); backdrop-filter:blur(4px); animation:fadeIn 0.2s ease-out;">
        <div onclick="event.stopPropagation()" style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); width:95%; max-width:1400px; max-height:90vh; background:linear-gradient(180deg, rgba(30,41,59,0.98), rgba(15,23,42,0.98)); border-radius:16px; border:1px solid rgba(148,163,184,0.3); box-shadow:0 20px 60px rgba(0,0,0,0.5); display:flex; flex-direction:column; overflow:hidden; animation:slideUp 0.3s ease-out;">
          <!-- 模态框头部 -->
          <div style="padding:20px 24px; border-bottom:2px solid rgba(148,163,184,0.2); display:flex; justify-content:space-between; align-items:center; background:rgba(15,23,42,0.8); flex-shrink:0;">
            <div>
              <h3 style="margin:0 0 4px 0; font-size:20px; color:#e5e7eb; font-weight:bold;">
                📊 详细分析报告
              </h3>
              <div id="pc-analysis-title-${channelConfigId || ''}" style="font-size:12px; color:#9ca3af;">
                ${channelTitle}
              </div>
            </div>
            <button onclick="closeAnalysisModal(${channelConfigId || 'null'})" style="padding:8px 16px; background:rgba(239,68,68,0.2); border:1px solid rgba(239,68,68,0.4); border-radius:8px; color:#ef4444; cursor:pointer; font-size:14px; transition:all 0.2s;" onmouseover="this.style.background='rgba(239,68,68,0.3)'" onmouseout="this.style.background='rgba(239,68,68,0.2)'">
              ✕ 关闭
            </button>
          </div>
          <!-- 可滚动内容区域 -->
          <div id="pc-analysis-${channelConfigId || ''}" style="flex:1; overflow-y:auto; padding:24px; scrollbar-width:thin; scrollbar-color:rgba(148,163,184,0.3) transparent;">
            <!-- 详细分析报告将在这里显示 -->
          </div>
        </div>
      </div>
    `;
    
    const snapshotsContainer = channelCard.querySelector(".pc-channel-snapshots");
    
    // 渲染每个快照的对比图（按时间顺序，最早的在前）
    snapshots.forEach((snap, idx) => {
      const comparisonCard = document.createElement("div");
      const hasChanges = (snap.change_count || 0) > 0;
      
      comparisonCard.style.cssText = `
        background:rgba(30,41,59,0.9);
        border-radius:10px;
        padding:16px;
        border:3px solid ${hasChanges ? "#10b981" : "rgba(148,163,184,0.3)"};
        transition:all 0.3s;
        box-shadow:0 2px 8px rgba(0,0,0,0.2);
      `;
      
      comparisonCard.onmouseenter = () => {
        if (hasChanges) {
          comparisonCard.style.boxShadow = "0 4px 16px rgba(16, 185, 129, 0.4)";
          comparisonCard.style.transform = "translateY(-2px)";
        }
      };
      comparisonCard.onmouseleave = () => {
        comparisonCard.style.boxShadow = "0 2px 8px rgba(0,0,0,0.2)";
        comparisonCard.style.transform = "";
      };
      
      const prevUrl = snap.prev_image_url || "";
      const currUrl = snap.image_url || "";
      
      // 调试：打印图片URL
      if (idx === 0) {
        console.log(`[快照 ${snap.id}] 原始URL - 当前: ${currUrl}, 上一张: ${prevUrl}`);
      }
      
      // 使用任务时间段显示（北京时间），而不是detected_at
      let detectedAt = "";
      if (snap.task_time_range && snap.task_time_range.start_ts && snap.task_time_range.end_ts) {
        // 使用任务时间段
        const startStr = formatTimestampToBeijing(Number(snap.task_time_range.start_ts));
        const endStr = formatTimestampToBeijing(Number(snap.task_time_range.end_ts));
        detectedAt = `${startStr} ~ ${endStr}`;
      } else if (snap.detected_at) {
        // 回退到detected_at（兼容旧数据）
        const d = new Date(snap.detected_at);
        if (!isNaN(d.getTime())) {
          detectedAt = d.toLocaleString('zh-CN', {
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
      }
      const changeDetails = snap.change_details || [];
      
      // 变化详情标签（更醒目的样式）
      const changeDetailsHtml = changeDetails.length > 0
        ? changeDetails.map(cd => {
            const typeLabel = cd.change_type === "arrive" ? "进车" : "离开";
            const typeColor = cd.change_type === "arrive" ? "#10b981" : "#ef4444";
            const typeIcon = cd.change_type === "arrive" ? "⬆️" : "⬇️";
            return `<span style="display:inline-block; background:${typeColor}25; color:${typeColor}; 
                               border:1.5px solid ${typeColor}; border-radius:6px; padding:4px 10px; 
                               font-size:12px; font-weight:bold; margin-right:6px; margin-bottom:6px;
                               box-shadow:0 2px 4px rgba(0,0,0,0.2);">
                      ${typeIcon} ${cd.space_name} <span style="opacity:0.9;">(${typeLabel})</span>
                    </span>`;
          }).join("")
        : '<span style="color:#9ca3af; font-size:12px; padding:8px; background:rgba(148,163,184,0.1); border-radius:4px; display:inline-block;">无变化</span>';
      
      // 处理图片URL（确保完整URL）
      let prevUrlFull = prevUrl;
      let currUrlFull = currUrl;
      
      if (prevUrl && !prevUrl.startsWith("http")) {
        if (prevUrl.startsWith("/api") || prevUrl.startsWith("/shots")) {
          prevUrlFull = `${window.location.origin}${prevUrl}`;
        } else if (prevUrl.startsWith("/")) {
          // 如果只是以 / 开头，也加上 origin
          prevUrlFull = `${window.location.origin}${prevUrl}`;
        }
      }
      
      if (currUrl && !currUrl.startsWith("http")) {
        if (currUrl.startsWith("/api") || currUrl.startsWith("/shots")) {
          currUrlFull = `${window.location.origin}${currUrl}`;
        } else if (currUrl.startsWith("/")) {
          // 如果只是以 / 开头，也加上 origin
          currUrlFull = `${window.location.origin}${currUrl}`;
        }
      }
      
      // 调试：打印处理后的URL
      if (idx === 0) {
        console.log(`[快照 ${snap.id}] 处理后URL - 当前: ${currUrlFull}, 上一张: ${prevUrlFull}`);
      }
      
      // 生成回退URL（如果 _detected.jpg 不存在，回退到原始图片）
      const prevFallbackUrl = prevUrlFull && prevUrlFull.includes('_detected.jpg') 
        ? prevUrlFull.replace('_detected.jpg', '.jpg').replace('_detected.jpeg', '.jpeg').replace('_detected.png', '.png')
        : null;
      const currFallbackUrl = currUrlFull && currUrlFull.includes('_detected.jpg') 
        ? currUrlFull.replace('_detected.jpg', '.jpg').replace('_detected.jpeg', '.jpeg').replace('_detected.png', '.png')
        : null;
      
      // 创建唯一的图片ID
      const prevImgId = `pc-prev-img-${snap.id || idx}`;
      const currImgId = `pc-curr-img-${snap.id || idx}`;
      
      comparisonCard.innerHTML = `
        <!-- 头部信息 -->
        <div style="margin-bottom:12px; padding-bottom:10px; border-bottom:1px solid rgba(148,163,184,0.2);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <div style="display:flex; align-items:center; gap:12px;">
              <div style="font-size:13px; color:#e5e7eb; font-weight:bold;">
                🕒 ${detectedAt || "时间未知"}
              </div>
              ${hasChanges ? `<div style="font-size:12px; background:#10b981; color:#fff; 
                                    border-radius:12px; padding:4px 12px; font-weight:bold;
                                    box-shadow:0 2px 4px rgba(16, 185, 129, 0.3);">
                                    🔔 ${snap.change_count} 个变化
                                  </div>` : 
                `<div style="font-size:12px; background:rgba(148,163,184,0.2); color:#9ca3af; 
                             border-radius:12px; padding:4px 12px;">
                            无变化
                          </div>`}
            </div>
            <button class="ghost" style="font-size:11px; padding:4px 10px; cursor:pointer;" 
                    onclick="openParkingChangeDetail(${snap.id || 0})">
              查看详情 →
            </button>
          </div>
          <div style="margin-top:8px;">
            <div style="font-size:11px; color:#6b7280; margin-bottom:4px;">变化车位：</div>
            <div style="display:flex; flex-wrap:wrap; gap:6px;">
              ${changeDetailsHtml}
            </div>
          </div>
        </div>
        
        <!-- 对比图区域 -->
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:12px;">
          <!-- 上一张图 -->
          <div style="background:rgba(2,6,23,0.5); border-radius:8px; padding:10px; border:2px solid rgba(148,163,184,0.2);">
            <div style="font-size:12px; color:#9ca3af; margin-bottom:8px; text-align:center; font-weight:bold;">
              ${prevUrl ? "📷 上一张（对比基准）" : "📷 第一张（无对比）"}
            </div>
            <div style="width:100%; min-height:280px; max-height:320px; border-radius:6px; overflow:hidden; background:#020617; 
                         display:flex; align-items:center; justify-content:center; position:relative; cursor:pointer;
                         border:2px solid rgba(148,163,184,0.3);"
                 onclick="handleImageClick('${prevUrlFull || currUrlFull}', '${currUrlFull || ''}', '上一张对比图', '当前变化图', ${snap.id || 0}); event.stopPropagation();"
                 title="点击查看大图或对比">
              ${prevUrlFull 
                ? `<img id="${prevImgId}" src="${prevUrlFull}" alt="上一张" loading="lazy"
                         style="max-width:100%; max-height:320px; width:auto; height:auto; object-fit:contain; display:block;"
                         onerror="handleImageError(this, ${prevFallbackUrl ? `'${prevFallbackUrl}'` : 'null'}, '${prevImgId}');" />
                   <div class="img-fallback-${prevImgId}" style="display:none; width:100%; min-height:280px; align-items:center; justify-content:center; color:#9ca3af; font-size:12px; background:rgba(148,163,184,0.12); flex-direction:column; gap:8px;">
                     <div>⚠️ 图片加载失败</div>
                     <div style="font-size:10px; opacity:0.7;">请检查图片文件是否存在</div>
                   </div>`
                : `<div style="width:100%; min-height:280px; display:flex; flex-direction:column; align-items:center; justify-content:center; color:#9ca3af; font-size:12px; gap:8px;">
                     <div style="font-size:24px;">📷</div>
                     <div>无上一张图</div>
                     <div style="font-size:10px; opacity:0.7;">这是第一张截图</div>
                   </div>`}
            </div>
          </div>
          
          <!-- 当前图 -->
          <div style="background:rgba(2,6,23,0.5); border-radius:8px; padding:10px; border:2px solid ${hasChanges ? 'rgba(16, 185, 129, 0.5)' : 'rgba(148,163,184,0.2)'};">
            <div style="font-size:12px; color:${hasChanges ? '#10b981' : '#9ca3af'}; margin-bottom:8px; text-align:center; font-weight:bold;">
              ${hasChanges ? "🔄 当前（有变化）" : "📷 当前（无变化）"}
            </div>
            <div style="width:100%; min-height:280px; max-height:320px; border-radius:6px; overflow:hidden; background:#020617; 
                         display:flex; align-items:center; justify-content:center; position:relative; cursor:pointer;
                         border:2px solid ${hasChanges ? 'rgba(16, 185, 129, 0.5)' : 'rgba(148,163,184,0.3)'};"
                 onclick="handleImageClick('${prevUrlFull || ''}', '${currUrlFull || ''}', '上一张对比图', '当前变化图', ${snap.id || 0}); event.stopPropagation();"
                 title="点击查看大图或对比">
              ${currUrlFull 
                ? `<img id="${currImgId}" src="${currUrlFull}" alt="当前" loading="lazy"
                         style="max-width:100%; max-height:320px; width:auto; height:auto; object-fit:contain; display:block;"
                         onerror="handleImageError(this, ${currFallbackUrl ? `'${currFallbackUrl}'` : 'null'}, '${currImgId}');" />
                   <div class="img-fallback-${currImgId}" style="display:none; width:100%; min-height:280px; align-items:center; justify-content:center; color:#9ca3af; font-size:12px; background:rgba(148,163,184,0.12); flex-direction:column; gap:8px;">
                     <div>⚠️ 图片加载失败</div>
                     <div style="font-size:10px; opacity:0.7;">请检查图片文件是否存在</div>
                   </div>`
                : `<div style="width:100%; min-height:280px; display:flex; flex-direction:column; align-items:center; justify-content:center; color:#9ca3af; font-size:12px; gap:8px;">
                     <div style="font-size:24px;">❌</div>
                     <div>暂无图片</div>
                     <div style="font-size:10px; opacity:0.7;">图片文件不存在</div>
                   </div>`}
            </div>
          </div>
        </div>
        
        <!-- 底部操作按钮 -->
        <div style="display:flex; justify-content:center; gap:8px; padding-top:8px; border-top:1px solid rgba(148,163,184,0.2);">
          <button class="ghost" style="font-size:11px; padding:6px 12px; cursor:pointer;" 
                  onclick="handleImageClick('${prevUrlFull || ''}', '${currUrlFull || ''}', '上一张对比图', '当前变化图', ${snap.id || 0})">
            🔍 对比查看
          </button>
          ${currUrlFull ? `<button class="ghost" style="font-size:11px; padding:6px 12px; cursor:pointer;" 
                                    onclick="window.openUrlInPreview && window.openUrlInPreview('${currUrlFull}', '当前变化图', ${snap.id || 0});">
                               🔎 查看大图
                             </button>` : ''}
          <button class="ghost" style="font-size:11px; padding:6px 12px; cursor:pointer;" 
                  onclick="openParkingChangeDetail(${snap.id || 0})">
            📋 查看详情
          </button>
        </div>
      `;
      
      snapshotsContainer.appendChild(comparisonCard);
    });
    
    groupedView.appendChild(channelCard);
  });
}

/**
 * 处理图片点击事件（对比查看或单独查看）
 */
function handleImageClick(prevUrl, currUrl, prevTitle, currTitle, snapshotId) {
  const urls = [];
  const titles = [];
  
  if (prevUrl) {
    urls.push(prevUrl);
    titles.push(prevTitle || "上一张");
  }
  if (currUrl) {
    urls.push(currUrl);
    titles.push(currTitle || "当前");
  }
  
  if (urls.length === 0) {
    alert("没有可查看的图片");
    return;
  }
  
  if (urls.length === 1) {
    // 只有一张图，单独查看，传递 snapshotId 以便显示变化信息
    if (window.openUrlInPreview) {
      // 确保 snapshotId 是数字类型
      const finalSnapshotId = snapshotId ? (typeof snapshotId === 'string' ? parseInt(snapshotId) : snapshotId) : null;
      window.openUrlInPreview(urls[0], titles[0], finalSnapshotId);
    }
  } else {
    // 多张图，对比查看（对比预览暂不支持 snapshotId，但可以通过 URL 推断）
    if (window.openComparePreview) {
      window.openComparePreview(urls, titles);
      // 如果有 snapshotId，尝试在对比预览后设置变化信息
      // 注意：对比预览使用的是不同的模态框，需要单独处理
    } else if (window.openUrlInPreview) {
      // 确保 snapshotId 是数字类型
      const finalSnapshotId = snapshotId ? (typeof snapshotId === 'string' ? parseInt(snapshotId) : snapshotId) : null;
      window.openUrlInPreview(urls[0], titles[0], finalSnapshotId);
    }
  }
}

/**
 * 处理图片加载错误
 */
function handleImageError(img, fallbackUrl, imgId) {
  if (fallbackUrl && !img.dataset.fallbackTried) {
    img.dataset.fallbackTried = 'true';
    img.src = fallbackUrl;
    return;
  }
  
  // 显示错误提示
  img.style.display = 'none';
  const fallbackDiv = img.parentElement.querySelector(`.img-fallback-${imgId}`);
  if (fallbackDiv) {
    fallbackDiv.style.display = 'flex';
  }
}

/**
 * 显示通道的详细分析报告（模态框方式）
 */
async function showChannelAnalysis(channelConfigId, channelCode, ip) {
  const modal = document.getElementById(`pc-analysis-modal-${channelConfigId}`);
  const analysisContainer = document.getElementById(`pc-analysis-${channelConfigId}`);
  const titleElement = document.getElementById(`pc-analysis-title-${channelConfigId}`);
  if (!modal || !analysisContainer) return;
  
  // 切换显示/隐藏
  const isVisible = modal.style.display !== "none";
  if (isVisible) {
    closeAnalysisModal(channelConfigId);
    return;
  }
  
  // 更新标题（如果存在）
  if (titleElement) {
    const channelCard = modal.closest('.pc-channel-card') || document.querySelector(`[id*="pc-channel-${channelConfigId}"]`);
    if (channelCard) {
      const channelTitleEl = channelCard.querySelector('h4');
      if (channelTitleEl) {
        titleElement.textContent = channelTitleEl.textContent.replace('📹 ', '');
      }
    }
  }
  
  // 显示模态框
  modal.style.display = "block";
  document.body.style.overflow = "hidden"; // 禁止背景滚动
  
  // 添加ESC键监听器
  document.addEventListener('keydown', handleEscKey);
  
  analysisContainer.innerHTML = '<div style="text-align:center; color:#9ca3af; padding:40px;"><div style="font-size:16px; margin-bottom:12px;">⏳ 正在加载分析报告...</div><div style="font-size:12px;">请稍候</div></div>';
  
  try {
    const res = await api(`/api/parking_changes/analysis/${channelConfigId}`);
    renderAnalysisReport(analysisContainer, res, channelCode, ip);
  } catch (e) {
    console.error("加载分析报告失败:", e);
    analysisContainer.innerHTML = `<div style="color:#ef4444; padding:40px; text-align:center;"><div style="font-size:16px; margin-bottom:8px;">❌ 加载失败</div><div style="font-size:12px; color:#9ca3af;">${e.message || e}</div></div>`;
  }
}

/**
 * 关闭分析报告模态框
 */
function closeAnalysisModal(channelConfigId) {
  const modal = document.getElementById(`pc-analysis-modal-${channelConfigId}`);
  if (modal) {
    modal.style.display = "none";
    document.body.style.overflow = ""; // 恢复背景滚动
  }
}

/**
 * 渲染详细分析报告
 */
function renderAnalysisReport(container, report, channelCode, ip) {
  if (!report || !report.time_sequence || report.time_sequence.length === 0) {
    container.innerHTML = '<div style="text-align:center; color:#9ca3af; padding:20px;">暂无分析数据</div>';
    return;
  }
  
  const { channel_info, time_sequence, space_layout, comparison_table, event_timeline, statistics, conclusion } = report;
  
  // 构建HTML - 使用卡片式布局，更美观易读
  let html = `
    <div style="color:#e5e7eb; max-width:100%;">
      <!-- 顶部统计卡片 -->
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:16px; margin-bottom:24px;">
        <div style="padding:16px; background:linear-gradient(135deg, rgba(34,211,238,0.15), rgba(16,185,129,0.15)); border-radius:12px; border:1px solid rgba(148,163,184,0.2);">
          <div style="font-size:12px; color:#9ca3af; margin-bottom:8px;">总车位数</div>
          <div style="font-size:24px; font-weight:bold; color:#e5e7eb;">${statistics.total_spaces}</div>
        </div>
        <div style="padding:16px; background:linear-gradient(135deg, rgba(34,211,238,0.15), rgba(16,185,129,0.15)); border-radius:12px; border:1px solid rgba(148,163,184,0.2);">
          <div style="font-size:12px; color:#9ca3af; margin-bottom:8px;">总快照数</div>
          <div style="font-size:24px; font-weight:bold; color:#e5e7eb;">${statistics.total_snapshots}</div>
        </div>
        <div style="padding:16px; background:linear-gradient(135deg, rgba(16,185,129,0.15), rgba(34,211,238,0.15)); border-radius:12px; border:1px solid rgba(16,185,129,0.3);">
          <div style="font-size:12px; color:#9ca3af; margin-bottom:8px;">车辆入场</div>
          <div style="font-size:24px; font-weight:bold; color:#10b981;">${statistics.total_entries}</div>
        </div>
        <div style="padding:16px; background:linear-gradient(135deg, rgba(239,68,68,0.15), rgba(34,211,238,0.15)); border-radius:12px; border:1px solid rgba(239,68,68,0.3);">
          <div style="font-size:12px; color:#9ca3af; margin-bottom:8px;">车辆离场</div>
          <div style="font-size:24px; font-weight:bold; color:#ef4444;">${statistics.total_exits}</div>
        </div>
      </div>
      
      <!-- 车位布局和时间顺序 - 并排显示 -->
      <div style="display:grid; grid-template-columns:1fr 2fr; gap:16px; margin-bottom:24px;">
        <!-- 车位布局卡片 -->
        <div style="padding:16px; background:rgba(15,23,42,0.6); border-radius:12px; border:1px solid rgba(148,163,184,0.2);">
          <h4 style="margin:0 0 12px 0; font-size:14px; color:#a5b4fc; font-weight:bold;">📍 车位布局</h4>
          <div style="display:flex; flex-wrap:wrap; gap:8px;">
  `;
  
  space_layout.forEach((space, idx) => {
    html += `<span style="display:inline-block; padding:6px 12px; background:rgba(148,163,184,0.2); border-radius:6px; font-size:12px; font-weight:500;">${space.space_name}</span>`;
  });
  
  html += `
          </div>
        </div>
        
        <!-- 时间顺序说明卡片 -->
        <div style="padding:16px; background:rgba(15,23,42,0.6); border-radius:12px; border:1px solid rgba(148,163,184,0.2);">
          <h4 style="margin:0 0 12px 0; font-size:14px; color:#a5b4fc; font-weight:bold;">📅 时间顺序</h4>
          <div style="max-height:200px; overflow-y:auto; scrollbar-width:thin;">
            <table style="width:100%; border-collapse:collapse; font-size:12px;">
              <thead>
                <tr style="background:rgba(148,163,184,0.1);">
                  <th style="text-align:left; padding:8px; border-bottom:1px solid rgba(148,163,184,0.2);">帧</th>
                  <th style="text-align:left; padding:8px; border-bottom:1px solid rgba(148,163,184,0.2);">时间</th>
                </tr>
              </thead>
              <tbody>
  `;
  
  time_sequence.forEach((ts, idx) => {
    const isFirst = idx === 0;
    const isLast = idx === time_sequence.length - 1;
    html += `
      <tr style="border-bottom:1px solid rgba(148,163,184,0.1);">
        <td style="padding:8px; color:${isFirst ? '#10b981' : isLast ? '#ef4444' : '#e5e7eb'}; font-weight:${isFirst || isLast ? 'bold' : 'normal'};">第${idx + 1}帧${isFirst ? '（最早）' : isLast ? '（最晚）' : ''}</td>
        <td style="padding:8px; color:#9ca3af;">${ts.display_time}</td>
      </tr>
    `;
  });
  
  html += `
              </tbody>
            </table>
          </div>
        </div>
      </div>
      
      <!-- 全车位状态对比表 - 优化显示 -->
      <div style="margin-bottom:24px; padding:20px; background:rgba(15,23,42,0.6); border-radius:12px; border:1px solid rgba(148,163,184,0.2);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
          <h4 style="margin:0; font-size:16px; color:#a5b4fc; font-weight:bold;">🔍 全车位状态对比表</h4>
          <div style="font-size:11px; color:#9ca3af;">横向滚动查看更多 →</div>
        </div>
        <div style="overflow-x:auto; overflow-y:visible; -webkit-overflow-scrolling:touch;">
          <table style="width:100%; border-collapse:collapse; font-size:12px; min-width:${Math.max(800, time_sequence.length * 120)}px;">
            <thead>
              <tr style="background:linear-gradient(90deg, rgba(148,163,184,0.15), rgba(148,163,184,0.1)); position:sticky; top:0; z-index:10;">
                <th style="text-align:left; padding:10px 12px; border:1px solid rgba(148,163,184,0.2); white-space:nowrap; background:rgba(15,23,42,0.9); font-weight:bold;">车位</th>
  `;
  
  time_sequence.forEach((ts, idx) => {
    const timeOnly = ts.display_time.split(' ')[1] || ts.display_time;
    html += `<th style="text-align:center; padding:10px 8px; border:1px solid rgba(148,163,184,0.2); white-space:nowrap; background:rgba(15,23,42,0.9); min-width:100px;">
      <div style="font-weight:bold; margin-bottom:4px;">${ts.frame_label}</div>
      <div style="font-size:10px; color:#9ca3af;">${timeOnly}</div>
    </th>`;
  });
  
  html += `
                <th style="text-align:left; padding:10px 12px; border:1px solid rgba(148,163,184,0.2); white-space:nowrap; background:rgba(15,23,42,0.9); font-weight:bold; min-width:200px;">变化总结</th>
              </tr>
            </thead>
            <tbody>
  `;
  
  comparison_table.forEach((row, rowIdx) => {
    const isEven = rowIdx % 2 === 0;
    html += `<tr style="background:${isEven ? 'rgba(148,163,184,0.05)' : 'transparent'}; transition:background 0.2s;">`;
    html += `<td style="padding:10px 12px; border:1px solid rgba(148,163,184,0.2); font-weight:bold; background:rgba(15,23,42,0.5); position:sticky; left:0; z-index:5;">${row.space_name}</td>`;
    
    let hasChange = false;
    let changeSummary = [];
    
    row.frames.forEach((frame, idx) => {
      const occupied = frame.occupied;
      const changeType = frame.change_type;
      const confidence = frame.confidence;
      
      let statusHtml = "";
      let cellBg = "";
      
      if (occupied === true) {
        statusHtml = `<span style="color:#10b981; font-weight:500;">✅ 有车</span>`;
        cellBg = "rgba(16,185,129,0.1)";
      } else if (occupied === false) {
        statusHtml = `<span style="color:#ef4444; font-weight:500;">❌ 空位</span>`;
        cellBg = "rgba(239,68,68,0.1)";
      } else {
        statusHtml = `<span style="color:#9ca3af;">-</span>`;
      }
      
      if (changeType === "arrive") {
        statusHtml += ` <span style="color:#10b981; font-size:12px; margin-left:4px;">⬆️</span>`;
        hasChange = true;
        cellBg = "rgba(16,185,129,0.2)";
        if (idx > 0) {
          const prevTime = time_sequence[idx - 1].display_time.split(' ')[1] || '';
          const currTime = time_sequence[idx].display_time.split(' ')[1] || '';
          changeSummary.push(`${prevTime}→${currTime}: 入场`);
        }
      } else if (changeType === "leave") {
        statusHtml += ` <span style="color:#ef4444; font-size:12px; margin-left:4px;">⬇️</span>`;
        hasChange = true;
        cellBg = "rgba(239,68,68,0.2)";
        if (idx > 0) {
          const prevTime = time_sequence[idx - 1].display_time.split(' ')[1] || '';
          const currTime = time_sequence[idx].display_time.split(' ')[1] || '';
          changeSummary.push(`${prevTime}→${currTime}: 离场`);
        }
      }
      
      if (confidence !== null && confidence !== undefined) {
        statusHtml += `<br/><span style="color:#6b7280; font-size:10px;">(${(confidence * 100).toFixed(0)}%)</span>`;
      }
      
      html += `<td style="padding:10px 8px; border:1px solid rgba(148,163,184,0.2); text-align:center; background:${cellBg || 'transparent'};">${statusHtml}</td>`;
    });
    
    const summaryText = hasChange 
      ? changeSummary.join("; ") || "有变化"
      : "无变化 — 车辆全程未动";
    
    html += `<td style="padding:10px 12px; border:1px solid rgba(148,163,184,0.2); font-size:11px; color:#9ca3af;">${summaryText}</td>`;
    html += `</tr>`;
  });
  
  html += `
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- 详细事件流 - 时间轴样式 -->
      <div style="margin-bottom:24px; padding:20px; background:rgba(15,23,42,0.6); border-radius:12px; border:1px solid rgba(148,163,184,0.2);">
        <h4 style="margin:0 0 16px 0; font-size:16px; color:#a5b4fc; font-weight:bold;">🔄 详细事件流（时间轴）</h4>
  `;
  
  if (event_timeline.length === 0) {
    html += `<div style="color:#9ca3af; padding:20px; text-align:center; background:rgba(148,163,184,0.05); border-radius:8px;">无事件发生</div>`;
  } else {
    html += `<div style="position:relative; padding-left:24px;">`;
    event_timeline.forEach((timeline, idx) => {
      const isLast = idx === event_timeline.length - 1;
      html += `
        <div style="position:relative; margin-bottom:${isLast ? '0' : '20px'};">
          <!-- 时间轴线条 -->
          ${!isLast ? `<div style="position:absolute; left:8px; top:32px; bottom:-20px; width:2px; background:linear-gradient(180deg, rgba(148,163,184,0.4), rgba(148,163,184,0.1));"></div>` : ''}
          <!-- 时间轴节点 -->
          <div style="position:absolute; left:0; top:4px; width:16px; height:16px; background:#a5b4fc; border-radius:50%; border:3px solid rgba(15,23,42,0.8); z-index:2;"></div>
          <!-- 事件卡片 -->
          <div style="margin-left:32px; padding:16px; background:rgba(30,41,59,0.6); border-radius:10px; border-left:4px solid #10b981; box-shadow:0 4px 12px rgba(0,0,0,0.2);">
            <div style="font-weight:bold; color:#a5b4fc; margin-bottom:12px; font-size:14px;">
              🕒 ${timeline.from_display} → ${timeline.to_display}
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:8px;">
      `;
      
      timeline.events.forEach(event => {
        const eventIcon = event.event_type === "entry" ? "⬆️" : "⬇️";
        const eventColor = event.event_type === "entry" ? "#10b981" : "#ef4444";
        const eventBg = event.event_type === "entry" ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)";
        const eventLabel = event.event_type === "entry" ? "入场" : "离场";
        html += `
          <div style="padding:8px 12px; background:${eventBg}; border-radius:6px; border:1px solid ${eventColor}40; display:inline-flex; align-items:center; gap:6px;">
            <span style="font-size:14px;">${eventIcon}</span>
            <strong style="color:${eventColor}; font-size:12px;">${event.space_name}</strong>
            <span style="color:#9ca3af; font-size:11px;">${eventLabel}</span>
          </div>
        `;
      });
      
      html += `</div></div></div>`;
    });
    html += `</div>`;
  }
  
  html += `
      </div>
      
      <!-- 结论卡片 -->
      <div style="padding:20px; background:linear-gradient(135deg, rgba(16,185,129,0.15), rgba(34,211,238,0.15)); border-radius:12px; border-left:4px solid #10b981; box-shadow:0 4px 12px rgba(0,0,0,0.2);">
        <h4 style="margin:0 0 12px 0; font-size:16px; color:#a5b4fc; font-weight:bold;">✅ 分析结论</h4>
        <div style="color:#e5e7eb; font-size:14px; line-height:1.8;">
          ${conclusion}
        </div>
      </div>
    </div>
  `;
  
  container.innerHTML = html;
}

/**
 * 从分组通道数据中刷新筛选选项
 */
function refreshParkingChangeFilterOptionsFromGroupedChannels(channels) {
  if (!Array.isArray(channels)) return;
  
  // 提取所有IP和通道
  const ipSet = new Set();
  const channelSet = new Set();
  
  channels.forEach(ch => {
    if (ch.ip) ipSet.add(ch.ip);
    if (ch.channel) channelSet.add(ch.channel);
  });
  
  // 刷新IP下拉
  const ipSelect = document.getElementById("pc-search-ip");
  if (ipSelect) {
    const currentValue = ipSelect.value.trim();
    const ipOptionsHtml = Array.from(ipSet).sort().map(ip => `<option value="${ip}">${ip}</option>`).join("");
    ipSelect.innerHTML = '<option value="">全部IP</option>' + ipOptionsHtml;
    if (currentValue) ipSelect.value = currentValue;
  }
  
  // 刷新通道下拉
  const chSelect = document.getElementById("pc-search-channel");
  if (chSelect) {
    const currentValue = chSelect.value.trim();
    const chOptionsHtml = Array.from(channelSet).sort().map(ch => {
      const upper = (ch || "").toUpperCase();
      return `<option value="${ch}">${upper}</option>`;
    }).join("");
    chSelect.innerHTML = '<option value="">全部通道</option>' + chOptionsHtml;
    if (currentValue) chSelect.value = currentValue;
  }
}

function resetParkingChangeSearch() {
  const dateEl = document.getElementById("pc-date");
  const ipEl = document.getElementById("pc-search-ip");
  const ipModeEl = document.getElementById("pc-ip-mode");
  const channelEl = document.getElementById("pc-search-channel");
  const channelModeEl = document.getElementById("pc-channel-mode");
  const parkingNameEl = document.getElementById("pc-parking-name");
  const taskStatusEl = document.getElementById("pc-task-status");
  const changeTypeEl = document.getElementById("pc-change-type");
  const spaceNameEl = document.getElementById("pc-space-name");
  const startTsGteEl = document.getElementById("pc-start-ts-gte");
  const startTsLteEl = document.getElementById("pc-start-ts-lte");
  const endTsGteEl = document.getElementById("pc-end-ts-gte");
  const endTsLteEl = document.getElementById("pc-end-ts-lte");
  const taskStatusInEl = document.getElementById("pc-task-status-in");
  const nameEqEl = document.getElementById("pc-name-eq");
  const nameLikeEl = document.getElementById("pc-name-like");
  const statusLabelEl = document.getElementById("pc-status-label");
  const statusLabelInEl = document.getElementById("pc-status-label-in");
  const missingEl = document.getElementById("pc-missing");
  
  if (dateEl) dateEl.value = "";
  if (ipEl) ipEl.value = "";
  if (ipModeEl) ipModeEl.value = "eq";
  if (channelEl) channelEl.value = "";
  if (channelModeEl) channelModeEl.value = "eq";
  if (parkingNameEl) parkingNameEl.value = "";
  if (taskStatusEl) taskStatusEl.value = "";
  if (changeTypeEl) changeTypeEl.value = "";
  if (spaceNameEl) spaceNameEl.value = "";
  if (startTsGteEl) startTsGteEl.value = "";
  if (startTsLteEl) startTsLteEl.value = "";
  if (endTsGteEl) endTsGteEl.value = "";
  if (endTsLteEl) endTsLteEl.value = "";
  if (taskStatusInEl) taskStatusInEl.value = "";
  if (nameEqEl) nameEqEl.value = "";
  if (nameLikeEl) nameLikeEl.value = "";
  if (statusLabelEl) statusLabelEl.value = "";
  if (statusLabelInEl) statusLabelInEl.value = "";
  if (missingEl) missingEl.value = "";
  
  parkingChangePage = 1;
  loadParkingChangeSnapshots();
}

/**
 * 根据当前车位变化结果，刷新车位变化页面的 IP 和通道下拉选项
 * 参考图片列表的实现，只展示当前筛选条件下"真正有数据"的 IP 和通道
 */
function refreshParkingChangeFilterOptionsFromResult(items) {
  if (!Array.isArray(items)) return;

  // 刷新 IP 下拉
  const ipSelect = document.getElementById("pc-search-ip");
  if (ipSelect) {
    const currentValue = ipSelect.value.trim();
    const ips = Array.from(
      new Set(
        items
          .map(it => it.ip)
          .filter(ip => ip && typeof ip === "string")
      )
    );
    const ipOptionsHtml = ips.map(ip => `<option value="${ip}">${ip}</option>`).join("");
    ipSelect.innerHTML = '<option value="">全部IP</option>' + ipOptionsHtml;
    if (currentValue) ipSelect.value = currentValue;
  }

  // 刷新通道下拉：下拉值/文本都是纯通道编码（c1/c2/c3/c4）
  const chSelect = document.getElementById("pc-search-channel");
  if (chSelect) {
    const currentValue = chSelect.value.trim();
    const channelSet = new Set();
    const channelLabels = [];
    items.forEach(it => {
      const raw = it.channel;
      if (!raw || typeof raw !== "string") return;
      // 从通道编码中解析出纯编码（如 "c1"）
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
 * 刷新车位变化页面的 IP 和通道下拉选项（兼容旧接口）
 * 如果当前没有数据，则尝试加载一次数据来获取选项
 */
async function refreshParkingChangeFilterOptions() {
  // 尝试使用新的分组API加载数据来获取筛选选项
  try {
    const res = await api("/api/parking_changes/grouped");
    const channels = Array.isArray(res.channels) ? res.channels : [];
    if (channels.length > 0) {
      refreshParkingChangeFilterOptionsFromGroupedChannels(channels);
      return;
    }
  } catch (e) {
    console.warn("使用分组API刷新筛选选项失败，尝试旧API:", e);
  }
  
  // 如果分组API失败，回退到旧API
  try {
    const res = await api("/api/parking_changes?page=1&page_size=1000");
    const items = Array.isArray(res.items) ? res.items : [];
    refreshParkingChangeFilterOptionsFromResult(items);
  } catch (e) {
    console.warn("刷新车位变化筛选选项失败:", e);
  }
}

// 导出到全局，方便在 main.js / HTML 中调用
// 注意：toggleAdvancedSearch 已在 tasks.js 中定义，支持通用视图（包括 "pc"）
window.loadParkingChangeSnapshots = loadParkingChangeSnapshots;
window.searchParkingChanges = searchParkingChanges;
window.resetParkingChangeSearch = resetParkingChangeSearch;
window.refreshParkingChangeFilterOptions = refreshParkingChangeFilterOptions;
window.showChannelAnalysis = showChannelAnalysis;
window.handleImageClick = handleImageClick;
window.handleImageError = handleImageError;
// toggleAdvancedSearch 已在 tasks.js 中定义，支持通用视图（包括 "pc"）

