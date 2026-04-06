import { createRouter, createWebHistory } from 'vue-router'
import auth from '@/utils/auth'
import DefaultLayout from '@/views/layouts/DefaultLayout.vue'
import BlankLayout from '@/views/layouts/BlankLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: DefaultLayout,
      children: [
        {
          path: '',
          redirect: 'home',
        },
        {
          path: 'home',
          name: 'pages-home',
          component: () => import('@/views/pages/HomeView.vue'),
        },
        {
          path: 'space',
          component: () => import('@/views/space/SpaceLayoutView.vue'),
          children: [
            {
              path: 'apps',
              name: 'space-apps-list',
              component: () => import('@/views/space/apps/ListView.vue'),
            },
            {
              path: 'tools',
              name: 'space-tools-list',
              component: () => import('@/views/space/tools/ListView.vue'),
            },
            {
              path: 'workflows',
              name: 'space-workflows-list',
              component: () => import('@/views/space/workflows/ListView.vue'),
            },
            {
              path: 'datasets',
              name: 'space-datasets-list',
              component: () => import('@/views/space/datasets/ListView.vue'),
            },
            {
              path: 'likes',
              name: 'space-likes-list',
              component: () => import('@/views/space/likes/ListView.vue'),
            },
            {
              path: 'favorites',
              name: 'space-favorites-list',
              component: () => import('@/views/space/favorites/ListView.vue'),
            },
          ],
        },
        {
          path: 'space/datasets/:dataset_id/documents',
          name: 'space-datasets-documents-list',
          component: () => import('@/views/space/datasets/documents/ListView.vue'),
        },
        {
          path: 'space/datasets/:dataset_id/documents/create',
          name: 'space-datasets-documents-create',
          component: () => import('@/views/space/datasets/documents/CreateView.vue'),
        },
        {
          path: 'space/datasets/:dataset_id/documents/:document_id/segments',
          name: 'space-datasets-documents-segments-list',
          component: () => import('@/views/space/datasets/documents/segments/ListView.vue'),
        },
        {
          path: 'store/public-apps',
          name: 'store-public-apps-list',
          component: () => import('@/views/store/public-apps/ListView.vue'),
        },
        {
          path: 'store/public-apps/:app_id',
          component: () => import('@/views/store/public-apps/AppPreviewLayoutView.vue'),
          children: [
            {
              path: 'preview',
              name: 'store-public-apps-preview',
              component: () => import('@/views/store/public-apps/AppPreviewDetailView.vue'),
            },
            {
              path: 'analysis',
              name: 'store-public-apps-analysis',
              component: () => import('@/views/store/public-apps/AppPreviewAnalysisView.vue'),
            },
          ],
        },
        {
          path: 'store/tools',
          name: 'store-tools-list',
          component: () => import('@/views/store/tools/ListView.vue'),
        },
        {
          path: 'store/workflows',
          name: 'store-workflows-list',
          component: () => import('@/views/store/workflows/ListView.vue'),
        },
        {
          path: 'store/workflows/:workflow_id/preview',
          name: 'store-workflows-preview',
          component: () => import('@/views/store/workflows/PreviewView.vue'),
        },
        {
          path: 'search',
          name: 'conversation-search',
          component: () => import('@/views/home/ConversationSearchView.vue'),
        },
        {
          path: 'openapi',
          component: () => import('@/views/openapi/OpenAPILayoutView.vue'),
          children: [
            {
              path: '',
              name: 'openapi-index',
              component: () => import('@/views/openapi/IndexView.vue'),
            },
            {
              path: 'api-keys',
              name: 'openapi-api-keys-list',
              component: () => import('@/views/openapi/api-keys/ListView.vue'),
            },
          ],
        },
      ],
    },
    {
      path: '/',
      component: BlankLayout,
      children: [
        {
          path: 'auth/login',
          name: 'auth-login',
          redirect: { path: '/home', query: { login: '1' } },
        },
        {
          path: 'auth/forgot-password',
          name: 'auth-forgot-password',
          redirect: '/home',
        },
        {
          path: 'auth/authorize/:provider_name',
          name: 'auth-authorize',
          component: () => import('@/views/auth/AuthorizeView.vue'),
        },
        {
          path: 'space/apps',
          component: () => import('@/views/space/apps/AppLayoutView.vue'),
          children: [
            {
              path: ':app_id',
              name: 'space-apps-detail',
              component: () => import('@/views/space/apps/DetailView.vue'),
            },
            {
              path: ':app_id/published',
              name: 'space-apps-published',
              component: () => import('@/views/space/apps/PublishedView.vue'),
            },
            {
              path: ':app_id/analysis',
              name: 'space-apps-analysis',
              component: () => import('@/views/space/apps/AnalysisView.vue'),
            },
            {
              path: ':app_id/versions',
              name: 'space-apps-versions',
              component: () => import('@/views/space/apps/VersionComparisonView.vue'),
            },
            {
              path: ':app_id/prompt-compare',
              name: 'space-apps-prompt-compare',
              component: () => import('@/views/space/apps/PromptCompareView.vue'),
            },
          ],
        },
        {
          path: 'space/workflows/:workflow_id',
          name: 'space-workflows-detail',
          component: () => import('@/views/space/workflows/DetailView.vue'),
        },
        {
          path: 'web-apps/:token',
          name: 'web-apps-index',
          component: () => import('@/views/web-apps/IndexView.vue'),
        },
        {
          path: '/errors/404',
          name: 'errors-not-found',
          component: () => import('@/views/errors/NotFoundView.vue'),
        },
        {
          path: '/errors/403',
          name: 'errors-forbidden',
          component: () => import('@/views/errors/ForbiddenView.vue'),
        },
        {
          path: '/:pathMatch(.*)*',
          redirect: '/errors/404' // 或者直接渲染404组件
        }
      ],
    },
  ],
})

const PUBLIC_ROUTE_NAMES = new Set([
  'pages-home',
  'web-apps-index',
  'store-public-apps-list',
  'store-public-apps-preview',
  'store-public-apps-analysis',
  'store-tools-list',
  'store-workflows-list',
  'store-workflows-preview',
  'auth-login',
  'auth-authorize',
  'auth-forgot-password',
  'openapi-index',
  'conversation-search',
  'errors-not-found',
  'errors-forbidden',
])

const ANONYMOUS_PROMPT_ROUTE_NAMES = new Set([
  'space-apps-list',
  'space-tools-list',
  'space-workflows-list',
  'space-datasets-list',
  'space-likes-list',
  'space-favorites-list',
  'openapi-api-keys-list',
])

export const getAuthGuardRedirect = ({
  routeName,
  isLoggedIn,
}: {
  routeName: string
  isLoggedIn: boolean
}) => {
  if (isLoggedIn) return null
  if (PUBLIC_ROUTE_NAMES.has(routeName) || ANONYMOUS_PROMPT_ROUTE_NAMES.has(routeName)) {
    return null
  }

  return { path: '/home' as const }
}

router.beforeEach(async (to) => {
  const redirect = getAuthGuardRedirect({
    routeName: String(to.name || ''),
    isLoggedIn: auth.isLogin(),
  })

  if (redirect) {
    return redirect
  }
})
export default router
