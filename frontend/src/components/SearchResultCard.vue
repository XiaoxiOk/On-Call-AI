<script setup lang="ts">
import { computed } from 'vue'

import type { SearchResult } from '../types/api'

const props = defineProps<{
  result: SearchResult
  rank: number
}>()

const scoreLabel = computed(() => props.result.score.toFixed(4))
</script>

<template>
  <article class="result-card">
    <div class="result-header">
      <div>
        <p class="result-rank">Top {{ rank }}</p>
        <h2>{{ result.title }}</h2>
        <p class="result-id mono-text">{{ result.id }}</p>
      </div>
      <div class="result-score">
        <span>score</span>
        <strong>{{ scoreLabel }}</strong>
      </div>
    </div>

    <p class="result-snippet" v-html="result.snippet" />
  </article>
</template>

<style scoped>
.result-card {
  padding: 18px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 24px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.9));
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.05);
}

.result-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.result-rank,
.result-id,
.result-score span {
  margin: 0;
  color: #5b6475;
  font-size: 12px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.result-header h2 {
  margin: 8px 0 6px;
  font-size: 22px;
}

.result-score {
  min-width: 86px;
  padding: 10px 12px;
  border-radius: 18px;
  background: rgba(15, 118, 110, 0.08);
  text-align: right;
}

.result-score strong {
  display: block;
  margin-top: 4px;
  font-size: 20px;
  color: #0f766e;
}

.result-snippet {
  margin: 18px 0 0;
  color: #374151;
  line-height: 1.7;
}

.result-snippet :deep(mark) {
  padding: 0 4px;
  border-radius: 6px;
  background: rgba(250, 204, 21, 0.28);
  color: #92400e;
}

@media (max-width: 640px) {
  .result-header {
    flex-direction: column;
  }

  .result-score {
    text-align: left;
  }
}
</style>
