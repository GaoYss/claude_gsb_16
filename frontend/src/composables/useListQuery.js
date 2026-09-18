import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/**
 * 列表页通用逻辑：分页 + 筛选条件 + 加载状态 + 汇总信息。
 *
 * @param {(params: object) => Promise<object>} fetcher 调用后端列表接口的方法
 * @param {object} options
 * @param {boolean} [options.routeSync=false] 是否把筛选条件与分页同步到 URL query，
 *   开启后从其他页面返回列表时可恢复原条件与翻页位置
 */
export function useListQuery(
  fetcher,
  { initialFilters = {}, pageSize = 10, immediate = true, routeSync = false } = {},
) {
  const route = routeSync ? useRoute() : null
  const router = routeSync ? useRouter() : null
  const defaults = { ...initialFilters }
  const filters = reactive({ ...defaults })
  const meta = reactive({ page: 1, page_size: pageSize, total: 0, pages: 0 })

  if (routeSync) {
    // 从 URL 恢复筛选条件：数值型（含 null 默认的数值字段）按 number 还原
    Object.keys(filters).forEach((key) => {
      const raw = route.query[key]
      if (raw === undefined || raw === '') return
      const current = filters[key]
      if (current === null || typeof current === 'number') {
        const parsed = Number(raw)
        if (Number.isFinite(parsed)) filters[key] = parsed
      } else {
        filters[key] = raw
      }
    })
    const queryPage = Number(route.query.page)
    if (Number.isFinite(queryPage) && queryPage > 0) meta.page = queryPage
    const querySize = Number(route.query.page_size)
    if (Number.isFinite(querySize) && querySize > 0) meta.page_size = querySize
  }

  const items = ref([])
  const summary = ref(null)
  const loading = ref(false)

  function buildParams() {
    const params = { page: meta.page, page_size: meta.page_size }
    Object.entries(filters).forEach(([key, value]) => {
      if (value === null || value === undefined || value === '') return
      if (Array.isArray(value)) {
        if (value.length === 0) return
        params[key] = value.join(',')
        return
      }
      params[key] = value
    })
    return params
  }

  function sameQuery(a, b) {
    const keys = new Set([...Object.keys(a || {}), ...Object.keys(b || {})])
    return [...keys].every((key) => String(a?.[key] ?? '') === String(b?.[key] ?? ''))
  }

  function syncToRoute() {
    if (!routeSync) return
    const query = {}
    Object.entries(filters).forEach(([key, value]) => {
      if (value === null || value === undefined || value === '' || value === false) return
      query[key] = Array.isArray(value) ? value.join(',') : String(value)
    })
    if (meta.page > 1) query.page = String(meta.page)
    if (meta.page_size !== pageSize) query.page_size = String(meta.page_size)
    if (!sameQuery(query, route.query)) {
      router.replace({ path: route.path, query })
    }
  }

  async function load() {
    loading.value = true
    try {
      const data = await fetcher(buildParams())
      items.value = data?.items ?? []
      summary.value = data?.summary ?? null
      if (data?.meta) Object.assign(meta, data.meta)
      syncToRoute()
    } catch {
      items.value = []
      summary.value = null
    } finally {
      loading.value = false
    }
  }

  function search() {
    meta.page = 1
    return load()
  }

  function resetFilters() {
    Object.keys(filters).forEach((key) => {
      if (key in defaults) return
      delete filters[key]
    })
    Object.assign(filters, defaults)
    return search()
  }

  function handlePageChange(page) {
    meta.page = page
    return load()
  }

  function handleSizeChange(size) {
    meta.page_size = size
    meta.page = 1
    return load()
  }

  if (immediate) onMounted(load)

  return {
    filters,
    meta,
    items,
    summary,
    loading,
    load,
    search,
    resetFilters,
    handlePageChange,
    handleSizeChange,
  }
}
