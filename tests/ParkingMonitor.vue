<template>
  <div class="min-h-screen bg-gray-50 p-4 md:p-6">
    <!-- 顶部信息栏 -->
    <div class="bg-white rounded-lg shadow p-4 mb-6">
      <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-2">
        <div>
          <h1 class="text-xl font-bold text-gray-800">高新停车场 · A区（通道 c1）</h1>
          <p class="text-sm text-gray-500">
            最后更新：{{ lastUpdateTime }}（{{ timeAgo }}）
          </p>
        </div>
        <div class="flex items-center gap-3">
          <span class="px-2 py-1 rounded-full text-xs font-medium"
                :class="systemStatus.color">
            {{ systemStatus.text }}
          </span>
          <button @click="toggleDebug"
                  class="text-xs text-blue-600 hover:underline">
            {{ debugMode ? '关闭调试' : '开启调试' }}
          </button>
          <button @click="filterUncertain = !filterUncertain"
                  class="px-3 py-1 bg-blue-50 text-blue-700 rounded text-xs">
            {{ filterUncertain ? '显示全部' : '仅看异常' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 车位网格 -->
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
      <div v-for="spot in filteredSpots" :key="spot.id"
           @click="openDetail(spot)"
           class="bg-white rounded-lg shadow cursor-pointer hover:shadow-md transition-shadow"
           :class="{
             'ring-2 ring-yellow-400': spot.uncertain,
             'ring-2 ring-green-500': !spot.uncertain && spot.status === 'occupied',
             'ring-2 ring-red-500': !spot.uncertain && spot.status === 'empty'
           }">
        <div class="p-3 text-center">
          <div class="font-semibold text-gray-800">{{ spot.name }}</div>
          <div class="mt-1 text-sm"
               :class="{
                 'text-green-600 font-medium': spot.status === 'occupied' && !spot.uncertain,
                 'text-red-600 font-medium': spot.status === 'empty' && !spot.uncertain,
                 'text-yellow-600 font-medium': spot.uncertain
               }">
            {{ spot.displayStatus }}
          </div>
          <div v-if="spot.confidence !== null" class="mt-1 text-xs text-gray-500">
            {{ Math.round(spot.confidence * 100) }}%
          </div>
          <div v-if="debugMode && spot.interference" class="mt-1 flex justify-center">
            <span v-if="spot.interference.includes('暗光')" class="text-xs text-blue-500">🌙</span>
            <span v-if="spot.interference.includes('遮挡')" class="text-xs text-purple-500">🌳</span>
            <span v-if="spot.lowConfidence" class="text-xs text-yellow-500">⚠️</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 事件时间线（可选） -->
    <div v-if="recentEvents.length > 0" class="mt-8 bg-white rounded-lg shadow p-4">
      <h2 class="text-lg font-semibold mb-3">最近状态变化</h2>
      <ul class="space-y-2">
        <li v-for="(event, i) in recentEvents" :key="i" class="text-sm">
          <span class="font-mono text-gray-500">{{ event.time }}</span>
          → <span class="font-medium">{{ event.spot }}</span>:
          <span :class="{
            'text-green-600': event.type === 'arrive',
            'text-red-600': event.type === 'leave'
          }">{{ event.type === 'arrive' ? '车辆进入' : '车辆离开' }}</span>
          <span v-if="event.similarity" class="text-gray-500 ml-2">
            (相似度: {{ event.similarity }}%)
          </span>
        </li>
      </ul>
    </div>
  </div>

  <!-- 车位详情弹窗 -->
  <Teleport to="body" v-if="selectedSpot">
    <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-lg w-full max-w-2xl max-h-[90vh] overflow-auto">
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-bold">{{ selectedSpot.name }} 详情</h3>
          <button @click="selectedSpot = null" class="text-gray-500 hover:text-gray-700">&times;</button>
        </div>
        <div class="p-4 space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <p class="text-sm text-gray-500">当前截图</p>
              <img :src="getScreenshotUrl(selectedSpot)" alt="当前" class="w-full border rounded mt-1">
            </div>
            <div>
              <p class="text-sm text-gray-500">上一帧（{{ selectedSpot.prevTime }}）</p>
              <img :src="getPrevScreenshotUrl(selectedSpot)" alt="上一帧" class="w-full border rounded mt-1">
            </div>
          </div>

          <div class="text-sm space-y-1">
            <p><span class="font-medium">当前状态：</span>{{ selectedSpot.displayStatus }}</p>
            <p><span class="font-medium">YOLO 置信度：</span>{{ Math.round(selectedSpot.confidence * 100) }}%</p>
            <p><span class="font-medium">特征相似度：</span>{{ selectedSpot.similarity }}%</p>
            <p><span class="font-medium">干扰因素：</span>{{ selectedSpot.interference.join(', ') || '无' }}</p>
          </div>

          <div class="flex gap-2 pt-2">
            <button @click="confirmStatus('occupied')"
                    class="px-3 py-1 bg-green-100 text-green-700 rounded text-sm">
              ✓ 确认有车
            </button>
            <button @click="confirmStatus('empty')"
                    class="px-3 py-1 bg-red-100 text-red-700 rounded text-sm">
              ✗ 确认为空
            </button>
            <button @click="selectedSpot = null"
                    class="px-3 py-1 bg-gray-100 text-gray-700 rounded text-sm">
              关闭
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

// 模拟从 WebSocket 或 API 获取的数据
const spots = ref([
  { id: 'GXSL001', name: '01', status: 'occupied', confidence: 0.77, similarity: 84.3, uncertain: true, interference: ['暗光', '遮挡'], lowConfidence: false },
  { id: 'GXSL002', name: '02', status: 'occupied', confidence: 0.92, similarity: 91.2, uncertain: false, interference: [], lowConfidence: false },
  { id: 'GXSL003', name: '03', status: 'empty', confidence: null, similarity: null, uncertain: false, interference: [], lowConfidence: false },
  { id: 'GXSL004', name: '04', status: 'occupied', confidence: 0.88, similarity: 89.1, uncertain: false, interference: [], lowConfidence: false },
  { id: 'GXSL005', name: '05', status: 'occupied', confidence: 0.85, similarity: 87.5, uncertain: false, interference: [], lowConfidence: false },
  { id: 'GXSL006', name: '06', status: 'occupied', confidence: 0.63, similarity: 83.7, uncertain: true, interference: ['暗光'], lowConfidence: true }
])

const recentEvents = ref([
  { time: '18:39:02', spot: 'GXSL006', type: 'arrive', similarity: 83.7 },
  { time: '18:38:30', spot: 'GXSL003', type: 'leave', similarity: null }
])

const lastUpdateTime = ref('18:39:05')
const timeAgo = ref('1秒前')
const debugMode = ref(false)
const filterUncertain = ref(false)
const selectedSpot = ref(null)

// 计算显示状态
spots.value.forEach(spot => {
  if (spot.uncertain) {
    spot.displayStatus = '有车?'
  } else {
    spot.displayStatus = spot.status === 'occupied' ? '有车' : '空'
  }
})

// 过滤车位
const filteredSpots = computed(() => {
  if (filterUncertain.value) {
    return spots.value.filter(s => s.uncertain)
  }
  return spots.value
})

// 系统状态
const systemStatus = computed(() => {
  const uncertainCount = spots.value.filter(s => s.uncertain).length
  if (uncertainCount === 0) {
    return { text: '系统正常', color: 'bg-green-100 text-green-800' }
  } else {
    return { text: `注意：${uncertainCount}个车位识别不稳定`, color: 'bg-yellow-100 text-yellow-800' }
  }
})

const toggleDebug = () => {
  debugMode.value = !debugMode.value
}

const openDetail = (spot) => {
  selectedSpot.value = { ...spot, prevTime: '18:38:55' }
}

const getScreenshotUrl = (spot) => {
  // 实际应替换为你的截图路径
  return `/screenshots/2025-12-19/10_10_11_123_1766155200_1766155799_c1.jpg`
}

const getPrevScreenshotUrl = (spot) => {
  return `/screenshots/2025-12-19/10_10_11_123_1766154600_1766155199_c1.jpg`
}

const confirmStatus = (status) => {
  alert(`已人工确认 ${selectedSpot.value.name} 为 ${status === 'occupied' ? '有车' : '空'}`)
  // 这里应调用 API 提交人工确认
  selectedSpot.value = null
}

// 模拟实时更新（实际用 WebSocket）
onMounted(() => {
  setInterval(() => {
    timeAgo.value = '刚刚'
  }, 1000)
})
</script>