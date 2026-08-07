// 数据源定义：每个源带 tier（lite=免费版 / plus=付费版专属）。
// plus 源请求需携带激活 token，后端 api 会校验。

export const SOURCE_GROUPS = [
  {
    name: '国内数据源',
    items: [
      {
        id: 'bing',
        label: '必应',
        desc: '必应图片搜索。通用性最强，适合绝大多数题材；中文搜索效果好，国内直接可用。',
        tag: '通用',
        tier: 'lite'
      },
      {
        id: 'baidu',
        label: '百度',
        desc: '百度图片。中文搜索最强，适合人物、明星、中文场景图；国内直接可用。',
        tag: '中文',
        tier: 'lite'
      },
      {
        id: 'so360',
        label: '360',
        desc: '360图片。中文图片，适合普通场景、素材图；国内直接可用。',
        tag: '中文',
        tier: 'lite'
      },
      {
        id: 'duitang',
        label: '堆糖',
        desc: '堆糖。中文美图社区，适合明星、穿搭、美食、生活场景；国内直接可用。',
        tag: '中文',
        tier: 'lite'
      },
      {
        id: 'xiurenai',
        label: '秀人网',
        desc: '秀人网，国内美女写真套图站，关键词搜索返回图集内高清大图（每个图集几十到上百张）；国内直连可用。',
        tag: '写真',
        tier: 'lite'
      },
      {
        id: 'meitulu',
        label: '美图录',
        desc: '成人内容！美图录，中文女优写真套图站，关键词搜索返回图集封面；国内直连可用。',
        tag: '成人',
        adult: true,
        tier: 'plus'
      },
      {
        id: 'xsnvshen',
        label: '秀色女神',
        desc: '成人内容！秀色女神，中文女优写真图集站，按关键词匹配图集标题返回封面；国内直连可用。',
        tag: '成人',
        adult: true,
        tier: 'plus'
      },
      {
        id: 'hhe62',
        label: 'hhe62美图',
        desc: '成人内容！hhe62 成人站美图图集，关键词匹配 7 个分类最新列表标题，返回图集内高清大图（按图集均分交错排列）。需配置 MACCMS_BASE（默认 https://zfxdrshm.top:2549）。',
        tag: '成人',
        adult: true,
        tier: 'plus'
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
        tag: '免版权',
        tier: 'plus'
      },
      {
        id: 'pixabay',
        label: 'Pixabay',
        desc: 'Pixabay 免版权图库。适合风景、自然、物体、商务素材；不适合特定名人、品牌、小众内容。',
        tag: '免版权',
        tier: 'plus'
      },
      {
        id: 'pxhere',
        label: 'pxhere',
        desc: 'pxhere 免版权摄影图库。CC0 授权可商用，适合风光、静物、人文；无需 key。',
        tag: '免版权',
        tier: 'plus'
      },
      {
        id: 'unsplash',
        label: 'Unsplash',
        desc: 'Unsplash 免版权图库。高质量摄影，适合设计素材、壁纸；无 key 时被防护墙拦截，需免费配置 Access Key。\n\n配置步骤：\n1. 打开 unsplash.com/developers 注册登录\n2. 点 "Your apps" → "New application"，同意协议创建\n3. 复制 App 的 Access Key\n4. 云端：Vercel → Settings → Environment Variables 新增 UNSPLASH_KEY → Redeploy',
        tag: '免版权',
        tier: 'plus'
      },
      {
        id: 'openverse',
        label: 'Openverse',
        desc: 'Openverse 聚合图库。汇集 Flickr、维基等千万级 CC 授权图片，覆盖极广；无需 key，需海外网络。',
        tag: '聚合',
        tier: 'plus'
      },
      {
        id: 'wikimedia',
        label: '维基共享',
        desc: 'Wikimedia Commons。百科级大图（公有领域/CC），适合人物、地点、历史、知识类；无需 key，需海外网络。',
        tag: '百科',
        tier: 'plus'
      },
      {
        id: 'wallhaven',
        label: 'Wallhaven',
        desc: 'Wallhaven 壁纸库。适合风景、动漫、游戏壁纸，支持 2K/4K 原图；无需 key，需海外网络。',
        tag: '壁纸',
        tier: 'plus'
      },
      {
        id: 'wallhere',
        label: 'Wallhere',
        desc: 'Wallhere 壁纸库。大量动漫/风景/游戏壁纸原图；需海外网络。',
        tag: '壁纸',
        tier: 'plus'
      },
      {
        id: 'yande',
        label: 'yande.re',
        desc: 'yande.re 动漫壁纸站。高清日系插画/壁纸，支持英文标签（如 cat、blue_archive）；需海外网络。',
        tag: '动漫',
        tier: 'plus'
      },
      {
        id: 'anime-pictures',
        label: 'Anime-Pictures',
        desc: 'Anime-Pictures 日系动漫图库。高清插画/壁纸，支持英文标签（如 cat、blue_archive），返回 AVIF 大图；需海外网络。',
        tag: '动漫',
        tier: 'plus'
      },
      {
        id: 'pixiv',
        label: 'Pixiv',
        desc: 'Pixiv 日本插画社区。关键词搜插图，支持 R18 内容。需在 Vercel 环境变量配置 PIXIV_PHPSESSID（=浏览器登录后 cookie 里的 PHPSESSID）；需海外网络。',
        tag: '插画',
        need_login: true,
        tier: 'plus'
      },
      {
        id: 'giphy',
        label: 'Giphy',
        desc: 'Giphy 动图库。返回 GIF 动图原图，适合表情包、动态素材；需海外网络。',
        tag: '动图',
        tier: 'plus'
      },
      {
        id: 'yahoo',
        label: 'Yahoo',
        desc: 'Yahoo 图片搜索，通用性强，适合各类题材；需海外网络。',
        tag: '通用',
        tier: 'plus'
      },
      {
        id: 'youtube',
        label: 'YouTube',
        desc: 'YouTube 缩略图。返回视频封面图，适合视频题材、封面素材；并非图片搜索。',
        tag: '视频封面',
        tier: 'plus'
      },
      {
        id: 'foamgirl',
        label: 'FoamGirl',
        desc: 'FoamGirl，亚洲性感美女写真图站，关键词搜索返回原图；需海外网络。',
        tag: '写真',
        tier: 'plus'
      },
      {
        id: 'xxknit',
        label: '爱妹国',
        desc: '爱妹国（写真/Cosplay 图集）中文站。关键词搜图集，返回封面图；需海外网络。',
        tag: '写真',
        tier: 'plus'
      },
      {
        id: 'pornhub',
        label: 'Pornhub',
        desc: '成人内容！Pornhub 视频封面图提取，适合视频题材封面素材；需海外节点。',
        tag: '成人',
        adult: true,
        tier: 'plus'
      },
      {
        id: 'pornhub-albums',
        label: 'Pornhub图集',
        desc: '成人内容！Pornhub 相册图集，关键词搜索返回图集内高清大图；需海外节点。',
        tag: '成人',
        adult: true,
        tier: 'plus'
      },
      {
        id: 'pornpics',
        label: 'PornPics',
        desc: '成人内容！PornPics 色情图片搜索站，关键词搜索返回图片；需海外节点。',
        tag: '成人',
        adult: true,
        tier: 'plus'
      },
      {
        id: 'photos18',
        label: 'Photos18',
        desc: '成人内容！Photos18 色情图片站，关键词搜索返回图片；需海外节点。',
        tag: '成人',
        adult: true,
        tier: 'plus'
      },
      {
        id: 'asiantolick',
        label: 'AsianToLick',
        desc: '成人内容！AsianToLick 亚洲色情图片站，关键词搜索返回原图；需海外节点。',
        tag: '成人',
        adult: true,
        tier: 'plus'
      },
      {
        id: 'custom',
        label: '自定义网址',
        desc: '提取任意网页内的图片（兜底方案）。适合单页批量取图，如推特帖文、图集页面等。',
        tag: '兜底',
        tier: 'lite'
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
    label: '国内搜索',
    tag: '搜索',
    desc: '国内搜索引擎：必应/百度/360/堆糖/秀人网（国内直连，中文效果好）',
    tier: 'lite',
    sources: ['bing', 'baidu', 'so360', 'duitang', 'xiurenai']
  },
  {
    id: 'porn_cn',
    label: '国内成人写真',
    tag: '成人',
    adult: true,
    desc: '美图录/秀色女神/hhe62美图（Plus 专属，成人内容）',
    tier: 'plus',
    sources: ['meitulu', 'xsnvshen', 'hhe62']
  },
  {
    id: 'library',
    label: '免版权图库',
    tag: '图库',
    desc: '免版权图库：Pexels/Pixabay/pxhere/Unsplash/Openverse/维基（需海外网络，Unsplash 需配置 Key）',
    tier: 'plus',
    sources: ['pexels', 'pixabay', 'pxhere', 'unsplash', 'openverse', 'wikimedia']
  },
  {
    id: 'wallpaper_anime',
    label: '壁纸插画动图',
    tag: '动漫',
    desc: '壁纸/插画/动图：Wallhaven/Wallhere/yande.re/Anime-Pictures/Pixiv/Giphy（需海外网络，Pixiv 需配置 PHPSESSID）',
    tier: 'plus',
    sources: ['wallhaven', 'wallhere', 'yande', 'anime-pictures', 'pixiv', 'giphy']
  },
  {
    id: 'photos_foreign',
    label: '海外写真',
    tag: '写真',
    desc: '海外写真图站：FoamGirl/爱妹国（需海外网络）',
    tier: 'plus',
    sources: ['foamgirl', 'xxknit']
  },
  {
    id: 'search_foreign',
    label: '海外搜索',
    tag: '通用',
    desc: '海外搜索/封面：Yahoo/YouTube封面（需海外网络）',
    tier: 'plus',
    sources: ['yahoo', 'youtube']
  },
  {
    id: 'porn_foreign',
    label: '海外成人',
    tag: '成人',
    adult: true,
    desc: '海外成人图库：Pornhub/PornHub图集/PornPics/Photos18/AsianToLick（需海外节点）',
    tier: 'plus',
    sources: ['pornhub', 'pornhub-albums', 'pornpics', 'photos18', 'asiantolick']
  }
]

export const NOVEL_SOURCES = [
  { id: 'aaanovel', label: 'AAA成人小说', desc: 'AAA成人小说，中文情色文学，关键词搜索返回小说文章；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: '1000novel', label: '1000成人小说', desc: '1000成人小说，中文情色文学；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: 'xbookcn', label: '中文成人文学', desc: '中文成人文学网（Blogger），长篇/短篇情色小说；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: 'hhhbook', label: '3H淫书', desc: '3H淫书，中文情色小说；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: 'canovel', label: 'CA情色小说', desc: 'CA情色小说，中文成人文学；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: 'h528', label: '风月文学网', desc: '风月文学网，中文情色文学；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: '69story', label: '69成人小说', desc: '69成人小说网，中文成人文学；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: 'biquga', label: '笔趣阁', desc: '笔趣阁（biquga.com），中文网文小说库；Vercel 云上可直接访问。', tag: '中文', tier: 'lite' },
  { id: 'bdsmcafe', label: 'BDSMCafe', desc: 'BDSMCafe，英文 BDSM 故事站；需代理。', tag: '英文', adult: true, tier: 'plus' },
  { id: 'chyoa', label: 'CHYOA', desc: 'CHYOA，英文互动色情小说站；需代理。', tag: '英文', adult: true, tier: 'plus' },
  { id: 'alicesw', label: '爱丽丝书屋', desc: '爱丽丝书屋（alicesw.com），中文原创小说站（含成人向作品），关键词直接搜索；国内可直连。', tag: '中文', adult: true, tier: 'plus' },
  { id: 'hhe62', label: 'hhe62小说', desc: '成人内容！hhe62 成人站小说分类（8 类），关键词匹配最新列表标题返回小说列表，点开阅读正文。需配置 MACCMS_BASE（默认 https://zfxdrshm.top:2549）。', tag: '中文', adult: true, tier: 'plus' }
]

export const SIMPLE_NOVEL_GROUPS = [
  {
    id: 'wangwen',
    label: '网文',
    tag: '网文',
    desc: '笔趣阁（biquga.com）—— 普通网文小说库',
    tier: 'lite',
    sources: ['biquga']
  },
  {
    id: 'porn_cn',
    label: '成人小说',
    tag: '成人',
    adult: true,
    desc: 'AAA成人小说/1000成人小说/中文成人文学/3H淫书/CA情色小说/风月文学网/69成人小说/爱丽丝书屋/hhe62小说',
    tier: 'plus',
    sources: ['aaanovel', '1000novel', 'xbookcn', 'hhhbook', 'canovel', 'h528', '69story', 'alicesw', 'hhe62']
  },
  {
    id: 'porn_en',
    label: 'porn英文',
    tag: '英文',
    adult: true,
    desc: 'BDSMCafe/CHYOA',
    tier: 'plus',
    sources: ['bdsmcafe', 'chyoa']
  }
]

export const COMIC_GROUPS = [
  {
    name: '韩漫',
    items: [
      { id: 'h-webtoon', label: 'H-Webtoon', desc: 'h-webtoon.com，中文韩漫/条漫，多章节整本下载；需海外网络。', tag: '韩漫' }
    ]
  },
  {
    name: '美漫',
    items: [
      { id: 'rokuhentai', label: 'Rokuhentai', desc: 'rokuhentai.com，美国网站欧美画风 H 漫图集，关键词翻成英文搜索；需海外网络。', tag: '美漫' },
      { id: 'allporncomic', label: 'AllPornComic', desc: 'allporncomic.com，英文站欧美漫画合集，关键词翻成英文搜索，多章节整本下载；需海外网络。', tag: '美漫' },
      { id: '8muses', label: '8muses', desc: '8muses.io，英文站欧美 3D 漫画图集，关键词翻成英文搜索，整本下载；需海外网络。', tag: '美漫' },
      { id: 'ilikecomix', label: 'ILikeComix', desc: 'ilikecomix.com，英文站欧美漫画图库，关键词翻成英文搜索，整本下载；需海外网络。', tag: '美漫' }
    ]
  },
  {
    name: '日漫',
    items: [
      { id: 'cartoon18', label: 'Cartoon18', desc: 'cartoon18.com，日文站日本漫画杂志扫描，关键词翻成日文搜索，多章节整本下载；需海外网络。', tag: '日漫' },
      { id: 'ho5ho', label: 'ho5ho', desc: 'ho5ho.com，繁中站 H 漫，关键词翻成繁中搜索，多章节整本下载；需海外网络。', tag: '日漫' }
    ]
  },
  {
    name: '全类型',
    items: [
      { id: 'wnacg', label: '绅士漫画', desc: '绅士漫画（wnacg.com），汉化本子/漫画图集，搜索后整本下载；需海外网络。', tag: '全类型' },
      { id: 'caitlin', label: 'Caitlin', desc: 'caitlin.top，英文站多语 H 漫图库，关键词翻成英文搜索，整本下载；国内直连可用。', tag: '全类型' },
      { id: '177picyy', label: '177picyy', desc: '177picyy.com，日文站图集，关键词翻成日文搜索，搜索后整本下载；国内直连可用。', tag: '全类型' },
      { id: 'xhentai888', label: 'xhentai888', desc: 'xhentai888.xyz，中文漫画合集，搜索不可用、按最新列表整本下载；国内直连可用。', tag: '全类型' },
      { id: 'sexacg', label: 'SexACG', desc: 'sexacg.xyz，CG/漫画合集图库，整本下载；国内直连可用。', tag: '全类型' },
      { id: 'hentaiclap', label: 'HentaiClap', desc: 'hentaiclap.com，英文站 Manga/Doujin/Western 混合图集，关键词翻成英文搜索，整本下载；需海外网络。', tag: '全类型' },
      { id: 'hentairun', label: 'HentaiRun', desc: 'hentairun.com，英文站 Manga/Doujinshi/Western/CG 全类型图集，关键词翻成英文搜索，整本下载；需海外网络。', tag: '全类型' }
    ]
  }
]

export const COMIC_SOURCES = COMIC_GROUPS.flatMap((g) => g.items.map((s) => ({ ...s, tier: 'plus' })))

export const SIMPLE_COMIC_GROUPS = [
  {
    id: 'korean',
    label: '韩漫',
    tag: '中文/原词',
    desc: 'H-Webtoon —— 站内为中文韩漫，原词搜索不翻译',
    sources: ['h-webtoon']
  },
  {
    id: 'american',
    label: '美漫',
    tag: '英文',
    desc: 'Rokuhentai/AllPornComic/8muses/ILikeComix —— 美国网站，关键词翻成英文搜索',
    sources: ['rokuhentai', 'allporncomic', '8muses', 'ilikecomix']
  },
  {
    id: 'japanese',
    label: '日漫',
    tag: '日文/繁中',
    desc: 'Cartoon18(日文站)/ho5ho(繁中站) —— 关键词翻成对应语言搜索',
    sources: ['cartoon18', 'ho5ho']
  },
  {
    id: 'general',
    label: '全类型',
    tag: '按站翻译',
    desc: '绅士漫画/xhentai888/SexACG 中文站原词搜；177picyy 日文站翻日文；Caitlin/HentaiClap/HentaiRun 英文站翻英文',
    sources: ['wnacg', 'caitlin', '177picyy', 'xhentai888', 'sexacg', 'hentaiclap', 'hentairun']
  }
]

export const comicSourceMap = Object.fromEntries(COMIC_SOURCES.map((s) => [s.id, s]))

// Plus 专属数据源判定（图片/小说）
export const PLUS_SOURCES = new Set(
  SOURCE_GROUPS.flatMap((g) => g.items)
    .filter((s) => s.tier === 'plus')
    .map((s) => s.id)
    .concat(NOVEL_SOURCES.filter((s) => s.tier === 'plus').map((s) => s.id))
    .concat(COMIC_SOURCES.map((s) => s.id))
)

export const LITE_SOURCES = new Set(
  SOURCE_GROUPS.flatMap((g) => g.items)
    .filter((s) => s.tier === 'lite')
    .map((s) => s.id)
    .concat(NOVEL_SOURCES.filter((s) => s.tier === 'lite').map((s) => s.id))
)
