# 蛋蛋小工具

一个完全在本机运行的 Windows 文件处理工具：支持图片压缩、视频压缩、电脑录屏、RapidOCR 中英文识别、PDF 转 Excel / Word、MODNet 人像抠图和印章抠图。文件不会上传互联网，也不会保留处理历史；除用户主动保存的最终结果外，处理过程中产生的临时文件会自动清理。

## Windows 下载与安装

> [下载最新版 Windows 安装包（蛋蛋小工具安装程序.exe）](https://github.com/DanDan9947/All-in-one-tool/releases/latest/download/%E8%9B%8B%E8%9B%8B%E5%B0%8F%E5%B7%A5%E5%85%B7%E5%AE%89%E8%A3%85%E7%A8%8B%E5%BA%8F.exe)

也可以进入 [GitHub Releases](https://github.com/DanDan9947/All-in-one-tool/releases/latest) 查看版本说明、校验值和便携版压缩包。

- 系统要求：Windows 10/11 64 位。
- 安装方式：下载后运行 `蛋蛋小工具安装程序.exe`，按向导完成安装；可选择是否创建桌面快捷方式。
- 卸载方式：打开 Windows“设置”→“应用”→“已安装的应用”，找到“蛋蛋小工具”并卸载。
- 隐私说明：文件在本机处理，不上传互联网；临时文件会自动清理。

当前安装包尚未进行商业代码签名，Windows SmartScreen 可能显示“Windows 已保护你的电脑”。请只从本项目的 GitHub Releases 下载；确认发布者和版本来源后，可选择“更多信息”→“仍要运行”。

> 维护者注意：`dist/` 是构建产物并已被 Git 忽略，不要把 EXE 直接提交到仓库。发布新版本时，请按 [RELEASE.md](RELEASE.md) 将安装包上传为 GitHub Release 附件；首次 Release 发布前，上面的下载链接暂时不可用。

## 项目组成

- `miniprogram/`：原生微信小程序 TypeScript 页面。
- `web/`：Vue 3、Vite、TypeScript 响应式网页。
- `server/`：FastAPI、RapidOCR、MODNet ONNX，以及 PDF/Office 转换服务。
- `deploy/`：Docker Compose、Nginx HTTPS 和 Windows 打包配置。

## 1. Conda 本地环境

项目使用独立 Python 3.11 环境，不修改 Conda base 环境。在 PowerShell 中执行：

```powershell
conda create -n wechat-image-tools python=3.11 -y
conda activate wechat-image-tools
python -m pip install -r server/requirements-dev.txt
```

下载 Apache 2.0 许可的 MODNet photographic ONNX 权重：

```powershell
python server/scripts/download_models.py
```

脚本会输出模型 SHA-256。当前验证权重的 SHA-256 已记录在 `.env.example`；正式部署时复制到 `.env`，服务启动时便会校验权重。

RapidOCR 需要一个本地字体来构造结果对象。Windows 和项目 Docker 镜像会自动使用系统字体；其他 Linux 环境若没有 DejaVu Sans，请通过 `OCR_FONT_PATH` 指定一个本地 TTF/TTC 文件。

## 2. 启动与验证后端

从项目根目录运行：

```powershell
conda activate wechat-image-tools
uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --reload
```

在 PyCharm 中也可以直接打开 `server/run.py`，右键选择 **Run 'run'**。该文件提供与 Java `main` 方法类似的一键开发启动入口。

检查接口：

```powershell
curl.exe http://127.0.0.1:8000/api/v1/health
```

开发环境接口文档位于 `http://127.0.0.1:8000/docs`。健康检查中的 `ocrReady` 和 `cutoutReady` 都应为 `true`。

运行测试：

```powershell
python -m pytest server/tests -q
```

## 3. 打开微信小程序

1. 安装微信开发者工具并导入本目录的 `project.config.json`。
2. 测试阶段使用 `touristappid`。
3. 在开发者工具中开启“不校验合法域名、web-view（业务域名）、TLS版本以及HTTPS证书”。
4. 模拟器访问本机后端使用 `http://127.0.0.1:8000`；真机调试时，把 `miniprogram/config.ts` 改为电脑局域网地址，例如 `http://192.168.1.10:8000`，并允许 Windows 防火墙入站访问8000端口。

正式发布前，将地址替换为已备案且配置在微信公众平台的 HTTPS 合法域名。

## 4. 启动与验证网页

网页开发环境会把 `/api` 请求代理到 `http://127.0.0.1:8000`。先启动后端，再打开新的 PowerShell：

```powershell
cd web
npm install
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`。运行网页测试和生产构建：

```powershell
npm test
npm run build
```

生产 Docker 镜像由 `deploy/web.Dockerfile` 构建 Vue 静态资源，Nginx 在同一域名的 `/` 提供网页，并将 `/api/` 转发到 FastAPI。

## API

### `GET /api/v1/health`

返回服务及模型就绪状态，不公开本地模型路径。

### `POST /api/v1/ocr`

标准客户端使用 `multipart/form-data`，字段名为 `file`；也支持请求体直接发送 JPEG、PNG 或 WebP。返回合并文本、逐行文本及置信度。

### `POST /api/v1/cutout`

标准客户端使用 `multipart/form-data`，字段名为 `file`；小程序使用原始图片 `ArrayBuffer`，并设置正确的 `Content-Type`。成功时直接返回 `image/png`。

### `POST /api/v1/image-compressions`

压缩 JPG、PNG 或 WebP 图片，支持小体积、均衡、高清与自定义预设。网页使用 `multipart/form-data`，小程序也可以发送原始图片请求体；结果通过响应头返回原始大小、输出大小、格式、尺寸、压缩率和目标大小状态。图片压缩单文件上限为 50MB。

### 视频压缩接口

- `POST /api/v1/video-compressions`：上传 MP4、MOV、MKV 或 WebM 并创建异步压缩任务。
- `GET /api/v1/video-compressions/{jobId}`：查询排队、压缩进度及结果状态。
- `GET /api/v1/video-compressions/results/{token}`：下载 H.264 + AAC MP4 结果。
- `DELETE /api/v1/video-compressions/{jobId}`：取消任务并清理临时文件。

Windows 本地版最大支持 2GB，在线部署默认限制 500MB；单任务压缩，结果保留 15 分钟。

### `POST /api/v1/pdf-conversions`

使用 `multipart/form-data` 上传，字段为 `file` 和 `outputFormat`（`xlsx` 或 `docx`）。支持 10MB、30 页以内、未加密且包含可选文字的 PDF。接口同步完成转换并返回临时下载令牌、文件名、格式和过期时间。

Excel 只提取表格：相同表头的跨页表格自动合并；`SA_RPT121` 付款类型差异报表会按固定列坐标重建明细、换行字段、小计和总计。Word 以可编辑内容优先，复杂版式为近似还原。

### `GET /api/v1/pdf-conversions/{token}/download`

下载转换后的 XLSX 或 DOCX。令牌不可猜测且 30 秒后失效，过期后返回 `RESULT_NOT_FOUND`。

所有 JSON 错误统一包含 `code`、`message` 和 `requestId`。图片和 PDF 上传上限均为10MB；PDF 转换默认单任务并发、120秒超时。

## Docker 上云

准备模型、域名和 HTTPS 证书后：

1. 把证书保存为 `deploy/certs/fullchain.pem` 和 `deploy/certs/privkey.pem`。
2. 将 `deploy/nginx.conf` 中的 `api.example.com` 替换为实际域名。
3. 在 `.env` 填写模型 SHA-256。
4. 执行：

```bash
docker compose --env-file .env -f deploy/docker-compose.yml up -d --build
```

生产环境使用一个 Uvicorn worker，避免每个 worker 重复加载模型。扩容时应增加容器实例，而不是在单容器中增加 worker。

## 隐私和上线检查

- 服务不建数据库，也不保存历史记录。图片不落盘；PDF 输入只在转换期间保存在临时目录，输出最多保留 30 秒并自动清理。Docker 使用临时内存文件系统存放这些文件。
- 视频压缩输入、输出仅存放在系统临时目录，任务取消、程序退出或结果超过 15 分钟后自动删除。
- Nginx限制上传大小和访问频率；生产服务器还应配置系统防火墙，仅开放80和443端口。
- 小程序隐私说明需写明图片用于文字识别或人像处理，PDF 用于文档格式转换，并说明临时文件的删除时限。
- 上线前完成域名 ICP 备案、小程序备案、HTTPS证书以及微信合法域名配置。
- 当前版本没有微信登录鉴权，只适合开发验证；公开发布前应增加登录态校验和用户级限流。

## 开源模型

- [RapidOCR](https://github.com/RapidAI/RapidOCR)
- [MODNet ONNX port](https://github.com/yakhyo/modnet)（Apache-2.0）
