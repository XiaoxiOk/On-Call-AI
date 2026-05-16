<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showFailToast } from 'vant'

import SearchResultCard from '../components/SearchResultCard.vue'
import { ApiError, apiFetch } from '../lib/http'
import type { SearchResponse } from '../types/api'

const examples = ['服务器挂了', '黑客攻击', '机器学习模型出问题']
const query = ref('服务器挂了')
const loading = ref(false)
const error = ref('')
const results = ref<SearchResponse['results']>([])

async function runSearch(nextQuery?: string): Promise<void> {
  if (nextQuery !== undefined) {
    query.value = nextQuery
  }

  const trimmed = query.value.trim()
  if (!trimmed) {
    error.value = '请输入语义查询。'
    results.value = []
    return
  }

  loading.value = true
  error.value = ''

  try {
    const response = await apiFetch<SearchResponse>(
      `/v2/search?q=${encodeURIComponent(trimmed)}`,
    )
    results.value = response.results
  } catch (cause) {
    const message =
      cause instanceof ApiError ? cause.detail : '语义检索请求失败，请稍后重试。'
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
        <p class="eyebrow">Phase 2</p>
        <h2>语义检索</h2>
      </div>
      <p class="search-copy">
        启动时加载中文 embedding 模型，将 SOP 文档编码为向量，并通过 `numpy.dot`
        计算归一化向量相似度。
      </p>
    </div>

    <van-search
      v-model="query"
      shape="round"
      placeholder="输入自然语言问题，例如 服务器挂了、黑客攻击"
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

    <van-button type="success" block @click="void runSearch()" :loading="loading">
      语义搜索
    </van-button>

    <van-notice-bar
      v-if="error"
      left-icon="warning-o"
      color="#92400e"
      background="#fff7ed"
    >
      {{ error }}
    </van-notice-bar>

    <van-loading v-if="loading" class="loading-block" size="24px" vertical>
      正在加载向量检索结果
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
      description="当前没有语义匹配结果，或者模型暂时不可用。"
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
  grid-template-columns: repeat(auto-fit, minmax(120px, max-content));
}

.loading-block {
  padding: 32px 0;
}
</style>
