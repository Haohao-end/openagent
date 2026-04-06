import type { App } from 'vue'
import Alert from '@arco-design/web-vue/es/alert'
import Avatar from '@arco-design/web-vue/es/avatar'
import Button from '@arco-design/web-vue/es/button'
import Card from '@arco-design/web-vue/es/card'
import Checkbox from '@arco-design/web-vue/es/checkbox'
import Collapse from '@arco-design/web-vue/es/collapse'
import Divider from '@arco-design/web-vue/es/divider'
import Drawer from '@arco-design/web-vue/es/drawer'
import Dropdown from '@arco-design/web-vue/es/dropdown'
import Empty from '@arco-design/web-vue/es/empty'
import Form from '@arco-design/web-vue/es/form'
import Grid from '@arco-design/web-vue/es/grid'
import Image from '@arco-design/web-vue/es/image'
import Input from '@arco-design/web-vue/es/input'
import InputNumber from '@arco-design/web-vue/es/input-number'
import InputTag from '@arco-design/web-vue/es/input-tag'
import {
  IconApps,
  IconBold,
  IconBookmark,
  IconBranch,
  IconBulb,
  IconCaretDown,
  IconCheck,
  IconCheckCircle,
  IconCheckCircleFill,
  IconClockCircle,
  IconClose,
  IconCloseCircle,
  IconCode,
  IconCodeBlock,
  IconCommon,
  IconCompass,
  IconComputer,
  IconCopy,
  IconDashboard,
  IconDelete,
  IconDown,
  IconEdit,
  IconEmail,
  IconEmpty,
  IconExclamationCircle,
  IconExclamationCircleFill,
  IconExpand,
  IconExperiment,
  IconEye,
  IconFile,
  IconFilter,
  IconFontColors,
  IconGithub,
  IconHome,
  IconInfoCircle,
  IconInfoCircleFill,
  IconItalic,
  IconLanguage,
  IconLeft,
  IconLink,
  IconList,
  IconLoading,
  IconLock,
  IconMessage,
  IconMinusCircle,
  IconMore,
  IconObliqueLine,
  IconOrderedList,
  IconPaste,
  IconPause,
  IconPlayArrow,
  IconPlayCircle,
  IconPlus,
  IconPlusCircleFill,
  IconPoweroff,
  IconPushpin,
  IconQuestionCircle,
  IconQuestionCircleFill,
  IconQuote,
  IconRefresh,
  IconRelation,
  IconRight,
  IconRobot,
  IconSafe,
  IconSave,
  IconSchedule,
  IconSend,
  IconSettings,
  IconShareAlt,
  IconStorage,
  IconSync,
  IconTool,
  IconTranslate,
  IconUnorderedList,
  IconUp,
  IconUpload,
  IconUser,
  IconWechat,
} from '@arco-design/web-vue/es/icon'
import Layout from '@arco-design/web-vue/es/layout'
import Link from '@arco-design/web-vue/es/link'
import Modal from '@arco-design/web-vue/es/modal'
import Pagination from '@arco-design/web-vue/es/pagination'
import Progress from '@arco-design/web-vue/es/progress'
import Radio from '@arco-design/web-vue/es/radio'
import Select from '@arco-design/web-vue/es/select'
import Skeleton from '@arco-design/web-vue/es/skeleton'
import Slider from '@arco-design/web-vue/es/slider'
import Space from '@arco-design/web-vue/es/space'
import Spin from '@arco-design/web-vue/es/spin'
import Steps from '@arco-design/web-vue/es/steps'
import Switch from '@arco-design/web-vue/es/switch'
import Table from '@arco-design/web-vue/es/table'
import Tabs from '@arco-design/web-vue/es/tabs'
import Tag from '@arco-design/web-vue/es/tag'
import Textarea from '@arco-design/web-vue/es/textarea'
import Tooltip from '@arco-design/web-vue/es/tooltip'
import Trigger from '@arco-design/web-vue/es/trigger'
import Upload from '@arco-design/web-vue/es/upload'

const arcoComponents = [
  Alert,
  Avatar,
  Button,
  Card,
  Checkbox,
  Collapse,
  Divider,
  Drawer,
  Dropdown,
  Empty,
  Form,
  Grid,
  Image,
  Input,
  InputNumber,
  InputTag,
  Layout,
  Link,
  Modal,
  Pagination,
  Progress,
  Radio,
  Select,
  Skeleton,
  Slider,
  Space,
  Spin,
  Steps,
  Switch,
  Table,
  Tabs,
  Tag,
  Textarea,
  Tooltip,
  Trigger,
  Upload,
] as const

const arcoIcons = [
  ['icon-apps', IconApps],
  ['icon-bold', IconBold],
  ['icon-bookmark', IconBookmark],
  ['icon-branch', IconBranch],
  ['icon-bulb', IconBulb],
  ['icon-caret-down', IconCaretDown],
  ['icon-check', IconCheck],
  ['icon-check-circle', IconCheckCircle],
  ['icon-check-circle-fill', IconCheckCircleFill],
  ['icon-clock-circle', IconClockCircle],
  ['icon-close', IconClose],
  ['icon-close-circle', IconCloseCircle],
  ['icon-code', IconCode],
  ['icon-code-block', IconCodeBlock],
  ['icon-common', IconCommon],
  ['icon-compass', IconCompass],
  ['icon-computer', IconComputer],
  ['icon-copy', IconCopy],
  ['icon-dashboard', IconDashboard],
  ['icon-delete', IconDelete],
  ['icon-down', IconDown],
  ['icon-edit', IconEdit],
  ['icon-email', IconEmail],
  ['icon-empty', IconEmpty],
  ['icon-exclamation-circle', IconExclamationCircle],
  ['icon-exclamation-circle-fill', IconExclamationCircleFill],
  ['icon-expand', IconExpand],
  ['icon-experiment', IconExperiment],
  ['icon-eye', IconEye],
  ['icon-file', IconFile],
  ['icon-filter', IconFilter],
  ['icon-font-colors', IconFontColors],
  ['icon-github', IconGithub],
  ['icon-home', IconHome],
  ['icon-info-circle', IconInfoCircle],
  ['icon-info-circle-fill', IconInfoCircleFill],
  ['icon-italic', IconItalic],
  ['icon-language', IconLanguage],
  ['icon-left', IconLeft],
  ['icon-link', IconLink],
  ['icon-list', IconList],
  ['icon-loading', IconLoading],
  ['icon-lock', IconLock],
  ['icon-message', IconMessage],
  ['icon-minus-circle', IconMinusCircle],
  ['icon-more', IconMore],
  ['icon-oblique-line', IconObliqueLine],
  ['icon-ordered-list', IconOrderedList],
  ['icon-paste', IconPaste],
  ['icon-pause', IconPause],
  ['icon-play-arrow', IconPlayArrow],
  ['icon-play-circle', IconPlayCircle],
  ['icon-plus', IconPlus],
  ['icon-plus-circle-fill', IconPlusCircleFill],
  ['icon-poweroff', IconPoweroff],
  ['icon-pushpin', IconPushpin],
  ['icon-question-circle', IconQuestionCircle],
  ['icon-question-circle-fill', IconQuestionCircleFill],
  ['icon-quote', IconQuote],
  ['icon-refresh', IconRefresh],
  ['icon-relation', IconRelation],
  ['icon-right', IconRight],
  ['icon-robot', IconRobot],
  ['icon-safe', IconSafe],
  ['icon-save', IconSave],
  ['icon-schedule', IconSchedule],
  ['icon-send', IconSend],
  ['icon-settings', IconSettings],
  ['icon-share-alt', IconShareAlt],
  ['icon-storage', IconStorage],
  ['icon-sync', IconSync],
  ['icon-tool', IconTool],
  ['icon-translate', IconTranslate],
  ['icon-unordered-list', IconUnorderedList],
  ['icon-up', IconUp],
  ['icon-upload', IconUpload],
  ['icon-user', IconUser],
  ['icon-wechat', IconWechat],
] as const

export function installArco(app: App) {
  arcoComponents.forEach((component) => {
    app.use(component)
  })

  arcoIcons.forEach(([name, component]) => {
    app.component(name, component)
  })
}
