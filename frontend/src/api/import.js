import request from './request'

/** 上传采购台账（Excel/CSV），admin only；字段名 file */
export function uploadImportFile(formData) {
  return request.post('/import/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
  })
}

/** 下载采购记录导入模板（CSV） */
export function downloadImportTemplate() {
  return request.get('/import/template', { responseType: 'blob' })
}
