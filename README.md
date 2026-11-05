# 存入思源 · PopClip 扩展

在任意 App 里选中文字，点一下 PopClip 图标，内容就以「摘录 + 来源」的嵌套列表追加到思源笔记指定文档。不打开思源、不弹窗、不打断当前操作。

## 特点

- **任意 App 划词**：浏览器、PDF 阅读器、微信、Pages、终端……只要能选中文字就能用。
- **可读性优先**：正文写成一个无序列表项，来源是缩进一层的子列表项，不再是与正文平级的引用块。
- **PDF 硬换行智能合并**：中文直连、英文补空格、行尾连字符还原断词；网页来源保留分行但仍留在同一个块里。应用名、网址、文字断行特征三重识别，覆盖 Edge 等浏览器内置 PDF 查看器。
- **四种目标定位**：文档 ID、笔记本 + 文档标题、今日日记、修饰键切换多场景。
- **不需要 API Token**：走思源 3.7+ 内置的 `SiYuan-Kernel` 命令行直接写 workspace，不用 Token、端口或 HTTP 服务。
- **干净**：不改剪贴板、不申请辅助功能权限、不联网、不上传任何数据。

## 写入效果

```markdown
- 地方政府不只是"守夜人"，而是深度参与经济发展的"运动员"。
  - 15:32 · [置身事内 - 读书笔记](https://example.com/article) · Safari
```

在 PDF 或微信等拿不到网页 URL 的场景，来源自动降级为 `15:32 · 预览`，不产生空链接。「保留来源信息」可一键关闭。

## 环境要求

| 项 | 要求 |
|---|---|
| 系统 | macOS（PopClip 为 macOS 专属） |
| 思源笔记 | 3.7 及以上（需内置 CLI） |
| PopClip | 2026.8.1 上验证过 |
| Python | 系统自带 `/usr/bin/python3`（需 Xcode Command Line Tools） |

## 安装

1. 从 [Releases](../../releases) 下载 `SiYuanClipper.popclipextz` 双击安装（GitHub 会把附件名中的空格替换成点，因此发布时使用无空格名，与本地的 `SiYuan Clipper.popclipextz` 是同一个包）；**或**双击本仓库的 `安装到PopClip.command`（推荐，脚本用临时副本安装，不会删掉源文件）。
2. 首次会弹「未签名扩展」警告，点确认即可。想永久免弹，在终端执行一次后重启 PopClip：

   ```bash
   defaults write com.pilotmoon.popclip LoadUnsignedExtensions -bool YES
   ```

3. 在 PopClip 设置里把「默认定位方式」改成 `今日日记` 即可零配置使用；或保持 `文档 ID` 并填入目标文档的块 ID。

> PopClip 从 `.popclipextz` 安装成功后会删除该 zip 文件，这是它的官方行为，不是文件损坏。

### 两种安装方式，该用哪个？

| | 直接双击 `.popclipextz` | 双击 `安装到PopClip.command` |
|---|---|---|
| 它是什么 | 扩展的压缩包，PopClip 官方安装格式 | 一个几行的 shell 脚本，**不是扩展本身** |
| 做了什么 | PopClip 直接读取并安装 | 把源目录复制到 `/tmp` → 打包 → 调用 PopClip 打开 |
| 安装之后 | **这个 zip 会被 PopClip 删除** | 源目录与本地文件不受影响，被删的只是临时副本 |
| 适合场景 | 从 Releases 下载后的一次性安装 | 已 clone 本仓库，或需要反复安装 / 更新 |

`安装到PopClip.command` 只做三件事：复制 `SiYuan Clipper.popclipext/` 到临时目录、打包成 `.popclipextz`、交给 PopClip；顺带刷新 `dist/` 里的分发副本。它**不修改插件内容、不联网、不写入 PopClip 的数据库**，两种方式装出来的扩展完全相同。

一句话：**从 Release 下载就双击 zip；本地已有仓库就双击 `.command`。**

## 文档

- [插件完整说明](<SiYuan Clipper.popclipext/Readme.md>)：15 项配置、四种定位方式、场景配置格式、反馈与排错。
- [功能介绍与常见问题](<docs/存入思源-PopClip划词摘录插件.md>)：适合发社区/论坛的图文说明。

## 目录结构

```
SiYuan Clipper.popclipext/    扩展本体
├── Config.yaml              扩展定义与 15 项设置
├── send.py                  主逻辑（Python 3，无第三方依赖）
└── Readme.md                完整说明
安装到PopClip.command         一键安装脚本（生成临时安装包并交给 PopClip，非扩展本体）
docs/                        功能介绍与 FAQ
```

## 工作原理

```
选中文本 → PopClip → send.py → SiYuan-Kernel block append --parent <文档ID> --file - → 思源
```

`send.py` 读取 PopClip 注入的 `POPCLIP_TEXT`、`POPCLIP_BROWSER_TITLE/URL`、`POPCLIP_APP_NAME`、`POPCLIP_MODIFIER_FLAGS` 等变量，组装成「列表项 + 子列表项」的 Markdown，通过 stdin 交给思源 CLI。按名称定位用只读 SQL 查 `blocks` 表，今日日记用 `dailynote create`。返回码 0 / 1 / 2 对应成功、运行失败、配置错误（PopClip 自动弹出设置面板）。

## 明确不做

截图 / 图片 / 文件 / OCR · 剪贴板接管 · 撤销上一条 · 全文搜索与管理笔记 · 同步 · 任何联网上传。加密笔记本不支持（思源 CLI 的限制）。

## 致谢

- [乔木闪记 Jot](https://github.com/joeseesun/qiaomu-jot)：重视原文、单独标注来源、场景化去处、明确能力边界的产品理念。
- [zotero-siyuan](https://github.com/loonghfut/zotero-siyuan)：CLI 优先、显式传递 workspace 的工程思路。
- [思源笔记](https://github.com/siyuan-note/siyuan) 内置 CLI · [PopClip 扩展开发文档](https://www.popclip.app/dev/)

## 许可证

[MIT](LICENSE)
