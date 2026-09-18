import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { useMetaStore } from '@/stores/meta'
import { formatNumber } from '@/utils/format'

/**
 * 从 URL query 中读取绿地台账的组合筛选条件，
 * 供档案详情与养护看板承接列表页的检索上下文，并在返回列表时原样带回（含分页与关键字）。
 */
export function useGreenSpaceScope() {
  const route = useRoute()
  const metaStore = useMetaStore()

  const ENUM_KEYS = {
    green_type: { group: 'green_space_type', text: '类型' },
    maintenance_grade: { group: 'maintenance_grade', text: '养护等级' },
    status: { group: 'green_space_status', text: '状态' },
  }
  const SCOPE_KEYS = ['district', 'green_type', 'maintenance_grade', 'status', 'area_min', 'area_max']

  function queryText(key) {
    const raw = route.query[key]
    if (raw === undefined || raw === null) return ''
    const value = String(raw).trim()
    return value
  }

  /** 调后端接口用的范围参数（关键字不进看板聚合口径）。 */
  const scopeParams = computed(() => {
    const params = {}
    SCOPE_KEYS.forEach((key) => {
      const value = queryText(key)
      if (!value) return
      params[key] = key.startsWith('area_') ? Number(value) : value
    })
    return params
  })

  const hasScope = computed(() => Object.keys(scopeParams.value).length > 0)

  const hasKeyword = computed(() => Boolean(queryText('keyword')))

  /** 顶部条件条使用的人类可读标签。 */
  const chips = computed(() => {
    metaStore.ensureLoaded()
    const items = []
    const district = queryText('district')
    if (district) items.push({ key: 'district', label: `行政区：${district}` })
    Object.entries(ENUM_KEYS).forEach(([key, config]) => {
      const value = queryText(key)
      if (!value) return
      items.push({ key, label: `${config.text}：${metaStore.label(config.group, value)}` })
    })
    const min = queryText('area_min')
    const max = queryText('area_max')
    if (min || max) {
      const left = min ? `${formatNumber(Number(min))} ㎡` : '0 ㎡'
      const right = max ? `${formatNumber(Number(max))} ㎡` : '不限'
      items.push({ key: 'area', label: `面积：${left} ~ ${right}` })
    }
    const keyword = queryText('keyword')
    if (keyword) items.push({ key: 'keyword', label: `关键字：${keyword}` })
    return items
  })

  /** 返回台账列表时原样带回的全部 query（含分页与关键字）。 */
  function listQuery() {
    return { ...route.query }
  }

  return { scopeParams, hasScope, hasKeyword, chips, listQuery }
}
