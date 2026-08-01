export const SOURCE_GROUPS = [
  {
    name: '国内数据源',
    items: [
      {
        id: 'bing',
        label: '必应',
        desc: '必应图片搜索。通用性最强，适合绝大多数题材；中文搜索效果好，国内直接可用。',
        tag: '通用'
      },
      {
        id: 'baidu',
        label: '百度',
        desc: '百度图片。中文搜索最强，适合人物、明星、中文场景图；国内直接可用。',
        tag: '中文'
      },
      {
        id: 'so360',
        label: '360',
        desc: '360图片。中文图片，适合普通场景、素材图；国内直接可用。',
        tag: '中文'
      },
      {
        id: 'duitang',
        label: '堆糖',
        desc: '堆糖。中文美图社区，适合明星、穿搭、美食、生活场景；国内直接可用。',
        tag: '中文'
      },
      {
        id: 'xiurenai',
        label: '秀人网',
        desc: '秀人网，国内美女写真套图站，关键词搜索返回图集内高清大图（每个图集几十到上百张）；国内直连可用。',
        tag: '写真'
      },
      {
        id: 'foamgirl',
        label: 'FoamGirl',
        desc: 'FoamGirl，亚洲性感美女写真图站，关键词搜索返回原图；需海外网络。',
        tag: '写真'
      }
    ]
  },
  {
    name: '国外数据源',
    items: [
      {
        id: 'pexels',
        label: 'Pexels',
        desc: 'Pexels 免版权图库。高质量摄影，适合风景、人物、商务素材；无需 key。',
        tag: '免版权'
      },
      {
        id: 'openverse',
        label: 'Openverse',
        desc: 'Openverse 聚合图库。汇集 Flickr、维基等千万级 CC 授权图片，覆盖极广；无需 key，需海外网络。',
        tag: '聚合'
      },
      {
        id: 'wikimedia',
        label: '维基共享',
        desc: 'Wikimedia Commons。百科级大图（公有领域/CC），适合人物、地点、历史、知识类；无需 key，需海外网络。',
        tag: '百科'
      },
      {
        id: 'wallhaven',
        label: 'Wallhaven',
        desc: 'Wallhaven 壁纸库。适合风景、动漫、游戏壁纸，支持 2K/4K 原图；无需 key，需海外网络。',
        tag: '壁纸'
      },
      {
        id: 'wallhere',
        label: 'Wallhere',
        desc: 'Wallhere 壁纸库。大量动漫/风景/游戏壁纸原图；需海外网络。',
        tag: '壁纸'
      },
      {
        id: 'yande',
        label: 'yande.re',
        desc: 'yande.re 动漫壁纸站。高清日系插画/壁纸，支持英文标签（如 cat、blue_archive）；需海外网络。',
        tag: '动漫'
      },
      {
        id: 'pxhere',
        label: 'pxhere',
        desc: 'pxhere 免版权摄影图库。CC0 授权可商用，适合风光、静物、人文；无需 key。',
        tag: '免版权'
      },
      {
        id: 'pixabay',
        label: 'Pixabay',
        desc: 'Pixabay 免版权图库。适合风景、自然、物体、商务素材；不适合特定名人、品牌、小众内容。',
        tag: '免版权'
      },
      {
        id: 'unsplash',
        label: 'Unsplash',
        desc: 'Unsplash 免版权图库。高质量摄影，适合设计素材、壁纸；无 key 时被防护墙拦截，需免费配置 Access Key。\n\n配置步骤：\n1. 打开 unsplash.com/developers 注册登录\n2. 点 "Your apps" → "New application"，同意协议创建\n3. 复制 App 的 Access Key\n4. 云端：Vercel → Settings → Environment Variables 新增 UNSPLASH_KEY → Redeploy',
        tag: '免版权'
      },
      {
        id: 'giphy',
        label: 'Giphy',
        desc: 'Giphy 动图库。返回 GIF 动图原图，适合表情包、动态素材；需海外网络。',
        tag: '动图'
      },
      {
        id: 'youtube',
        label: 'YouTube',
        desc: 'YouTube 缩略图。返回视频封面图，适合视频题材、封面素材；并非图片搜索。',
        tag: '视频封面'
      },
      {
        id: 'custom',
        label: '自定义网址',
        desc: '提取任意网页内的图片（兜底方案）。适合单页批量取图，如推特帖文、图集页面等。',
        tag: '兜底'
      }
    ]
  }
]

export const sourceMap = Object.fromEntries(
  SOURCE_GROUPS.flatMap((g) => g.items.map((s) => [s.id, s]))
)

export const SIMPLE_GROUPS = [
  {
    id: 'photos',
    label: '写真',
    tag: '写真',
    desc: '写真套图汇总：秀人网/FoamGirl',
    sources: ['xiurenai', 'foamgirl']
  },
  {
    id: 'browser',
    label: '浏览器',
    tag: '通用',
    desc: '搜索引擎汇总：必应/百度/360/堆糖',
    sources: ['bing', 'baidu', 'so360', 'duitang']
  },
  {
    id: 'library',
    label: '图库',
    tag: '图库',
    desc: '免版权图库汇总：Pexels/Pixabay/Openverse/维基/Wallhaven/pxhere/Unsplash/Giphy/Wallhere/yande.re',
    sources: ['pexels', 'pixabay', 'openverse', 'wikimedia', 'wallhaven', 'pxhere', 'unsplash', 'giphy', 'wallhere', 'yande']
  }
]

export const NOVEL_SOURCES = [
  { id: 'biquga', label: '笔趣阁', desc: '笔趣阁（biquga.com），中文网文小说库；Vercel 云上可直接访问。', tag: '中文' }
]

export const SIMPLE_NOVEL_GROUPS = [
  {
    id: 'wangwen',
    label: '网文',
    tag: '网文',
    desc: '笔趣阁（biquga.com）—— 普通网文小说库',
    sources: ['biquga']
  }
]
