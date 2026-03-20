// Axios 封装
const { ElMessage } = ElementPlus;

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const msg = error.response?.data?.message
      || error.response?.data?.detail
      || error.message
      || '网络异常';
    ElMessage.error(msg);
    return Promise.reject(error);
  },
);

const api = {

  /** 获取配置状态 */
  getStatus() {
    return http.get('/status').then(r => r.data);
  },

  /** 提交签到请求 */
  sign(qrUrl) {
    return http.post('/sign', { qr_url: qrUrl }).then(r => r.data);
  },
};

export default api;
