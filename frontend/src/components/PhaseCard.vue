<script setup lang="ts">
defineProps<{
  title: string
  summary: string
  route: string
  badge: string
}>()
</script>

<template>
  <article class="phase-card">
    <div class="phase-card-header">
      <span class="phase-badge">{{ badge }}</span>
      <RouterLink :to="route" class="phase-link">Open</RouterLink>
    </div>
    <h2>{{ title }}</h2>
    <p>{{ summary }}</p>
  </article>
</template>

<style scoped>
.phase-card {
  padding: 18px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(255, 255, 255, 0.78));
}

.phase-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.phase-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.1);
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.phase-link {
  font-size: 13px;
  font-weight: 700;
  color: #0f766e;
}

.phase-card h2 {
  margin: 14px 0 8px;
  font-size: 20px;
}

.phase-card p {
  margin: 0;
  color: #5b6475;
  font-size: 14px;
}
</style>
