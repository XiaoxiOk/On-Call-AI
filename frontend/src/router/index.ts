import { createRouter, createWebHistory } from 'vue-router'

import HomeView from '../views/HomeView.vue'
import V1SearchView from '../views/V1SearchView.vue'
import V2SearchView from '../views/V2SearchView.vue'
import V3ChatView from '../views/V3ChatView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/v1', name: 'v1', component: V1SearchView },
    { path: '/v2', name: 'v2', component: V2SearchView },
    { path: '/v3', name: 'v3', component: V3ChatView },
  ],
})

export default router
