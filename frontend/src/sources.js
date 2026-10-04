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
        id: 'cg51',
        label: '51吃瓜网',
        desc: '成人内容！51吃瓜网，关键词搜索帖子后自动进帖抓取该帖全部图片（帖子=图集）；域名自动跟随最新地址，国内直连可用。',
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
  },
  {
    name: '随机·忽略关键词',
    items: [
      {
        id: 'dogceo',
        label: '旺财随机图',
        desc: '狗品种随机图片（dog.ceo）。不支持关键词，每次调用都返回不同内容；国内直连可用。',
        tag: '随机',
        tier: 'lite'
      },
      {
        id: 'catapi',
        label: '猫咪随机图',
        desc: '猫咪随机图片（TheCatAPI）。不支持关键词，每次调用都返回不同内容；需海外网络。',
        tag: '随机',
        tier: 'lite'
      },
      {
        id: 'bingwp',
        label: 'Bing壁纸库',
        desc: 'Bing 壁纸全量库（1600+ 张 1920x1080），按页轮换。不支持关键词；国内直连可用。',
        tag: '随机',
        tier: 'lite'
      },
      {
        id: 'bingbg',
        label: 'Bing每日壁纸',
        desc: 'Bing 每日壁纸接口（仅当日几张），按页轮换。不支持关键词；国内直连可用。',
        tag: '随机',
        tier: 'lite'
      },
      {
        id: 'picsum',
        label: 'Picsum图库',
        desc: 'Lorem Picsum 免费图库，带作者与尺寸，真分页浏览。不支持关键词；需海外网络。',
        tag: '随机',
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
    id: 'cg51',
    label: '51吃瓜',
    tag: '成人',
    adult: true,
    tier: 'plus',
    desc: '51吃瓜网：搜帖子后自动进帖抓全图，帖子即图集；域名自动跟随最新地址，国内直连',
    sources: ['cg51']
  },
  {
    id: 'random',
    label: '随机图片',
    tag: '随机',
    tier: 'lite',
    desc: '随机图片：旺财/猫咪/Bing壁纸库/Bing每日壁纸/Picsum（忽略关键词，每次结果都不同）',
    sources: ['dogceo', 'catapi', 'bingwp', 'bingbg', 'picsum']
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

// 视频源：tier 与 api/_auth.py 的 PLUS_VIDEO 必须保持一致
export const VIDEO_SOURCES = [
  {
    id: 'bing',
    label: '必应视频',
    desc: '必应视频聚合搜索，结果多为 B站、腾讯视频、爱奇艺等中文平台；国内直接可用。\n\n说明：部分结果站点（爱奇艺、搜狐）无法解析直链，选 B站、腾讯视频等条目即可。',
    tag: '中文聚合',
    tier: 'lite'
  },
  {
    id: 'bilibili',
    label: 'B站',
    desc: 'Bilibili 官方搜索 API，返回视频标题、封面、时长（按人气排序）；国内直接可用。\n\n在线播放采用双流同步（视频流 + 音频流），无需合并。',
    tag: '国内',
    tier: 'lite'
  },
  {
    id: 'acfun',
    label: 'AcFun',
    desc: 'AcFun 官方搜索接口，返回视频标题、封面、时长；国内直接可用。',
    tag: '国内',
    tier: 'lite'
  },
  {
    id: 'youku',
    label: '优酷',
    desc: '优酷视频聚合搜索（SSR 页面解析），返回标题、时长；国内直接可用。\n\n说明：结果无封面图，时长来自页面数据。',
    tag: '国内',
    tier: 'lite'
  },
  {
    id: 'mgtv',
    label: '芒果TV',
    desc: '芒果TV 官方搜索接口，返回影视剧/综艺/少儿等节目条目与封面；国内直接可用。\n\n说明：当前网络环境下播放源域名被阻断，芒果TV 条目暂无法播放，仅供浏览检索。',
    tag: '国内',
    tier: 'lite'
  },
  {
    id: 'yahoo',
    label: 'Yahoo视频',
    desc: 'Yahoo 视频聚合搜索，结果多为 YouTube、B站 等平台，含时长信息；需代理。',
    tag: '海外聚合',
    tier: 'lite'
  },
  {
    id: 'youtube',
    label: 'YouTube',
    desc: 'YouTube 站内搜索，在线播放封顶 1080p；需海外网络。\n\nDASH 站，播放时视频流与音频流分别加载后同步。',
    tag: '海外',
    tier: 'lite'
  },
  {
    id: 'twitter',
    label: 'Twitter/X',
    desc: 'Twitter/X 搜索含图片/视频的推文（需登录 Cookie，在设置 TWITTER_COOKIE 填写 auth_token=...; ct0=...）。视频取最高画质 HLS 流；需海外节点。',
    tag: '海外',
    tier: 'lite'
  },
  {
    id: 'pornhub',
    label: 'Pornhub',
    desc: '成人内容！Pornhub 站内搜索，在线播放封顶 1080p；需海外节点，且节点所在国家不能屏蔽成人站（如韩国会直接掐断）。\n\n注意：搜索结果不含时长信息，时长过滤请选「不限」；用链接解析 tab 粘贴视频页链接则不受此限制。\n\n出站代理：Vercel Environment Variables 里加 ADULT_PROXY=http://user:pass@host:port（只影响成人源，未配则回落全局 PROXY）；未配代理时数据中心出口会被源站降级成无关推荐页。',
    tag: '成人',
    adult: true,
    tier: 'plus'
  },
  {
    id: 'thothub',
    label: 'ThotHub',
    desc: '成人内容！ThotHub 站内搜索，在线播放封顶 1080p，含时长信息；需海外节点。\n\n出站代理：Vercel 环境变量 ADULT_PROXY=http://user:pass@host:port（只影响成人源，未配则回落全局 PROXY）。',
    tag: '成人',
    adult: true,
    tier: 'plus'
  },
  {
    id: 'xnxx',
    label: 'XNXX',
    desc: '成人内容！XNXX 站内搜索，在线播放封顶 1080p；需海外节点。\n\n搜索结果不含时长，时长过滤请选「不限」。\n\n出站代理：Vercel 环境变量 ADULT_PROXY=http://user:pass@host:port（只影响成人源，未配则回落全局 PROXY）。',
    tag: '成人',
    adult: true,
    tier: 'plus'
  },
  {
    id: 'xvideos',
    label: 'XVIDEOS',
    desc: '成人内容！XVIDEOS 站内搜索，在线播放封顶 1080p，含时长信息；需海外节点。\n\n出站代理：Vercel 环境变量 ADULT_PROXY=http://user:pass@host:port（只影响成人源，未配则回落全局 PROXY）。',
    tag: '成人',
    adult: true,
    tier: 'plus'
  },
  {
    id: 'xhamster',
    label: 'xHamster',
    desc: '成人内容！xHamster 站内搜索，在线播放封顶 1080p；需海外节点。\n\n搜索结果不含时长，时长过滤请选「不限」。\n\n出站代理：Vercel 环境变量 ADULT_PROXY=http://user:pass@host:port（只影响成人源，未配则回落全局 PROXY）。',
    tag: '成人',
    adult: true,
    tier: 'plus'
  },
  {
    id: 'doll',
    label: '玩偶姐姐',
    desc: '成人内容！玩偶姐姐/麻豆系（hongkongdollvideo.com，含麻豆传媒/蜜桃传媒/糖心Vlog/91制片厂/天美传媒），站内搜索返回视频列表，解析走 yt-dlp；需海外节点。\n\n本部署无浏览器环境，播放以嗅探/直链为准。',
    tag: '成人',
    adult: true,
    tier: 'plus'
  },
  {
    id: 'cg51',
    label: '51吃瓜网',
    desc: '成人内容！51吃瓜网站内搜索，帖子即视频，自动解析 HLS 流在线播放；域名自动跟随最新地址，国内直连可用。\n\n搜索结果不含时长，时长过滤请选「不限」。',
    tag: '成人',
    adult: true,
    tier: 'plus'
  },
  {
    id: 'xjj',
    label: '高质量小姐姐',
    desc: '随机小姐姐视频（api.kuleu.com）。不支持关键词，每次调用都返回不同 mp4 直链，可直接预览；国内直连可用。\n\n搜索结果不含时长，时长过滤请选「不限」。',
    tag: '随机',
    tier: 'lite'
  },
  {
    id: 'link',
    label: '链接解析',
    desc: '粘贴视频页面链接直接解析播放，支持 B站、YouTube 及大量 yt-dlp 支持的站点；无需搜索。',
    tag: '直链',
    tier: 'lite'
  }
]

export const videoSourceMap = Object.fromEntries(VIDEO_SOURCES.map((s) => [s.id, s]))

export const NOVEL_SOURCES = [
  { id: 'aaanovel', label: 'AAA成人小说', desc: 'AAA成人小说，中文情色文学，关键词搜索返回小说文章；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: '1000novel', label: '1000成人小说', desc: '1000成人小说，中文情色文学；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: 'xbookcn', label: '中文成人文学', desc: '中文成人文学网（Blogger），长篇/短篇情色小说；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: 'hhhbook', label: '3H淫书', desc: '3H淫书，中文情色小说；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: 'canovel', label: 'CA情色小说', desc: 'CA情色小说，中文成人文学；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: 'h528', label: '风月文学网', desc: '风月文学网，中文情色文学；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: '69story', label: '69成人小说', desc: '69成人小说网，中文成人文学；需代理。', tag: '中文', adult: true, tier: 'plus' },
  { id: 'biquga', label: '笔趣阁', desc: '笔趣阁（biquga.com），中文网文小说库；Vercel 云上可直接访问。', tag: '中文', tier: 'lite' },
  { id: 'txt800', label: '800小说网', desc: '800小说网（txt800.cc），中文网文小说下载站，关键词搜索返回书页，整本 TXT 下载；Vercel 云上可直接访问。', tag: '中文', tier: 'lite' },
  { id: 'bqgnovels', label: '新笔趣阁', desc: '新笔趣阁（bqgnovels.com），中文网文小说库，JSON API 干净搜索，分章节阅读/整本下载；Vercel 云上可直接访问。', tag: '中文', tier: 'lite' },
  { id: 'ttkan', label: '天天看小说', desc: '天天看小说（cn.ttkan.co），中文网文小说库，支持关键词搜索 + 按内容分类浏览（玄幻/都市/言情/仙侠等 15+ 分类），分章节阅读；Vercel 云上可直接访问。', tag: '中文', tier: 'lite', category: true },
  { id: 'bdsmcafe', label: 'BDSMCafe', desc: 'BDSMCafe，英文 BDSM 故事站；需代理。', tag: '英文', adult: true, tier: 'plus' },
  { id: 'chyoa', label: 'CHYOA', desc: 'CHYOA，英文互动色情小说站；需代理。', tag: '英文', adult: true, tier: 'plus' },
  { id: 'alicesw', label: '爱丽丝书屋', desc: '爱丽丝书屋（alicesw.com），中文原创小说站（含成人向作品），关键词直接搜索；国内可直连。', tag: '中文', adult: true, tier: 'plus' },
  { id: 'hhe62', label: 'hhe62小说', desc: '成人内容！hhe62 成人站小说分类（8 类），关键词匹配最新列表标题返回小说列表，点开阅读正文。需配置 MACCMS_BASE（默认 https://zfxdrshm.top:2549）。', tag: '中文', adult: true, tier: 'plus' }
]

export const SIMPLE_VIDEO_GROUPS = [
  {
    id: 'cn',
    label: '国内',
    tag: '中文',
    desc: '必应视频聚合搜索/B站/AcFun/优酷/芒果TV',
    tier: 'lite',
    sources: ['bing', 'bilibili', 'acfun', 'youku', 'mgtv']
  },
  {
    id: 'foreign',
    label: '国外通用',
    tag: '海外',
    desc: 'Yahoo视频/YouTube/Twitter',
    tier: 'lite',
    sources: ['yahoo', 'youtube', 'twitter']
  },
  {
    id: 'adult',
    label: 'porn成人',
    tag: '成人',
    adult: true,
    desc: 'Pornhub/ThotHub/XNXX/XVIDEOS/xHamster/玩偶姐姐/51吃瓜网',
    tier: 'plus',
    sources: ['pornhub', 'thothub', 'xnxx', 'xvideos', 'xhamster', 'doll', 'cg51']
  },
  {
    id: 'random',
    label: '随机视频',
    tag: '随机',
    desc: '随机小姐姐视频（忽略关键词，每次结果都不同，mp4 直链）',
    tier: 'lite',
    sources: ['xjj']
  },
  {
    id: 'link',
    label: '链接解析',
    tag: '直链',
    desc: '粘贴视频页面链接直接解析播放',
    tier: 'lite',
    sources: ['link']
  }
]

export const SIMPLE_NOVEL_GROUPS = [
  {
    id: 'wangwen',
    label: '网文',
    tag: '网文',
    desc: '笔趣阁/800小说网/新笔趣阁/天天看小说 —— 普通网文小说库（天天看支持分类浏览）',
    tier: 'lite',
    sources: ['biquga', 'txt800', 'bqgnovels', 'ttkan']
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
    .concat(VIDEO_SOURCES.filter((s) => s.tier === 'plus').map((s) => s.id))
    .concat(COMIC_SOURCES.map((s) => s.id))
)

export const LITE_SOURCES = new Set(
  SOURCE_GROUPS.flatMap((g) => g.items)
    .filter((s) => s.tier === 'lite')
    .map((s) => s.id)
    .concat(NOVEL_SOURCES.filter((s) => s.tier === 'lite').map((s) => s.id))
    .concat(VIDEO_SOURCES.filter((s) => s.tier === 'lite').map((s) => s.id))
)
