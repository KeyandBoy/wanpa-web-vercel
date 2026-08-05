<template>
  <div class="layer-filter">
    <div class="layer-filter-head">
      <span class="layer-filter-label">多层筛选</span>
      <el-button type="primary" link size="small" @click="addLayer">+ 添加一层</el-button>
    </div>
    <div v-if="!modelValue.length" class="layer-filter-empty">
      未启用。添加规则后，对搜索结果逐层过滤（层间取交集，层内关键词取并集）。
    </div>
    <div v-for="(rule, i) in modelValue" :key="i" class="layer-row">
      <el-select v-model="rule.field" size="small" style="width: 84px">
        <el-option label="全部" value="all" />
        <el-option label="标题" value="title" />
        <el-option label="网址" value="url" />
      </el-select>
      <el-select v-model="rule.mode" size="small" style="width: 84px">
        <el-option label="包含" value="include" />
        <el-option label="排除" value="exclude" />
      </el-select>
      <el-input
        v-model="rule.words"
        size="small"
        placeholder="关键词，逗号分隔"
        clearable
      />
      <el-button link size="small" type="danger" title="删除本层" @click="removeLayer(i)">
        <el-icon><CircleClose /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { CircleClose } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

function addLayer() {
  emit('update:modelValue', [...props.modelValue, { field: 'all', mode: 'include', words: '' }])
}

function removeLayer(i) {
  const next = props.modelValue.slice()
  next.splice(i, 1)
  emit('update:modelValue', next)
}
</script>

<style scoped>
.layer-filter {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}
.layer-filter-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.layer-filter-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.layer-filter-empty {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}
.layer-row {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}
.layer-row .el-input {
  flex: 1;
}
</style>
