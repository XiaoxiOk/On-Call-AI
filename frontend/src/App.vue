<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { label: 'Overview', to: '/' },
  { label: 'Phase 1', to: '/v1' },
  { label: 'Phase 2', to: '/v2' },
  { label: 'Phase 3', to: '/v3' },
]

const pageTitle = computed(() => {
  const current = navItems.find((item) => item.to === route.path)
  return current?.label ?? 'On-Call Assistant'
})
</script>

<template>
  <div class="app-shell">
    <header class="hero-panel">
      <p class="eyebrow">On-Call Assistant</p>
      <h1>{{ pageTitle }}</h1>
      <p class="hero-copy">
        Frontend skeleton for the FastAPI + Vue 3 incident response assistant.
      </p>
    </header>

    <nav class="nav-strip" aria-label="Primary">
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="nav-chip"
        :class="{ 'nav-chip-active': route.path === item.to }"
      >
        {{ item.label }}
      </RouterLink>
    </nav>

    <main class="page-panel">
      <RouterView />
    </main>
  </div>
</template>
