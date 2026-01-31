/**
 * API调用封装模块
 * 提供统一的API调用接口，处理错误和响应解析
 */

const api = async (path, options = {}) => {
  const fetchOptions = Object.assign({ headers: { "Content-Type": "application/json" } }, options || {});
  const res = await fetch(path, fetchOptions);
  const text = await res.text();
  try {
    const data = JSON.parse(text);
    // 如果响应状态不是2xx，抛出错误
    if (!res.ok) {
      // 422错误通常包含详细的验证错误信息
      let errorMsg = data.detail || data.message;
      if (Array.isArray(data.detail)) {
        errorMsg = data.detail.map(d => {
          const loc = (d && d.loc && Array.isArray(d.loc)) ? d.loc.join('.') : '';
          const msg = d && d.msg ? d.msg : '';
          return loc ? `${loc}: ${msg}` : (msg || JSON.stringify(d));
        }).join('; ');
      } else if (typeof data.detail === 'object') {
        errorMsg = JSON.stringify(data.detail);
      }
      throw new Error(errorMsg || `HTTP ${res.status}: ${res.statusText}`);
    }
    return data;
  } catch (e) {
    // 如果是我们抛出的错误，直接抛出
    if (e.message) throw e;
    // 非 JSON 响应，返回包装对象
    throw new Error(text || res.statusText || `HTTP ${res.status}: unknown error`);
  }
};
