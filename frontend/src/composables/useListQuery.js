import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/**
 * 列表页通用逻辑：分页 + 筛选条件 + 加载状态 + 汇总信息。
 *
 * @param {(params: object) => Promise<object>} fetcher 调用后端列表接口的方法
 * @param {object} options
 * @param {boolean} options.routeSync 是否把筛选条件与分页同步到 URL，
 *   开启后从 URL 初始化状态、每次查询回写 query，便于跳转详情/看板后原样返回。
 * @param {string[]} options.numericFilters 需要按数字解析的筛选字段（如面积区间）。
 */
export function useListQuery(
  fetcher,
  { initialFilters = {}, pageSize = 10, immediate = true, routeSync = false, numericFilters = [] } = {},
) {
  const defaults = { ...initialFilters }
  const route = routeSync ? useRoute() : null
  const router = routeSync ? useRouter() : null

  function queryValue(key) {
    const raw = route?.query[key]
    if (raw === undefined || raw === null) return undefined
    const value = String(raw).trim()
    return value === '' ? undefined : value
  }

  const filters = reactive({ ...defaults })
  if (route) {
    Object.keys(filters).forEach((key) => {
      const value = queryValue(key)
      if (value === undefined) return
      if (numericFilters.includes(key)) {
        const number = Number(value)
        filters[key] = Number.isFinite(number) ? number : defaults[key] ?? null
      } else {
        filters[key] = value
      }
    })
  }

  function initialPageSize() {
    if (!route) return pageSize
    const size = Number(queryValue('page_size'))
    return Number.isFinite(size) && size > 0 ? size : pageSize
  }

  function initialPage() {
    if (!route) return 1
    const page = Number(queryValue('page'))
    return Number.isFinite(page) && page > 0 ? page : 1
  }

  const meta = reactive({ page: initialPage(), page_size: initialPageSize(), total: 0, pages: 0 })
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

  function syncRoute() {
    if (!router || !route) return
    const query = {}
    Object.entries(buildParams()).forEach(([key, value]) => {
      if (value === null || value === undefined || value === '' || value === false) return
      query[key] = String(value)
    })
    const current = new URLSearchParams(route.fullPath.split('?')[1] || '').toString()
    const target = new URLSearchParams(query).toString()
    if (current !== target) {
      router.replace({ query })
    }
  }

  async function load() {
    loading.value = true
    try {
      const data = await fetcher(buildParams())
      items.value = data?.items ?? []
      summary.value = data?.summary ?? null
      if (data?.meta) Object.assign(meta, data.meta)
      if (routeSync) syncRoute()
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
    route,
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
