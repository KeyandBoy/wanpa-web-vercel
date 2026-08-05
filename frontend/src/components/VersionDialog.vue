<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { isLocal } from '../api'
import { license, resetLicense, setPlus } from '../license'

const props = defineProps({
  modelValue: Boolean
})
const emit = defineEmits(['update:modelValue', 'unlocked'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const step = ref(1) // 1 功能对比 → 2 扫码付款 → 3 输入激活码
const email = ref('')
const code = ref('')
const verifying = ref(false)
const done = ref(false)

// 收款码图片：放到 public/pay/ 下，可替换（wechat.png / alipay.png）
// 价格与文案：编辑 public/pay/config.json 即可，无需改代码
const PAY = {
  wechat: '/pay/wechat.png',
  alipay: '/pay/alipay.png',
  price: '19.9',
  priceNote: 'Plus 永久版（一次性买断）',
  contactNote: '付款后请将支付单号与邮箱发送给管理员，激活码将发到邮箱。'
}

onMounted(async () => {
  try {
    const r = await fetch('/pay/config.json')
    if (r.ok) {
      const cfg = await r.json()
      if (cfg.price) PAY.price = String(cfg.price)
      if (cfg.price_note) PAY.priceNote = cfg.price_note
      if (cfg.contact_note) PAY.contactNote = cfg.contact_note
    }
  } catch (e) {}
})

const isUnlocked = computed(() => license.version === 'plus')

const FEATURES = [
  { lite: true, plus: true, text: '国内图片搜索（必应/百度/360/堆糖/秀人）' },
  { lite: true, plus: true, text: '自定义网址图片提取' },
  { lite: true, plus: true, text: '笔趣阁小说 + 多层筛选 / AI 摘要' },
  { lite: false, plus: true, text: '海外免版权图库（Pexels/Pixabay/Unsplash 等）' },
  { lite: false, plus: true, text: '壁纸插画动图（Wallhaven/yande/Pixiv/Giphy 等）' },
  { lite: false, plus: true, text: '海外写真图库（FoamGirl 等）' },
  { lite: false, plus: true, text: '漫画板块（韩漫/美漫/日漫/全类型 14 源）' },
  { lite: false, plus: true, text: 'hhe62 小说' }
]

function resetForm() {
  step.value = 1
  email.value = ''
  code.value = ''
  done.value = false
}

function close() {
  resetForm()
  visible.value = false
}

async function doVerify() {
  const c = code.value.trim()
  if (!c) {
    ElMessage.warning('请输入激活码')
    return
  }
  verifying.value = true
  try {
    const r = await api.verify(c)
    if (r.ok && r.token) {
      setPlus(r.token, r.code)
      done.value = true
      ElMessage.success('激活成功，已解锁 Plus 版本')
      emit('unlocked')
      setTimeout(() => {
        resetForm()
        visible.value = false
      }, 1200)
    }
  } catch (e) {
    ElMessage.error(e.message || '激活失败')
  } finally {
    verifying.value = false
  }
}

function logout() {
  resetLicense()
  done.value = false
  resetForm()
  ElMessage.success('已切换回 Lite 免费版')
}

function goPay() {
  step.value = 2
}

function confirmPay() {
  const e = email.value.trim()
  if (!e || !/^\S+@\S+\.\S+$/.test(e)) {
    ElMessage.warning('请填写正确的邮箱，激活码将发送到该邮箱')
    return
  }
  ElMessage.success('已登记，激活码将发送到您的邮箱')
  step.value = 3
}

function goEnterCode() {
  step.value = 3
}

function copyCode() {
  const c = code.value.trim()
  if (c) {
    try {
      navigator.clipboard.writeText(c)
      ElMessage.success('已复制激活码')
    } catch (e) {}
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="版本与激活"
    width="640px"
    :close-on-click-modal="false"
    @close="resetForm"
  >
    <div class="steps">
      <div class="step" :class="{ active: step >= 1 }">
        <span class="step-num">1</span>
        <span class="step-label">功能对比</span>
      </div>
      <div class="step-line" :class="{ active: step >= 2 }"></div>
      <div class="step" :class="{ active: step >= 2 }">
        <span class="step-num">2</span>
        <span class="step-label">扫码付款</span>
      </div>
      <div class="step-line" :class="{ active: step >= 3 }"></div>
      <div class="step" :class="{ active: step >= 3 }">
        <span class="step-num">3</span>
        <span class="step-label">输入激活码</span>
      </div>
    </div>

    <div v-if="isUnlocked && done" class="unlocked-banner">
      已激活 Plus 版，永久有效。本机已解锁，随时可用。
    </div>

    <div v-if="step === 1" class="panel">
      <div class="cmp">
        <div class="cmp-row cmp-head">
          <div class="cmp-name">功能</div>
          <div class="cmp-lite">Lite 免费版</div>
          <div class="cmp-plus">Plus 付费版</div>
        </div>
        <div v-for="f in FEATURES" :key="f.text" class="cmp-row">
          <div class="cmp-name">{{ f.text }}</div>
          <div class="cmp-lite">
            <span :class="f.lite ? 'yes' : 'no'">{{ f.lite ? '✓' : '—' }}</span>
          </div>
          <div class="cmp-plus">
            <span :class="f.plus ? 'yes' : 'no'">{{ f.plus ? '✓' : '—' }}</span>
          </div>
        </div>
        <div class="cmp-actions">
          <el-button type="primary" size="large" @click="goPay">开通 Plus</el-button>
          <span v-if="!isUnlocked" class="dim">激活码永久有效，一次购买永久使用</span>
          <span v-else class="dim">当前已为 Plus 版</span>
        </div>
      </div>
    </div>

    <div v-else-if="step === 2" class="panel">
      <div class="pay">
        <div class="pay-price">¥{{ PAY.price }} · {{ PAY.priceNote }}</div>
        <div class="pay-qrs">
          <div class="pay-qr">
            <img :src="PAY.wechat" alt="微信收款码" />
            <span>微信支付</span>
          </div>
          <div class="pay-qr">
            <img :src="PAY.alipay" alt="支付宝收款码" />
            <span>支付宝</span>
          </div>
        </div>
        <div class="pay-tip">
          {{ PAY.contactNote }}
        </div>
        <el-form label-width="70px" label-position="left">
          <el-form-item label="邮箱">
            <el-input v-model="email" placeholder="用于接收激活码" clearable />
          </el-form-item>
        </el-form>
        <el-button type="primary" size="large" @click="confirmPay">我已付款并提交邮箱</el-button>
        <div class="pay-hascode">
          <el-button link @click="goEnterCode">已有激活码？直接输入</el-button>
        </div>
        <div class="pay-back">
          <el-button link @click="step = 1">← 返回功能对比</el-button>
        </div>
      </div>
    </div>

    <div v-else class="panel">
      <div class="activate">
        <el-form label-width="90px" label-position="left">
          <el-form-item label="激活码">
            <el-input
              v-model="code"
              placeholder="WANPA-XXXX-XXXX-XXXX"
              clearable
              @keyup.enter="doVerify"
            />
          </el-form-item>
        </el-form>
        <div class="activate-actions">
          <el-button type="primary" size="large" :loading="verifying" @click="doVerify">
            激活
          </el-button>
          <el-button v-if="code" link @click="copyCode">复制</el-button>
          <el-button link @click="step = 2">← 返回付款</el-button>
        </div>
        <div class="activate-tip">
          激活码将发送到您付款时填写的邮箱；一个码可在多台设备解锁（换新设备重复输入即可）。
        </div>
      </div>
    </div>

    <template #footer>
      <el-button v-if="isUnlocked" plain type="danger" @click="logout">退出并切换回 Lite</el-button>
      <el-button @click="close">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: 16px;
}
.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 72px;
  font-size: 12px;
  color: #909399;
}
.step-num {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: #f0f2f5;
  border: 2px solid #dcdfe6;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #c0c4cc;
}
.step.active .step-num {
  background: var(--brand, #409eff);
  border-color: var(--brand, #409eff);
  color: #fff;
}
.step-line {
  width: 40px;
  height: 2px;
  background: #dcdfe6;
  margin-bottom: 22px;
}
.step-line.active {
  background: var(--brand, #409eff);
}
.step.active .step-label {
  color: var(--brand, #409eff);
  font-weight: 600;
}
.panel {
  min-height: 240px;
}
.pay-back {
  margin-top: 10px;
}
.pay-hascode {
  margin-top: 12px;
}
.unlocked-banner {
  background: #f0f9eb;
  color: #67c23a;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 12px;
  font-size: 13px;
}
[data-theme='dark'] .unlocked-banner {
  background: #1d3a1f;
}
.cmp {
  font-size: 13px;
}
.cmp-row {
  display: flex;
  align-items: center;
  padding: 7px 0;
  border-bottom: 1px solid var(--border);
}
.cmp-row:last-child {
  border-bottom: none;
}
.cmp-head {
  font-weight: 700;
}
.cmp-name {
  flex: 1;
  min-width: 0;
  color: var(--text);
}
.cmp-lite,
.cmp-plus {
  width: 90px;
  text-align: center;
  flex-shrink: 0;
}
.cmp-head .cmp-lite {
  color: #909399;
}
.cmp-head .cmp-plus {
  color: var(--brand);
}
.yes {
  color: #67c23a;
  font-weight: 700;
}
.no {
  color: #c0c4cc;
}
.cmp-actions {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.dim {
  color: #909399;
  font-size: 12px;
}
.pay {
  text-align: center;
}
.pay-price {
  font-size: 20px;
  font-weight: 700;
  color: #f56c6c;
  margin-bottom: 14px;
}
.pay-qrs {
  display: flex;
  justify-content: center;
  gap: 20px;
}
.pay-qr {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
  font-size: 13px;
  color: var(--text);
}
.pay-qr img {
  width: 160px;
  height: 160px;
  object-fit: contain;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
}
.pay-tip {
  margin: 14px auto;
  max-width: 460px;
  font-size: 12px;
  color: #909399;
  line-height: 1.7;
}
.activate {
  padding: 6px 10px;
}
.activate-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.activate-tip {
  margin-top: 14px;
  font-size: 12px;
  color: #909399;
  line-height: 1.7;
}
</style>
