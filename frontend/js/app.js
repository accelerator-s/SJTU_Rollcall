// Vue 根实例：签到扫码主应用
import api from '/static/js/api.js';

const { createApp, ref, onMounted, onUnmounted, nextTick } = Vue;
const { ElMessage } = ElementPlus;

// 内联 SVG 图标
const ICONS = {
  scan: `<svg viewBox="0 0 16 16"><rect x="1" y="1" width="5" height="5" rx=".8" fill="none" stroke="currentColor" stroke-width="1.2"/><rect x="10" y="1" width="5" height="5" rx=".8" fill="none" stroke="currentColor" stroke-width="1.2"/><rect x="1" y="10" width="5" height="5" rx=".8" fill="none" stroke="currentColor" stroke-width="1.2"/><rect x="10" y="10" width="5" height="5" rx=".8" fill="none" stroke="currentColor" stroke-width="1.2"/><rect x="3" y="3" width="1.5" height="1.5" fill="currentColor"/><rect x="12" y="3" width="1.5" height="1.5" fill="currentColor"/><rect x="3" y="12" width="1.5" height="1.5" fill="currentColor"/></svg>`,

  checkCircle: `<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="9" fill="#107c10"/><path d="M6 10l2.5 3L14 7" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`,

  errorCircle: `<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="9" fill="#d13438"/><path d="M7 7l6 6M13 7l-6 6" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>`,

  warnCircle: `<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="9" fill="#797600"/><path d="M10 6v5" stroke="#fff" stroke-width="2" stroke-linecap="round"/><circle cx="10" cy="14" r="1.2" fill="#fff"/></svg>`,

  camera: `<svg viewBox="0 0 16 16"><path d="M2 4.5h2l1-2h6l1 2h2a1 1 0 011 1v7a1 1 0 01-1 1H2a1 1 0 01-1-1v-7a1 1 0 011-1z" fill="none" stroke="currentColor" stroke-width="1.1"/><circle cx="8" cy="8.5" r="2.5" fill="none" stroke="currentColor" stroke-width="1.1"/></svg>`,

  history: `<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M8 4.5V8l2.5 1.5" stroke="currentColor" stroke-width="1.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`,

  user: `<svg viewBox="0 0 16 16"><circle cx="8" cy="5" r="3" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M2 14c0-3.3 2.7-6 6-6s6 2.7 6 6" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>`,
};

const App = {
  template: `
    <div style="display:flex;flex-direction:column;height:100vh;">

      <!-- 顶部栏 -->
      <div class="az-header">
        <div class="az-header__left">
          <div class="az-header__brand">SJTU 签到助手</div>
        </div>
        <div class="az-header__right">
          <div class="az-header__status" :class="{
            'az-header__status--ok':  configured,
            'az-header__status--err': !configured
          }">
            <span class="az-header__dot" :class="{
              'az-header__dot--ok':  configured,
              'az-header__dot--err': !configured
            }"></span>
            {{ configured ? jaccount : '未配置账号' }}
          </div>
        </div>
      </div>

      <!-- 主内容 -->
      <div class="az-main">
        <div class="az-page">

          <!-- 未配置提示 -->
          <div v-if="!configured" class="az-status-banner az-status-banner--warn">
            <div class="az-status-banner__icon" v-html="icons.warnCircle"></div>
            <div class="az-status-banner__text">
              <div class="az-status-banner__title">未配置 jAccount 账号</div>
              <div class="az-status-banner__desc">
                请在 config/default_config.json 中填写 jaccount 和 password 字段后重启服务
              </div>
            </div>
          </div>

          <!-- 扫码卡片 -->
          <div class="az-card">
            <div class="az-card__header">
              <div>
                <div class="az-card__title">扫码签到</div>
                <div class="az-card__subtitle">将摄像头对准签到二维码</div>
              </div>
            </div>
            <div class="az-card__body">
              <div class="scanner-wrapper">
                <div id="qr-reader"></div>
                <div class="scanner-overlay" v-if="scanning && !processing">
                  <div class="scanner-overlay__corner scanner-overlay__corner--tl"></div>
                  <div class="scanner-overlay__corner scanner-overlay__corner--tr"></div>
                  <div class="scanner-overlay__corner scanner-overlay__corner--bl"></div>
                  <div class="scanner-overlay__corner scanner-overlay__corner--br"></div>
                  <div class="scanner-overlay__line"></div>
                </div>
                <div class="scanner-processing" v-if="processing">
                  <div class="scanner-processing__spinner"></div>
                  <div class="scanner-processing__text">正在签到...</div>
                </div>
              </div>
              <div class="scanner-controls">
                <el-button
                  :type="scanning ? 'danger' : 'primary'"
                  size="large"
                  @click="toggleScanner"
                  :disabled="processing || !configured"
                >
                  {{ scanning ? '停止扫码' : '开始扫码' }}
                </el-button>
              </div>
            </div>
          </div>

          <!-- 签到记录 -->
          <div class="az-card">
            <div class="az-card__header">
              <div>
                <div class="az-card__title">签到记录</div>
                <div class="az-card__subtitle">当前会话的签到历史</div>
              </div>
              <el-button v-if="history.length > 0" size="small" text type="danger" @click="clearHistory">
                清空
              </el-button>
            </div>
            <div class="az-card__body">
              <div class="sign-history" v-if="history.length > 0">
                <transition-group name="az-fade">
                  <div
                    v-for="item in history"
                    :key="item.id"
                    class="sign-history__item"
                  >
                    <div class="sign-history__icon"
                         v-html="item.success ? icons.checkCircle : icons.errorCircle"></div>
                    <div class="sign-history__content">
                      <div class="sign-history__message"
                           :class="item.success ? 'az-text-success' : 'az-text-danger'">
                        {{ item.message }}
                      </div>
                      <div class="sign-history__time">{{ item.time }}</div>
                      <div class="sign-history__url">{{ item.url }}</div>
                    </div>
                  </div>
                </transition-group>
              </div>
              <div v-else class="sign-history__empty">暂无签到记录</div>
            </div>
          </div>

        </div>
      </div>
    </div>
  `,

  setup() {
    const icons = ICONS;
    const configured = ref(false);
    const jaccount = ref('');
    const scanning = ref(false);
    const processing = ref(false);
    const history = ref([]);

    let scanner = null;
    let historyIdCounter = 0;
    let lastScannedUrl = '';
    let lastScannedTime = 0;

    // 格式化当前时间
    const formatTime = () => {
      const d = new Date();
      const pad = (n) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    };

    // 添加记录
    const addHistory = (success, message, url) => {
      history.value.unshift({
        id: ++historyIdCounter,
        success,
        message,
        url,
        time: formatTime(),
      });
    };

    // 清空记录
    const clearHistory = () => {
      history.value = [];
      ElMessage.success('已清空签到记录');
    };

    // 二维码扫描成功回调
    const onScanSuccess = async (decodedText) => {
      // 防抖：同一 URL 5 秒内不重复处理
      const now = Date.now();
      if (decodedText === lastScannedUrl && now - lastScannedTime < 5000) {
        return;
      }
      lastScannedUrl = decodedText;
      lastScannedTime = now;

      // 验证 URL 格式
      if (!decodedText.startsWith('https://mlearning.sjtu.edu.cn/lms/mobile2/forscan/')) {
        return;
      }

      processing.value = true;

      try {
        const result = await api.sign(decodedText);
        if (result.success) {
          ElMessage.success(result.message || '签到成功');
          addHistory(true, result.message || '签到成功', decodedText);
        } else {
          ElMessage.error(result.message || '签到失败');
          addHistory(false, result.message || '签到失败', decodedText);
        }
      } catch (err) {
        const msg = err.response?.data?.message || '签到请求异常';
        addHistory(false, msg, decodedText);
      } finally {
        processing.value = false;
      }
    };

    // 启动/停止扫码
    const toggleScanner = async () => {
      if (!configured.value) {
        ElMessage.warning('请先在 config/default_config.json 中配置账号密码并重启服务');
        return;
      }

      if (scanning.value) {
        await stopScanner();
      } else {
        await startScanner();
      }
    };

    const requestCameraPermission = async () => {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('BROWSER_CAMERA_API_UNSUPPORTED');
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: false,
      });
      stream.getTracks().forEach((track) => track.stop());
    };

    const startScanner = async () => {
      await nextTick();

      if (!scanner) {
        scanner = new Html5Qrcode('qr-reader');
      }

      try {
        await requestCameraPermission();

        const config = {
          fps: 5,
          qrbox: (viewfinderWidth, viewfinderHeight) => {
            const size = Math.min(viewfinderWidth, viewfinderHeight) * 0.6;
            return { width: size, height: size };
          },
          aspectRatio: 1,
        };

        const cameraOptions = [
          { facingMode: { exact: 'environment' } },
          { facingMode: 'environment' },
          { facingMode: 'user' },
        ];

        try {
          const cameras = await Html5Qrcode.getCameras();
          if (Array.isArray(cameras) && cameras.length > 0) {
            cameraOptions.push({ deviceId: { exact: cameras[0].id } });
          }
        } catch { /* noop */ }

        let started = false;
        let lastError = null;

        for (const cameraOption of cameraOptions) {
          try {
            await scanner.start(cameraOption, config, onScanSuccess, () => {});
            started = true;
            break;
          } catch (error) {
            lastError = error;
          }
        }

        if (!started) {
          throw lastError || new Error('NO_CAMERA_AVAILABLE');
        }

        scanning.value = true;
      } catch (err) {
        const errName = err?.name || '';
        if (err?.message === 'BROWSER_CAMERA_API_UNSUPPORTED') {
          ElMessage.error('当前浏览器不支持摄像头调用，请更换为最新版 Chrome/Edge');
        } else if (errName === 'NotAllowedError' || errName === 'PermissionDeniedError') {
          ElMessage.error('摄像头权限被拒绝，请在浏览器地址栏中允许摄像头后重试');
        } else if (errName === 'NotFoundError' || errName === 'DevicesNotFoundError') {
          ElMessage.error('未检测到可用摄像头设备');
        } else {
          ElMessage.error('无法启动摄像头，请确认浏览器权限与摄像头设备可用');
        }
        console.error('Camera start error:', err);
      }
    };

    const stopScanner = async () => {
      if (scanner) {
        try {
          await scanner.stop();
        } catch { /* noop */ }
      }
      scanning.value = false;
    };

    // 获取配置状态
    const checkStatus = async () => {
      try {
        const resp = await api.getStatus();
        configured.value = resp.configured;
        jaccount.value = resp.jaccount || '';
      } catch { /* noop */ }
    };

    onMounted(() => {
      checkStatus();
    });

    onUnmounted(() => {
      stopScanner();
    });

    return {
      icons,
      configured,
      jaccount,
      scanning,
      processing,
      history,
      toggleScanner,
      clearHistory,
    };
  },
};

// 启动应用
const app = createApp(App);
app.use(ElementPlus);

for (const [key, comp] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, comp);
}

app.mount('#app');
