<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showFailToast } from 'vant'

import SearchResultCard from '../components/SearchResultCard.vue'
import { ApiError, apiFetch } from '../lib/http'
import type { SearchResponse } from '../types/api'

const examples = ['OOM', '故障', 'CDN', '&']
const query = ref('OOM')
const loading = ref(false)
const error = ref('')
const results = ref<SearchResponse['results']>([])

async function runSearch(nextQuery?: string): Promise<void> {
  if (nextQuery !== undefined) {
    query.value = nextQuery
  }

  const trimmed = query.value.trim()
  if (!trimmed) {
    error.value = '请输入关键词。'
    results.value = []
    return
  }

  loading.value = true
  error.value = ''

  try {
    const response = await apiFetch<SearchResponse>(
      `/v1/search?q=${encodeURIComponent(trimmed)}`,
    )
    results.value = response.results
  } catch (cause) {
    const message =
      cause instanceof ApiError ? cause.detail : '搜索请求失败，请稍后重试。'
    error.value = message
    results.value = []
    showFailToast(message)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void runSearch()
})
</script>

<template>
  <section class="section-stack">
    <div class="search-lead">
      <div>
        <p class="eyebrow">Phase 1</p>
        <h2>关键词检索</h2>
      </div>
      <p class="search-copy">
        使用 `jieba` 分词和 BM25 内存索引，从 `data/` 下的 SOP 文档中检索高亮片段。
      </p>
    </div>

    <van-search
      v-model="query"
      shape="round"
      placeholder="输入故障关键词，例如 OOM、CDN、主从延迟"
      @search="void runSearch()"
    />

    <div class="example-row">
      <van-button
        v-for="example in examples"
        :key="example"
        plain
        round
        size="small"
        @click="void runSearch(example)"
      >
        {{ example }}
      </van-button>
    </div>

    <van-button type="primary" block @click="void runSearch()" :loading="loading">
      开始搜索
    </van-button>

    <van-notice-bar
      v-if="error"
      left-icon="warning-o"
      color="#991b1b"
      background="#fef2f2"
    >
      {{ error }}
    </van-notice-bar>

    <van-loading v-if="loading" class="loading-block" size="24px" vertical>
      正在检索 SOP 文档
    </van-loading>

    <div v-else-if="results.length" class="result-stack">
      <SearchResultCard
        v-for="(result, index) in results"
        :key="result.id"
        :rank="index + 1"
        :result="result"
      />
    </div>

    <van-empty
      v-else
      description="当前没有匹配结果，可以尝试更换关键词。"
    />
  </section>
</template>

<style scoped>
.search-lead {
  display: grid;
  gap: 8px;
}

.search-lead h2 {
  margin: 0;
  font-size: 28px;
}

.search-copy {
  margin: 0;
  color: #5b6475;
}

.example-row,
.result-stack {
  display: grid;
  gap: 12px;
}

.example-row {
  grid-template-columns: repeat(auto-fit, minmax(88px, max-content));
}

.loading-block {
  padding: 32px 0;
}
</style>
