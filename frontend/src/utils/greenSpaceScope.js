import { useMetaStore } from '@/stores/meta'
import { formatNumber } from '@/utils/format'

/** 绿地台账组合检索条件的字段名：列表、档案详情、看板三处共用。 */
export const GREEN_SPACE_FILTER_KEYS = [
  'keyword',
  'district',
  'green_type',
  'maintenance_grade',
  'status',
  'area_min',
  'area_max',
]

/** 从路由 query（或筛选对象）中提取台账条件，转发给下一页或接口时保持同口径。 */
export function pickGreenSpaceFilters(source) {
  const query = {}
  GREEN_SPACE_FILTER_KEYS.forEach((key) => {
    const value = source?.[key]
    if (value === null || value === undefined || value === '') return
    query[key] = String(value)
  })
  return query
}

/** 把当前筛选条件整理成人类可读的标签，用于档案详情与看板上的条件回显。 */
export function describeGreenSpaceFilters(source) {
  const meta = useMetaStore()
  const tags = []
  const text = (key) => {
    const value = source?.[key]
    return value === null || value === undefined || value === '' ? null : String(value)
  }

  const keyword = text('keyword')
  if (keyword) tags.push({ key: 'keyword', label: `关键字：${keyword}` })
  const district = text('district')
  if (district) tags.push({ key: 'district', label: `行政区：${district}` })
  const greenType = text('green_type')
  if (greenType) tags.push({ key: 'green_type', label: `类型：${meta.label('green_space_type', greenType)}` })
  const grade = text('maintenance_grade')
  if (grade) tags.push({ key: 'maintenance_grade', label: `养护等级：${meta.label('maintenance_grade', grade)}` })
  const status = text('status')
  if (status) tags.push({ key: 'status', label: `状态：${meta.label('green_space_status', status)}` })

  const areaMin = text('area_min')
  const areaMax = text('area_max')
  if (areaMin || areaMax) {
    let label = '面积：'
    if (areaMin && areaMax) {
      label += `${formatNumber(areaMin)} ~ ${formatNumber(areaMax)} ㎡`
    } else if (areaMin) {
      label += `≥ ${formatNumber(areaMin)} ㎡`
    } else {
      label += `≤ ${formatNumber(areaMax)} ㎡`
    }
    tags.push({ key: 'area', label })
  }
  return tags
}
