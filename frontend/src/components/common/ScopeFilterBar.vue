<template>
  <div v-if="tags.length" class="panel scope-bar">
    <span class="scope-bar__label">{{ title }}</span>
    <el-tag
      v-for="tag in tags"
      :key="tag.key"
      size="small"
      type="info"
      effect="plain"
      class="scope-bar__tag"
    >
      {{ tag.label }}
    </el-tag>
    <span class="scope-bar__spacer" />
    <slot />
  </div>
</template>

<script setup>
defineProps({
  tags: { type: Array, default: () => [] },
  title: { type: String, default: '台账筛选条件' },
})
</script>

<style scoped>
.scope-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
}

.scope-bar__label {
  color: #606266;
  font-size: 13px;
  font-weight: 600;
}

.scope-bar__tag {
  margin: 0;
}

.scope-bar__spacer {
  flex: 1;
}
</style>
