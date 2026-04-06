export type SpaceResourceType = 'app' | 'workflow'

export type SpaceResourceCardItem = {
  id: string
  resource_type: SpaceResourceType
  name: string
  icon: string
  description: string
  category: string
  view_count: number
  like_count: number
  fork_count: number
  favorite_count: number
  creator_name: string
  creator_avatar: string
  published_at: number
  created_at: number
  action_at: number
  is_liked: boolean
  is_favorited: boolean
  is_forked: boolean
}
