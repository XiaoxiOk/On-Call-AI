<script setup lang="ts">
import PhaseCard from '../components/PhaseCard.vue'

const phases = [
  {
    badge: 'Step 1',
    title: 'Keyword Search',
    route: '/v1',
    summary: 'Prepare the Phase 1 page for BM25-based SOP lookup.',
  },
  {
    badge: 'Step 2',
    title: 'Semantic Search',
    route: '/v2',
    summary: 'Reserve the Phase 2 entry for dense retrieval and relevance ranking.',
  },
  {
    badge: 'Step 3',
    title: 'Streaming Agent',
    route: '/v3',
    summary: 'Reserve the Phase 3 chat surface for tool-aware SSE responses.',
  },
]

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
</script>

<template>
  <section class="section-stack">
    <van-notice-bar left-icon="info-o" color="#134e4a" background="#ecfdf5">
      Project skeleton is ready. Backend targets {{ apiBaseUrl }} during local development.
    </van-notice-bar>

    <div class="overview-grid">
      <PhaseCard
        v-for="phase in phases"
        :key="phase.route"
        :badge="phase.badge"
        :route="phase.route"
        :summary="phase.summary"
        :title="phase.title"
      />
    </div>

    <van-cell-group inset>
      <van-cell title="Backend entry" value="main.py" />
      <van-cell title="API prefixes" value="/v1, /v2, /v3" />
      <van-cell title="Frontend stack" value="Vue 3 + Vite + Vant 4" />
      <van-cell title="Phase 2 model" value="BAAI/bge-small-zh-v1.5" />
      <van-cell title="Phase 3 config" value="OPENAI_API_KEY required" />
    </van-cell-group>
  </section>
</template>

<style scoped>
.overview-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

@media (max-width: 900px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
