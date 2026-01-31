/**
 * 车位变化列表视图（按通道分组，展示每个通道下各车位在不同时间段的状态）
 * 使用 /api/parking_changes/grouped-by-channel-and-space API
 */

async function loadParkingChangeList() {
  const dateEl = document.getElementById("pcl-date");
  const ipEl = document.getElementById("pcl-search-ip");
  const ipModeEl = document.getElementById("pcl-ip-mode");
  const channelEl = document.getElementById("pcl-search-channel");
  const channelModeEl = document.getElementById("pcl-channel-mode");
  const parkingNameEl = document.getElementById("pcl-parking-name");
  const taskStatusEl = document.getElementById("pcl-task-status");
  const changeTypeEl = document.getElementById("pcl-change-type");
  const spaceNameEl = document.getElementById("pcl-space-name");
  const msgEl = document.getElementById("pcl-msg");
  const groupedView = document.getElementById("pcl-grouped-view");

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
  if (parkingNameEl && parkingNameEl.value.trim()) {
    params.append("parking_name", parkingNameEl.value.trim());
  }
  
  // 任务状态
  if (taskStatusEl && taskStatusEl.value) {
    params.append("task_status", taskStatusEl.value);
  }
  
  // 变化类型
  if (changeTypeEl && changeTypeEl.value) {
    params.append("change_type", changeTypeEl.value);
  }
  
  // 车位编号
  if (spaceNameEl && spaceNameEl.value.trim()) {
    params.append("space_name", spaceNameEl.value.trim());
  }

  if (msgEl) msgEl.textContent = "正在加载...";
  if (groupedView) groupedView.innerHTML = "";

  try {
    const res = await api(`/api/parking_changes/grouped-by-channel-and-space?${params.toString()}`);
    const channels = Array.isArray(res.channels) ? res.channels : [];

    if (channels.length === 0) {
      if (msgEl) msgEl.textContent = "暂无车位变化记录，可以调整日期或筛选条件后再次查询。";
      if (groupedView) groupedView.innerHTML = "";
      return;
    }

    // 将所有通道下的车位合并成一个列表
    let allSpaces = [];
    channels.forEach(ch => {
      if (ch.spaces && ch.spaces.length > 0) {
        ch.spaces.forEach(space => {
          // 为每个车位添加通道信息（用于显示，但不作为分组）
          allSpaces.push({
            ...space,
            channel: ch.channel,
            ip: ch.ip,
            parking_name: ch.parking_name
          });
        });
      }
    });
    
    // 按车位名称排序
    allSpaces.sort((a, b) => {
      const nameA = a.space_name || '';
      const nameB = b.space_name || '';
      return nameA.localeCompare(nameB, 'zh-CN');
    });
    
    // 计算总记录数
    const totalRecords = allSpaces.reduce((sum, sp) => sum + (sp.status_timeline?.length || 0), 0);
    if (msgEl) msgEl.textContent = `共 ${allSpaces.length} 个车位，${totalRecords} 条状态记录`;
    
    // 渲染车位列表（不按通道分组）
    renderParkingSpacesList(allSpaces);
    
  } catch (e) {
    console.error("加载车位变化列表失败:", e);
    if (msgEl) msgEl.textContent = `加载失败：${e.message || e}`;
    if (groupedView) groupedView.innerHTML = "";
  }
}

/**
 * 渲染车位列表（直接展示所有车位及其时间线状态，不按通道分组）
 */
function renderParkingSpacesList(spaces) {
  const container = document.getElementById("pcl-grouped-view");
  if (!container) return;
  
  if (spaces.length === 0) {
    container.innerHTML = '<div style="text-align:center; color:#9ca3af; padding:40px;">暂无数据</div>';
    return;
  }
  
  let html = '<div style="display:flex; flex-direction:column; gap:16px;">';
  
  spaces.forEach((space, spaceIndex) => {
    const spaceName = space.space_name || `车位${space.space_id || ''}`;
    const timeline = space.status_timeline || [];
    const channelInfo = space.channel ? `📹 ${space.channel}` : '';
    const ipInfo = space.ip ? ` | ${space.ip}` : '';
    const parkingInfo = space.parking_name ? ` | ${space.parking_name}` : '';
    
    // 统计有变化和无变化的数量
    const withChangeCount = timeline.filter(s => s.has_change === true).length;
    const withoutChangeCount = timeline.filter(s => s.has_change === false).length;
    
    // 生成唯一的ID用于折叠/展开
    const spaceCardId = `space-card-${spaceIndex}`;
    const spaceContentId = `space-content-${spaceIndex}`;
    
    html += `
      <div id="${spaceCardId}" style="background:rgba(15,23,42,0.6); border-radius:12px; border:1px solid rgba(148,163,184,0.2); padding:20px; box-shadow:0 4px 12px rgba(0,0,0,0.1);">
        <div style="display:flex; justify-content:space-between; align-items:center; cursor:pointer;" onclick="toggleSpaceCard('${spaceContentId}', '${spaceCardId}')">
          <div style="flex:1;">
            <h4 style="margin:0 0 4px 0; font-size:18px; color:#e5e7eb; font-weight:bold; display:flex; align-items:center; gap:8px;">
              <span id="${spaceCardId}-icon" style="transition:transform 0.3s;">▶</span>
              🅿️ ${spaceName}
            </h4>
            ${channelInfo || ipInfo || parkingInfo ? `
              <div style="font-size:12px; color:#9ca3af; margin-top:4px;">
                ${channelInfo}${ipInfo}${parkingInfo}
              </div>
            ` : ''}
          </div>
          <div style="font-size:14px; color:#a5b4fc; text-align:right;">
            <div>共 <strong style="color:#10b981;">${timeline.length}</strong> 个时间段</div>
            ${withChangeCount > 0 ? `<div style="color:#10b981; font-size:12px; margin-top:4px;">🔔 ${withChangeCount} 个有变化</div>` : ''}
            ${withoutChangeCount > 0 ? `<div style="color:#94a3b8; font-size:12px; margin-top:2px;">✓ ${withoutChangeCount} 个无变化</div>` : ''}
          </div>
        </div>
        <div id="${spaceContentId}" style="display:none; margin-top:16px; padding-top:16px; border-top:2px solid rgba(148,163,184,0.2);">
    `;
    
    if (timeline.length === 0) {
      html += '<div style="color:#9ca3af; padding:12px; text-align:center; font-size:13px;">暂无状态记录</div>';
    } else {
      // 按时间段分组：有变化和无变化
      const timeRangesWithChange = [];
      const timeRangesWithoutChange = [];
      
      timeline.forEach((status) => {
        // 使用任务时间段显示（北京时间）
        let timeDisplay = "-";
        let timeKey = "";
        if (status.time) {
          if (typeof status.time === 'object' && status.time.start_ts && status.time.end_ts) {
            // 使用任务时间段
            const startStr = formatTimestampToBeijing(Number(status.time.start_ts));
            const endStr = formatTimestampToBeijing(Number(status.time.end_ts));
            timeDisplay = `${startStr} ~ ${endStr}`;
            timeKey = `${status.time.start_ts}_${status.time.end_ts}`;
          } else if (typeof status.time === 'string') {
            // 兼容旧格式（ISO字符串）
            const d = new Date(status.time);
            if (!isNaN(d.getTime())) {
              timeDisplay = d.toLocaleString('zh-CN', {
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
        }
        
        // 判断是否有变化：优先使用 has_change 字段，如果没有则通过 change_type 判断
        const hasChange = status.has_change === true || (status.change_type !== null && status.change_type !== undefined);
        const occupied = status.occupied;
        const prevOccupied = status.prev_occupied;
        const changeType = status.change_type;
        const confidence = status.confidence ? `(${(status.confidence * 100).toFixed(0)}%)` : "";
        const imageUrl = status.image_url || "";
        
        const statusColor = occupied ? "#10b981" : "#ef4444";
        const statusText = occupied ? "有车" : "空闲";
        const statusIcon = occupied ? "🚗" : "🅿️";
        
        // 变化类型和描述
        let changeIcon = "";
        let changeDescription = "";
        if (changeType === "arrive") {
          changeIcon = "⬆️";
          changeDescription = "进车";
        } else if (changeType === "leave") {
          changeIcon = "⬇️";
          changeDescription = "离开";
        } else if (changeType === "unknown") {
          changeIcon = "❓";
          changeDescription = "未知变化";
        }
        
        // 构建变化详情文本
        let changeDetailText = "";
        if (hasChange && prevOccupied !== null && prevOccupied !== undefined) {
          const prevText = prevOccupied ? "有车" : "空闲";
          const currText = occupied ? "有车" : "空闲";
          changeDetailText = `${prevText} → ${currText}`;
        } else if (hasChange) {
          changeDetailText = `当前状态：${statusText}`;
        }
        
        const timeRangeData = {
          timeDisplay,
          timeKey,
          occupied,
          prevOccupied,
          changeType,
          changeDescription,
          changeDetailText,
          confidence,
          imageUrl,
          statusColor,
          statusText,
          statusIcon,
          changeIcon,
          hasChange
        };
        
        if (hasChange) {
          timeRangesWithChange.push(timeRangeData);
        } else {
          timeRangesWithoutChange.push(timeRangeData);
        }
      });
      
      // 显示有变化的时间段
      if (timeRangesWithChange.length > 0) {
        html += `
          <div style="margin-bottom:16px;">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px; padding:8px; background:rgba(16,185,129,0.1); border-radius:6px; border-left:4px solid #10b981;">
              <span style="font-size:16px;">🔔</span>
              <span style="color:#10b981; font-weight:bold; font-size:14px;">有变化的时间段（${timeRangesWithChange.length}个）</span>
            </div>
            <div style="display:flex; flex-direction:column; gap:8px;">
        `;
        
        timeRangesWithChange.forEach((tr) => {
          // 构建更详细的变化信息
          let changeInfoText = "";
          if (tr.prevOccupied !== null && tr.prevOccupied !== undefined) {
            const prevText = tr.prevOccupied ? "有车" : "空闲";
            const currText = tr.occupied ? "有车" : "空闲";
            changeInfoText = `从 ${prevText} 变为 ${currText}`;
          } else if (tr.changeType === "arrive") {
            changeInfoText = "车辆驶入（进车）";
          } else if (tr.changeType === "leave") {
            changeInfoText = "车辆离开";
          } else {
            changeInfoText = `当前状态：${tr.statusText}`;
          }
          
          html += `
            <div style="padding:12px; background:rgba(16,185,129,0.15); border-radius:6px; border-left:4px solid #10b981; border:2px solid rgba(16,185,129,0.3);">
              <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;">
                <div style="flex:1; min-width:200px;">
                  <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px; flex-wrap:wrap;">
                    <span style="font-size:16px;">${tr.statusIcon}</span>
                    <span style="color:${tr.statusColor}; font-weight:bold; font-size:14px;">${tr.statusText}</span>
                    ${tr.changeIcon ? `<span style="font-size:14px;" title="${tr.changeDescription}">${tr.changeIcon}</span>` : ''}
                    ${tr.changeDescription ? `<span style="color:#10b981; font-weight:bold; font-size:13px;">${tr.changeDescription}</span>` : ''}
                    ${tr.confidence ? `<span style="color:#9ca3af; font-size:12px;">${tr.confidence}</span>` : ''}
                    <span style="background:#10b981; color:white; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:bold; margin-left:4px;">有变化</span>
                  </div>
                  <div style="color:#10b981; font-size:12px; margin-bottom:4px; font-weight:500; background:rgba(16,185,129,0.1); padding:4px 8px; border-radius:4px; display:inline-block;">
                    📊 ${changeInfoText}
                  </div>
                  <div style="color:#9ca3af; font-size:12px; margin-top:4px;">
                    🕒 ${tr.timeDisplay}
                  </div>
                </div>
                ${tr.imageUrl ? `
                  <button onclick="openImageModal('${tr.imageUrl}', '${spaceName} - ${tr.timeDisplay}')" 
                          style="padding:6px 12px; background:rgba(16,185,129,0.2); border:1px solid rgba(16,185,129,0.4); border-radius:6px; color:#10b981; cursor:pointer; font-size:12px; white-space:nowrap; font-weight:bold;">
                    📷 查看
                  </button>
                ` : ''}
              </div>
            </div>
          `;
        });
        
        html += `
            </div>
          </div>
        `;
      }
      
      // 显示无变化的时间段（合并显示，减少冗余）
      if (timeRangesWithoutChange.length > 0) {
        // 合并连续的无变化时间段
        const mergedRanges = [];
        let currentRange = null;
        
        timeRangesWithoutChange.forEach((tr) => {
          if (!currentRange) {
            currentRange = {
              start: tr.timeDisplay.split(' ~ ')[0],
              end: tr.timeDisplay.split(' ~ ')[1],
              count: 1,
              occupied: tr.occupied,
              statusText: tr.statusText,
              statusIcon: tr.statusIcon
            };
          } else {
            // 检查是否可以合并（连续的时间段）
            const currentEnd = currentRange.end;
            const nextStart = tr.timeDisplay.split(' ~ ')[0];
            
            // 如果下一个时间段的开始时间等于当前时间段的结束时间（或接近），可以合并
            if (currentEnd === nextStart || Math.abs(new Date(currentEnd.replace(/-/g, '/')).getTime() - new Date(nextStart.replace(/-/g, '/')).getTime()) < 60000) {
              currentRange.end = tr.timeDisplay.split(' ~ ')[1];
              currentRange.count++;
            } else {
              // 不能合并，保存当前范围，开始新范围
              mergedRanges.push(currentRange);
              currentRange = {
                start: tr.timeDisplay.split(' ~ ')[0],
                end: tr.timeDisplay.split(' ~ ')[1],
                count: 1,
                occupied: tr.occupied,
                statusText: tr.statusText,
                statusIcon: tr.statusIcon
              };
            }
          }
        });
        
        if (currentRange) {
          mergedRanges.push(currentRange);
        }
        
        html += `
          <div>
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px; padding:8px; background:rgba(148,163,184,0.1); border-radius:6px; border-left:4px solid #94a3b8;">
              <span style="font-size:16px;">✓</span>
              <span style="color:#94a3b8; font-weight:bold; font-size:14px;">无变化的时间段（${timeRangesWithoutChange.length}个）</span>
            </div>
            <div style="display:flex; flex-direction:column; gap:6px;">
        `;
        
        mergedRanges.forEach((mr) => {
          const rangeDisplay = mr.count === 1 
            ? `${mr.start} ~ ${mr.end}`
            : `${mr.start} ~ ${mr.end} (连续${mr.count}个时间段)`;
          
          html += `
            <div style="padding:10px; background:rgba(30,41,59,0.3); border-radius:6px; border-left:3px solid #94a3b8; opacity:0.7;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:14px;">${mr.statusIcon}</span>
                <span style="color:#94a3b8; font-size:13px;">${mr.statusText}</span>
                <span style="color:#9ca3af; font-size:11px; margin-left:8px;">🕒 ${rangeDisplay}</span>
              </div>
            </div>
          `;
        });
        
        html += `
            </div>
          </div>
        `;
      }
    }
    
    html += `
        </div>
      </div>
    `;
  });
  
  html += '</div>';
  container.innerHTML = html;
}

/**
 * 切换车位卡片的展开/折叠状态
 */
function toggleSpaceCard(contentId, cardId) {
  const content = document.getElementById(contentId);
  const icon = document.getElementById(cardId + '-icon');
  
  if (content && icon) {
    if (content.style.display === 'none') {
      content.style.display = 'block';
      icon.textContent = '▼';
      icon.style.transform = 'rotate(0deg)';
    } else {
      content.style.display = 'none';
      icon.textContent = '▶';
      icon.style.transform = 'rotate(0deg)';
    }
  }
}

/**
 * 渲染按车位分组的车位变化列表（保留旧函数以兼容）
 */
function renderParkingChangesGroupedBySpace(spaces) {
  const container = document.getElementById("pcl-grouped-view");
  if (!container) return;
  
  if (spaces.length === 0) {
    container.innerHTML = '<div style="text-align:center; color:#9ca3af; padding:40px;">暂无数据</div>';
    return;
  }
  
  let html = '<div style="display:flex; flex-direction:column; gap:20px;">';
  
  spaces.forEach(space => {
    const spaceName = space.space_name || `车位${space.space_id || ''}`;
    const channelInfo = space.channel ? `📹 ${space.channel}` : '';
    const ipInfo = space.ip ? ` | ${space.ip}` : '';
    const parkingInfo = space.parking_name ? ` | ${space.parking_name}` : '';
    const changeCount = space.changes?.length || 0;
    
    html += `
      <div style="background:rgba(15,23,42,0.6); border-radius:12px; border:1px solid rgba(148,163,184,0.2); padding:20px; box-shadow:0 4px 12px rgba(0,0,0,0.1);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; padding-bottom:12px; border-bottom:2px solid rgba(148,163,184,0.2);">
          <div>
            <h4 style="margin:0 0 4px 0; font-size:18px; color:#e5e7eb; font-weight:bold;">
              🅿️ ${spaceName}
            </h4>
            <div style="font-size:12px; color:#9ca3af; margin-top:4px;">
              ${channelInfo}${ipInfo}${parkingInfo}
            </div>
          </div>
          <div style="font-size:14px; color:#a5b4fc;">
            共 <strong style="color:#10b981;">${changeCount}</strong> 次变化
          </div>
        </div>
        <div style="display:flex; flex-direction:column; gap:12px;">
    `;
    
    if (!space.changes || space.changes.length === 0) {
      html += '<div style="color:#9ca3af; padding:12px; text-align:center;">暂无变化记录</div>';
    } else {
      space.changes.forEach((change, idx) => {
        const changeType = change.change_type;
        const isArrive = changeType === "arrive";
        const changeIcon = isArrive ? "⬆️" : "⬇️";
        const changeLabel = isArrive ? "进车" : "离开";
        const changeColor = isArrive ? "#10b981" : "#ef4444";
        const changeBg = isArrive ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)";
        
        const prevState = change.prev_occupied ? "有车" : "无车";
        const currState = change.curr_occupied ? "有车" : "无车";
        const confidence = change.detection_confidence ? `(${(change.detection_confidence * 100).toFixed(0)}%)` : "";
        const detectedAt = change.detected_at ? new Date(change.detected_at).toLocaleString('zh-CN') : "-";
        
        html += `
          <div style="padding:16px; background:rgba(30,41,59,0.5); border-radius:8px; border-left:4px solid ${changeColor};">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
              <div style="flex:1;">
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                  <span style="font-size:18px;">${changeIcon}</span>
                  <span style="color:${changeColor}; font-weight:bold; font-size:14px;">${changeLabel}</span>
                  <span style="color:#9ca3af; font-size:12px;">${confidence}</span>
                </div>
                <div style="color:#e5e7eb; font-size:13px; margin-bottom:4px;">
                  <span style="color:#9ca3af;">状态变化：</span>
                  <span style="color:${change.prev_occupied ? '#10b981' : '#ef4444'}">${prevState}</span>
                  <span style="color:#9ca3af; margin:0 8px;">→</span>
                  <span style="color:${change.curr_occupied ? '#10b981' : '#ef4444'}">${currState}</span>
                </div>
                <div style="color:#9ca3af; font-size:12px;">
                  🕒 ${detectedAt}
                </div>
              </div>
              <div style="display:flex; gap:8px; flex-shrink:0;">
                ${change.prev_image_url ? `
                  <button onclick="openImageModal('${change.prev_image_url}', '上一张 - ${spaceName}')" 
                          style="padding:6px 12px; background:rgba(148,163,184,0.2); border:1px solid rgba(148,163,184,0.3); border-radius:6px; color:#e5e7eb; cursor:pointer; font-size:12px;">
                    📷 上一张
                  </button>
                ` : ''}
                ${change.image_url ? `
                  <button onclick="openImageModal('${change.image_url}', '当前 - ${spaceName}')" 
                          style="padding:6px 12px; background:rgba(148,163,184,0.2); border:1px solid rgba(148,163,184,0.3); border-radius:6px; color:#e5e7eb; cursor:pointer; font-size:12px;">
                    📷 当前
                  </button>
                ` : ''}
                ${change.prev_image_url && change.image_url ? `
                  <button onclick="openImageComparison('${change.prev_image_url}', '${change.image_url}', '${spaceName} - ${changeLabel}')" 
                          style="padding:6px 12px; background:rgba(34,211,238,0.2); border:1px solid rgba(34,211,238,0.4); border-radius:6px; color:#22d3ee; cursor:pointer; font-size:12px;">
                    🔍 对比
                  </button>
                ` : ''}
              </div>
            </div>
          </div>
        `;
      });
    }
    
    html += `
        </div>
      </div>
    `;
  });
  
  html += '</div>';
  container.innerHTML = html;
}

/**
 * 重置搜索条件
 */
function resetParkingChangeListSearch() {
  const dateEl = document.getElementById("pcl-date");
  const ipEl = document.getElementById("pcl-search-ip");
  const ipModeEl = document.getElementById("pcl-ip-mode");
  const channelEl = document.getElementById("pcl-search-channel");
  const channelModeEl = document.getElementById("pcl-channel-mode");
  const parkingNameEl = document.getElementById("pcl-parking-name");
  const taskStatusEl = document.getElementById("pcl-task-status");
  const changeTypeEl = document.getElementById("pcl-change-type");
  const spaceNameEl = document.getElementById("pcl-space-name");
  
  if (dateEl) dateEl.value = "";
  if (ipEl) ipEl.value = "";
  if (ipModeEl) ipModeEl.value = "eq";
  if (channelEl) channelEl.value = "";
  if (channelModeEl) channelModeEl.value = "eq";
  if (parkingNameEl) parkingNameEl.value = "";
  if (taskStatusEl) taskStatusEl.value = "";
  if (changeTypeEl) changeTypeEl.value = "";
  if (spaceNameEl) spaceNameEl.value = "";
  
  loadParkingChangeList();
}

/**
 * 打开图片预览模态框
 */
function openImageModal(imageUrl, title) {
  if (typeof openUrlInPreview === 'function') {
    openUrlInPreview(imageUrl, title);
  } else {
    // 如果 images.js 未加载，使用简单的窗口打开
    window.open(imageUrl, '_blank');
  }
}

/**
 * 打开图片对比预览
 */
function openImageComparison(prevImageUrl, currImageUrl, title) {
  if (typeof openComparePreview === 'function') {
    openComparePreview([prevImageUrl, currImageUrl], ['上一张', '当前']);
  } else {
    // 如果 images.js 未加载，打开两张图片
    window.open(prevImageUrl, '_blank');
    setTimeout(() => window.open(currImageUrl, '_blank'), 100);
  }
}

// 页面加载时自动加载数据
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function() {
    // 如果当前视图是车位变化列表，则加载数据
    const view = document.getElementById('view-parking-changes-list');
    if (view && view.style.display !== 'none') {
      loadParkingChangeList();
    }
  });
} else {
  // 如果DOM已经加载完成
  const view = document.getElementById('view-parking-changes-list');
  if (view && view.style.display !== 'none') {
    loadParkingChangeList();
  }
}
