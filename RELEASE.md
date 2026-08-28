# Windows 版本发布说明

Windows 安装包和便携版属于构建产物，不直接提交到 Git 仓库。项目的 `dist/` 已在 `.gitignore` 中忽略，面向用户的文件应上传到 GitHub Releases。

## 发布前检查

1. 在 `deploy/windows-installer.iss` 中更新 `AppVersion`，例如 `1.0.1`。
2. 在项目根目录构建 Windows 便携版：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\deploy\build-windows.ps1
   ```

3. 构建安装程序：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\deploy\build-installer.ps1
   ```

4. 确认以下文件能够在一台未安装开发环境的 Windows 10/11 64 位电脑上正常运行：

   - `dist/DandanTools-Setup.exe`
   - `dist/DandanTools-windows-x64.zip`

5. 计算并保存 SHA-256：

   ```powershell
   Get-FileHash .\dist\DandanTools-Setup.exe -Algorithm SHA256
   Get-FileHash .\dist\DandanTools-windows-x64.zip -Algorithm SHA256
   ```

## 发布到 GitHub Releases

1. 打开项目的 [Releases 页面](https://github.com/DanDan9947/All-in-one-tool/releases)，点击“Draft a new release”。
2. 创建与安装包版本一致的标签，例如 `v1.0.0`，并填写版本标题和更新内容。
3. 上传以下两个附件，文件名不要改变，否则 README 中的固定下载链接会失效：

   - `DandanTools-Setup.exe`
   - `DandanTools-windows-x64.zip`

4. 在发布说明中写入两个文件的 SHA-256，并注明支持 Windows 10/11 64 位、安装包是否已进行代码签名。
5. 点击“Publish release”。发布后验证以下链接：

   - [最新版发布页](https://github.com/DanDan9947/All-in-one-tool/releases/latest)
   - [最新版安装程序直链](https://github.com/DanDan9947/All-in-one-tool/releases/latest/download/DandanTools-Setup.exe)
   - [最新版便携版直链](https://github.com/DanDan9947/All-in-one-tool/releases/latest/download/DandanTools-windows-x64.zip)

## 首次发布建议

- 标签：`v1.0.0`
- 标题：`蛋蛋小工具 v1.0.0`
- 安装程序状态：未进行代码签名
- 安装程序 SHA-256：`5169AF77E4BBAF9C4EB1F25EAF684E94359A6D78E3AE4DCBF5A1D7FBA0AA8FB1`
- 便携版 ZIP SHA-256：`D00F8E8FACBF716672E3EBDC4CA46EAFE50F35554CE5E4364CEADB62629CD91D`

上述校验值对应 2026-08-27 完成测试后生成的 v1.0.0 产物。源码或打包配置再次修改后，发布前必须重新执行完整构建和测试，并更新 SHA-256。
